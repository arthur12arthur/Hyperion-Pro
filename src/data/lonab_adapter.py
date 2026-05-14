# ============================================================
# HYPERION PRO v1 — Adaptateur LONAB (PDF → Data)
# src/data/lonab_adapter.py
# ============================================================

import os
import json
import logging
import requests
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

LONAB_PROGRAMME_URL = "https://lonab.bf/programme-pmub"
LONAB_BASE_URL = "https://lonab.bf"


class LONABAdapter:
    """
    Extrait les données du programme officiel LONAB (PDF)
    via Gemini Vision. Retourne un dictionnaire structuré
    par course et par cheval.
    """

    EXTRACTION_PROMPT = """
    Tu es un expert en courses hippiques. Analyse ce programme de courses LONAB (Burkina Faso).

    Extrais TOUTES les informations disponibles et retourne un JSON structuré UNIQUEMENT,
    sans texte avant ou après, selon ce format exact :

    {
      "date": "YYYY-MM-DD",
      "hippodrome": "nom du lieu",
      "races": [
        {
          "race_number": 1,
          "race_name": "nom de la course",
          "distance": 1600,
          "terrain": "plat|haies|obstacle",
          "conditions": "conditions de la course",
          "prize_money": 0,
          "horses": [
            {
              "horse_number": 1,
              "horse_name": "NOM DU CHEVAL",
              "jockey": "Nom Jockey",
              "trainer": "Nom Entraîneur",
              "weight": 56.5,
              "age": 4,
              "sex": "M|F|H",
              "form": "1-2-3-4-5",
              "owner": "Propriétaire",
              "odds_lonab": 3.5
            }
          ]
        }
      ]
    }

    Sois précis et exhaustif. Si une information est manquante, utilise null.
    """

    def __init__(self, config: dict):
        self.config = config
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY manquant dans les variables d'environnement")
        self.client = genai.Client(api_key=api_key)
        self.vision_model = config.get("gemini", {}).get("vision_model", "gemini-2.5-flash")
        self.max_tokens = config.get("gemini", {}).get("max_tokens", 8192)
        logger.info("✅ LONABAdapter initialisé avec Gemini Vision")

    def extract(self, pdf_path: str = None) -> dict:
        """
        Extrait les données du PDF LONAB.
        Si pdf_path est None, scrape et télécharge le PDF du jour.
        """
        if pdf_path is None:
            pdf_path = self._download_pdf()

        if not pdf_path or not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF LONAB introuvable : {pdf_path}")

        # Vérification taille
        file_size = Path(pdf_path).stat().st_size
        logger.info(f"📦 Taille du PDF : {file_size} octets")

        if file_size == 0:
            raise ValueError(f"Le PDF téléchargé est vide (0 octet) : {pdf_path}")

        # Vérification header PDF
        with open(pdf_path, "rb") as f:
            header = f.read(4)
        if header != b"%PDF":
            raise ValueError(
                f"Le fichier n'est pas un PDF valide (header détecté : {header!r}). "
                f"L'URL pointe peut-être vers une page HTML."
            )

        logger.info(f"📄 Extraction PDF : {pdf_path}")
        return self._extract_with_gemini(pdf_path)

    def _find_pdf_url_for_today(self) -> str:
        """
        Scrape la page des programmes LONAB et retourne
        l'URL du PDF correspondant à la date du jour.
        En cas d'échec, retourne le dernier PDF disponible.
        """
        today = date.today()
        today_str = today.strftime("%d/%m/%Y")  # format affiché sur le site
        today_day = today.strftime("%d")
        today_month = today.strftime("%m")
        today_year = today.strftime("%Y")

        logger.info(f"🔍 Recherche du PDF du jour ({today_str}) sur {LONAB_PROGRAMME_URL}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*",
        }

        try:
            response = requests.get(LONAB_PROGRAMME_URL, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Impossible de scraper la page LONAB : {e}")

        soup = BeautifulSoup(response.text, "html.parser")

        # Chercher tous les liens de téléchargement PDF
        pdf_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                full_url = href if href.startswith("http") else LONAB_BASE_URL + href
                pdf_links.append((a.get_text(strip=True), full_url))

        if not pdf_links:
            raise RuntimeError("Aucun lien PDF trouvé sur la page LONAB")

        logger.info(f"📋 {len(pdf_links)} PDF(s) trouvé(s) sur la page")

        # Chercher le PDF du jour (format dans le nom de fichier : DD-MM-YYYY)
        date_pattern = f"{today_day}-{today_month}-{today_year}"
        for label, url in pdf_links:
            if date_pattern in url:
                logger.info(f"✅ PDF du jour trouvé : {url}")
                return url

        # Fallback : prendre le premier (le plus récent)
        fallback_label, fallback_url = pdf_links[0]
        logger.warning(
            f"⚠️ PDF du {today_str} non trouvé — utilisation du plus récent : "
            f"'{fallback_label}' → {fallback_url}"
        )
        return fallback_url

    def _download_pdf(self) -> str:
        """Scrape la page LONAB et télécharge le PDF du jour."""
        save_path = "data/raw/programme_lonab.pdf"
        os.makedirs("data/raw", exist_ok=True)

        # Récupérer l'URL du PDF dynamiquement
        pdf_url = self._find_pdf_url_for_today()

        logger.info(f"⬇️ Téléchargement PDF : {pdf_url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/pdf,*/*",
            "Referer": LONAB_PROGRAMME_URL,
        }

        try:
            response = requests.get(pdf_url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Erreur HTTP lors du téléchargement du PDF : {e}")
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Impossible de joindre l'URL LONAB : {e}")
        except requests.exceptions.Timeout:
            raise RuntimeError("Timeout lors du téléchargement du PDF LONAB")

        content = response.content
        if not content:
            raise ValueError("Le contenu téléchargé est vide (réponse sans body)")

        with open(save_path, "wb") as f:
            f.write(content)

        file_size = Path(save_path).stat().st_size
        logger.info(f"✅ PDF téléchargé : {save_path} ({file_size} octets)")

        return save_path

    def _extract_with_gemini(self, pdf_path: str) -> dict:
        """Utilise Gemini Vision pour extraire les données du PDF."""
        try:
            uploaded_file = self.client.files.upload(
                file=pdf_path,
                config=types.UploadFileConfig(mime_type="application/pdf")
            )

            response = self.client.models.generate_content(
                model=self.vision_model,
                contents=[uploaded_file, self.EXTRACTION_PROMPT],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=self.max_tokens
                )
            )

            raw_text = response.text.strip()

            # Nettoyer les éventuels blocs markdown
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            data = json.loads(raw_text)
            self._enrich_data(data)

            logger.info(
                f"✅ Extraction réussie : {len(data.get('races', []))} courses, "
                f"{sum(len(r.get('horses', [])) for r in data.get('races', []))} chevaux"
            )
            return data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON Gemini : {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Erreur extraction Gemini : {e}")
            raise

    def _enrich_data(self, data: dict):
        """Ajoute des champs calculés à chaque cheval."""
        for race in data.get("races", []):
            for horse in race.get("horses", []):
                horse["form_score"] = self._compute_form_score(horse.get("form", ""))
                horse["race_number"] = race.get("race_number")
                horse["race_name"] = race.get("race_name")
                horse["distance"] = race.get("distance")
                horse["terrain"] = race.get("terrain")

    def _compute_form_score(self, form_str: str) -> float:
        """
        Calcule un score de forme (0-1) depuis la chaîne de résultats.
        Ex: "1-2-1-3-1" → score élevé
        """
        if not form_str:
            return 0.5

        scores = []
        for char in form_str.replace("-", "").replace(" ", ""):
            if char.isdigit():
                pos = int(char)
                if pos == 1:
                    scores.append(1.0)
                elif pos == 2:
                    scores.append(0.8)
                elif pos == 3:
                    scores.append(0.6)
                else:
                    scores.append(max(0.1, 1.0 - pos * 0.1))
            elif char == "0":
                scores.append(0.0)

        return round(sum(scores) / len(scores), 3) if scores else 0.5

    @property
    def horses(self) -> list:
        """Retourne la liste plate de tous les chevaux (toutes courses)."""
        return getattr(self, "_horses", [])
