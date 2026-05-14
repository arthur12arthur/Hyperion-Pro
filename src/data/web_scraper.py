# ============================================================
# HYPERION PRO v1 — Web Scraper (Historiques & Pronostics)
# src/data/web_scraper.py
# ============================================================

import logging
import time
import random
import unicodedata
import re
import requests
import json
import os
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Délai entre requêtes HTTP (secondes)
HTTP_DELAY = (1.5, 3.0)
# Délai minimum entre appels Gemini (secondes)
GEMINI_MIN_DELAY = 10.0


class WebScraper:
    """
    Récupère les historiques des chevaux français (PMU France)
    depuis Turfoo et Zeturf. Ces chevaux courent en France mais
    la LONAB (Burkina Faso) les propose comme course du jour à ses parieurs.

    Gemini n'est appelé QU'UNE SEULE FOIS à la fin pour synthétiser
    toutes les données brutes récupérées — pas un appel par cheval.
    """

    TURFOO_SEARCH = "https://www.turfoo.fr/chevaux/{slug}/"
    ZETURF_SEARCH = "https://www.zeturf.fr/fr/chevaux/fiche/{slug}"

    SYNTHESIS_PROMPT = """
    Tu es un expert hippique. Voici les données brutes scrappées depuis des sites
    de courses hippiques françaises pour plusieurs chevaux du programme PMU du jour.

    Pour chaque cheval, analyse le texte brut et extrais les informations clés.
    Retourne UNIQUEMENT un JSON valide, sans texte avant ou après :

    {{
      "chevaux": [
        {{
          "horse_name": "NOM DU CHEVAL",
          "last_races": [
            {{
              "date": "YYYY-MM-DD",
              "position": 1,
              "total_runners": 10,
              "distance": 1600,
              "terrain": "plat",
              "jockey": "Nom",
              "odds": 3.5
            }}
          ],
          "win_rate": 0.25,
          "place_rate": 0.45,
          "best_distance": 1600,
          "best_terrain": "plat",
          "total_races": 20,
          "total_wins": 5,
          "expert_pronostic": "favori|outsider|null",
          "expert_comment": "commentaire synthétique"
        }}
      ]
    }}

    Données brutes :
    {raw_data}

    Si une information est manquante, utilise null. Pas de texte hors JSON.
    """

    def __init__(self, config: dict):
        self.config = config
        self.ua = UserAgent()

        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model = config.get("gemini", {}).get("model", "gemini-2.5-flash")
        self._last_gemini_call = 0.0

        logger.info("✅ WebScraper initialisé — 4 sources")

    # ── Utilitaires ──────────────────────────────────────────

    def _slug(self, name: str) -> str:
        """'THE SHADOW' → 'the-shadow'"""
        name = unicodedata.normalize("NFD", name.lower())
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")
        name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
        return name

    def _get(self, url: str) -> str | None:
        """Requête HTTP simple, retourne le texte brut ou None."""
        try:
            headers = {
                "User-Agent": self.ua.random,
                "Accept-Language": "fr-FR,fr;q=0.9",
                "Accept": "text/html,application/xhtml+xml,*/*",
            }
            r = requests.get(url, headers=headers, timeout=12)
            r.raise_for_status()
            text = BeautifulSoup(r.text, "lxml").get_text(separator="\n", strip=True)
            return text[:4000] if len(text) > 100 else None
        except Exception as e:
            logger.debug(f"    GET {url} → {e}")
            return None

    def _gemini_rate_wait(self):
        """Attend si nécessaire pour respecter le rate limit Gemini."""
        elapsed = time.time() - self._last_gemini_call
        if elapsed < GEMINI_MIN_DELAY:
            wait = GEMINI_MIN_DELAY - elapsed
            logger.debug(f"    ⏳ Rate limit Gemini — attente {wait:.1f}s")
            time.sleep(wait)
        self._last_gemini_call = time.time()

    def _parse_json(self, raw: str) -> dict | list | None:
        """Nettoie et parse un JSON retourné par Gemini."""
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.debug(f"    JSON parse error : {e}")
            return None

    # ── Scraping par cheval ──────────────────────────────────

    def _fetch_turfoo(self, horse_name: str) -> str | None:
        """Scrape la fiche cheval sur Turfoo."""
        url = self.TURFOO_SEARCH.format(slug=self._slug(horse_name))
        text = self._get(url)
        if text:
            logger.debug(f"    ✅ Turfoo OK : {horse_name}")
        return text

    def _fetch_zeturf(self, horse_name: str) -> str | None:
        """Scrape la fiche cheval sur Zeturf."""
        url = self.ZETURF_SEARCH.format(slug=self._slug(horse_name))
        text = self._get(url)
        if text:
            logger.debug(f"    ✅ Zeturf OK : {horse_name}")
        return text

    def _fetch_horse_raw(self, horse_name: str) -> str:
        """
        Tente Turfoo puis Zeturf.
        Retourne le texte brut disponible ou une chaîne vide.
        """
        text = self._fetch_turfoo(horse_name)
        if not text:
            time.sleep(random.uniform(*HTTP_DELAY))
            text = self._fetch_zeturf(horse_name)
        return text or ""

    # ── Scraping batch + synthèse Gemini unique ──────────────

    def scrape(self, horses: list) -> dict:
        """
        Scrape les données web pour tous les chevaux.
        1. Récupère le texte brut depuis Turfoo/Zeturf pour chaque cheval
        2. Envoie TOUT à Gemini en UN SEUL appel pour synthèse
        Retourne : horse_name → données enrichies
        """
        # Filtrer les chevaux valides
        valid_horses = [
            h for h in horses
            if h.get("horse_name") and
            h["horse_name"].upper() not in ("PLACEHOLDER", "")
        ]

        if not valid_horses:
            logger.warning("  ⚠️ Aucun cheval valide à scraper")
            return {}

        # ── Étape 1 : collecte HTTP (sans Gemini) ──
        raw_collection = {}
        for horse in valid_horses:
            name = horse.get("horse_name")
            logger.info(f"  🔍 Recherche web : {name}")
            raw_text = self._fetch_horse_raw(name)
            raw_collection[name] = raw_text
            time.sleep(random.uniform(*HTTP_DELAY))

        # ── Étape 2 : synthèse Gemini (UN SEUL appel) ──
        horses_found = {k: v for k, v in raw_collection.items() if v}
        horses_not_found = [k for k, v in raw_collection.items() if not v]

        if horses_not_found:
            logger.info(f"  ℹ️ {len(horses_not_found)} cheval(aux) non trouvé(s) sur les sources web")

        web_data = {}

        if horses_found:
            web_data = self._synthesize_with_gemini(horses_found)

        # Chevaux non trouvés → données minimales
        for name in horses_not_found:
            web_data[name] = {
                "horse_name": name,
                "source": "not_found",
                "source_weight": 0.1,
                "win_rate": None,
                "place_rate": None,
                "total_races": None,
                "total_wins": None,
                "last_races": [],
                "expert_pronostic": None,
                "expert_comment": None,
            }

        logger.info(f"  ✅ Web scraping : {len(horses_found)}/{len(valid_horses)} chevaux enrichis")
        return web_data

    def _synthesize_with_gemini(self, horses_raw: dict) -> dict:
        """
        Envoie toutes les données brutes à Gemini en UN SEUL appel.
        Retourne un dict horse_name → données structurées.
        """
        # Construire le bloc de données brutes
        raw_blocks = []
        for name, text in horses_raw.items():
            block = f"=== {name} ===\n{text[:2000]}\n"
            raw_blocks.append(block)

        raw_data = "\n".join(raw_blocks)
        prompt = self.SYNTHESIS_PROMPT.format(raw_data=raw_data)

        self._gemini_rate_wait()

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=4096
                )
            )

            parsed = self._parse_json(response.text)
            if not parsed or "chevaux" not in parsed:
                logger.warning("  ⚠️ Gemini n'a pas retourné de données structurées")
                return {}

            result = {}
            for horse_data in parsed["chevaux"]:
                name = horse_data.get("horse_name", "")
                if name:
                    horse_data["source"] = "turfoo_zeturf+gemini"
                    horse_data["source_weight"] = 0.85
                    result[name] = horse_data

            logger.info(f"  ✅ Gemini synthèse : {len(result)} chevaux analysés (1 appel API)")
            return result

        except Exception as e:
            logger.error(f"  ❌ Erreur synthèse Gemini : {e}")
            return {}

    # ── Jockey ───────────────────────────────────────────────

    def scrape_jockey(self, jockey_name: str) -> dict:
        """Récupère les statistiques d'un jockey via Turfoo."""
        slug = self._slug(jockey_name)
        url = f"https://www.turfoo.fr/jockeys/{slug}/"
        text = self._get(url)

        if not text:
            return {"jockey_name": jockey_name, "source": "not_found"}

        self._gemini_rate_wait()

        try:
            prompt = f"""
            Extrais les statistiques du jockey "{jockey_name}" depuis ce texte.
            Retourne UNIQUEMENT un JSON valide :
            {{
              "jockey_name": "{jockey_name}",
              "win_rate": 0.20,
              "place_rate": 0.45,
              "specialty_terrain": "plat",
              "specialty_distance": 1600,
              "recent_form": "bonne|moyenne|mauvaise",
              "total_wins_season": 15
            }}
            Si inconnu, retourne null pour chaque champ. Pas de texte hors JSON.

            Texte :
            {text[:2000]}
            """
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=512
                )
            )
            return self._parse_json(response.text) or {}
        except Exception as e:
            logger.warning(f"  ⚠️ Stats jockey {jockey_name} indisponibles : {e}")
            return {}
