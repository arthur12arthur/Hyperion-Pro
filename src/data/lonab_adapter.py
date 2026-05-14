# ============================================================
# HYPERION PRO v1 — Adaptateur LONAB (PDF → Data)
# src/data/lonab_adapter.py
# ============================================================

import os
import json
import logging
import requests
from pathlib import Path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


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
        Si pdf_path est None, télécharge depuis l'URL configurée.
        """
        if pdf_path is None:
            pdf_path = self._download_pdf()

        if not pdf_path or not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF LONAB introuvable : {pdf_path}")

        logger.info(f"📄 Extraction PDF : {pdf_path}")
        return self._extract_with_gemini(pdf_path)

    def _download_pdf(self) -> str:
        """Télécharge le PDF depuis l'URL LONAB configurée."""
        url = os.getenv("LONAB_PDF_URL")
        if not url:
            raise ValueError("LONAB_PDF_URL manquant dans les variables d'environnement")

        save_path = "data/raw/programme_lonab.pdf"
        os.makedirs("data/raw", exist_ok=True)

        logger.info(f"⬇️ Téléchargement PDF : {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(save_path, "wb") as f:
            f.write(response.content)

        logger.info(f"✅ PDF téléchargé : {save_path}")
        return save_path

    def _extract_with_gemini(self, pdf_path: str) -> dict:
        """Utilise Gemini Vision pour extraire les données du PDF."""
        try:
            # Upload du PDF vers Gemini
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
