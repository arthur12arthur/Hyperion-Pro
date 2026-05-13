# ============================================================
# HYPERION PRO v1 — Web Scraper (Historiques & Pronostics)
# src/data/web_scraper.py
# ============================================================

import logging
import time
import random
import requests
import google.generativeai as genai
import os
import json
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Récupère depuis le web :
    - L'historique des performances des chevaux
    - Les performances des jockeys
    - Les pronostics d'experts externes
    Utilise Gemini pour parser les pages complexes.
    """

    PARSE_PROMPT = """
    Analyse cette page web de courses hippiques et extrais les informations
    sur le cheval "{horse_name}". Retourne UNIQUEMENT un JSON valide :

    {{
      "horse_name": "{horse_name}",
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
      "expert_pronostic": "favori|outsider|non_partant|null",
      "expert_comment": "commentaire si disponible"
    }}

    Si une information est manquante, utilise null. Pas de texte hors JSON.
    """

    def __init__(self, config: dict):
        self.config = config
        self.ua = UserAgent()
        self.sources = self._load_sources()

        # Gemini pour parsing intelligent
        api_key = os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        self.gemini = genai.GenerativeModel(
            config.get("gemini", {}).get("model", "gemini-1.5-pro")
        )
        logger.info(f"✅ WebScraper initialisé — {len(self.sources)} sources")

    def _load_sources(self) -> list:
        """Charge les sources actives depuis la configuration."""
        sources = []
        lonab_cfg = self.config.get("sources", {}).get("lonab", {})
        sources.extend(lonab_cfg.get("pronostics", []))
        sources.extend(self.config.get("sources", {}).get("historical", []))
        return [s for s in sources if s.get("enabled", False)]

    def scrape(self, horses: list) -> dict:
        """
        Scrape les données web pour une liste de chevaux.
        Retourne : horse_name → données enrichies
        """
        web_data = {}

        for horse in horses:
            name = horse.get("horse_name", "")
            if not name:
                continue

            logger.info(f"  🔍 Recherche web : {name}")
            horse_data = self._scrape_horse(name)

            if horse_data:
                web_data[name] = horse_data

            time.sleep(random.uniform(1.0, 2.5))

        logger.info(f"  ✅ Web scraping : {len(web_data)}/{len(horses)} chevaux enrichis")
        return web_data

    def _scrape_horse(self, horse_name: str) -> dict:
        """Tente de scraper les données d'un cheval depuis plusieurs sources."""
        for source in self.sources:
            try:
                data = self._fetch_from_source(source, horse_name)
                if data and data.get("total_races", 0) > 0:
                    data["source"] = source["name"]
                    data["source_weight"] = source.get("weight", 1.0)
                    return data
            except Exception as e:
                logger.debug(f"    Source {source['name']} échouée pour {horse_name}: {e}")
                continue

        # Fallback : recherche générale via Gemini web
        return self._gemini_web_search(horse_name)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=8))
    def _fetch_from_source(self, source: dict, horse_name: str) -> dict:
        """Récupère et parse les données depuis une source spécifique."""
        headers = {"User-Agent": self.ua.random}
        search_url = f"{source['url']}/recherche?cheval={horse_name.replace(' ', '+')}"

        response = requests.get(search_url, headers=headers, timeout=12)
        response.raise_for_status()

        # Parser avec Gemini si la page est complexe
        page_text = BeautifulSoup(response.text, "lxml").get_text(
            separator="\n", strip=True
        )[:3000]  # Limiter pour Gemini

        if len(page_text) < 100:
            return None

        return self._parse_with_gemini(page_text, horse_name)

    def _parse_with_gemini(self, page_text: str, horse_name: str) -> dict:
        """Utilise Gemini pour parser intelligemment le contenu d'une page."""
        prompt = self.PARSE_PROMPT.format(horse_name=horse_name)
        full_prompt = f"{prompt}\n\nContenu de la page:\n{page_text}"

        response = self.gemini.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=1024
            )
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        return data

    def _gemini_web_search(self, horse_name: str) -> dict:
        """
        Fallback : demande à Gemini ses connaissances sur le cheval.
        Utile pour les chevaux connus sur le circuit LONAB.
        """
        try:
            prompt = f"""
            Donne-moi les informations disponibles sur le cheval de course "{horse_name}"
            qui court sur le circuit LONAB au Burkina Faso.
            Retourne UNIQUEMENT un JSON valide avec les champs :
            win_rate, place_rate, total_races, total_wins, best_distance,
            best_terrain, expert_pronostic, expert_comment.
            Si tu ne connais pas ce cheval, retourne null pour chaque champ.
            Pas de texte hors JSON.
            """
            response = self.gemini.generate_content(prompt)
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            data["source"] = "gemini_knowledge"
            data["source_weight"] = 0.4
            return data
        except Exception:
            return {}

    def scrape_jockey(self, jockey_name: str) -> dict:
        """
        Récupère les statistiques d'un jockey.
        Retourne : win_rate, place_rate, recent_form, specialty_distance
        """
        try:
            prompt = f"""
            Donne les statistiques du jockey "{jockey_name}" sur le circuit hippique
            LONAB Burkina Faso ou PMU France.
            Retourne UNIQUEMENT un JSON :
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
            """
            response = self.gemini.generate_content(prompt)
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"  ⚠️ Impossible de récupérer stats jockey {jockey_name}: {e}")
            return {}
