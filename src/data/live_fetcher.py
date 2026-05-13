# ============================================================
# HYPERION PRO v1 — Récupérateur de cotes en temps réel
# src/data/live_fetcher.py
# ============================================================

import logging
import time
import random
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LiveFetcher:
    """
    Récupère les cotes en temps réel depuis les sources web configurées.
    Détecte les variations significatives (signaux de valeur ou manipulation).
    """

    def __init__(self, config: dict):
        self.config = config
        self.ua = UserAgent()
        self.sources = config.get("sources", {}).get("lonab", {}).get("odds", [])
        self.odds_history = {}  # horse_name → [cote_t0, cote_t1, ...]
        logger.info(f"✅ LiveFetcher initialisé — {len(self.sources)} sources configurées")

    def fetch(self, horses: list) -> dict:
        """
        Récupère les cotes live pour une liste de chevaux.
        Retourne un dict : horse_name → {odds, variation, signal}
        """
        live_odds = {}

        for horse in horses:
            name = horse.get("horse_name", "")
            if not name:
                continue

            try:
                odds_data = self._fetch_horse_odds(name, horse.get("race_number"))
                if odds_data:
                    live_odds[name] = odds_data
                    self._update_history(name, odds_data["odds"])

                # Pause courte pour éviter le bannissement
                time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                logger.warning(f"  ⚠️ Impossible de récupérer cotes pour {name} : {e}")
                # Fallback sur la cote LONAB officielle
                if horse.get("odds_lonab"):
                    live_odds[name] = {
                        "odds": horse["odds_lonab"],
                        "variation": 0.0,
                        "signal": "neutral",
                        "source": "lonab_fallback"
                    }

        logger.info(f"  📊 Cotes récupérées : {len(live_odds)}/{len(horses)} chevaux")
        return live_odds

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_horse_odds(self, horse_name: str, race_number: int = None) -> dict:
        """
        Tente de récupérer la cote d'un cheval depuis les sources actives.
        Utilise plusieurs sources et retourne la moyenne pondérée.
        """
        odds_collected = []

        for source in self.sources:
            if not source.get("enabled", False):
                continue

            try:
                odds = self._scrape_source(source["url"], horse_name, race_number)
                if odds:
                    odds_collected.append({
                        "odds": odds,
                        "weight": source.get("weight", 1.0),
                        "source": source["name"]
                    })
            except Exception:
                pass

        if not odds_collected:
            return None

        # Moyenne pondérée
        total_weight = sum(o["weight"] for o in odds_collected)
        weighted_odds = sum(o["odds"] * o["weight"] for o in odds_collected) / total_weight

        # Calcul variation par rapport à l'historique
        variation = self._compute_variation(horse_name, weighted_odds)
        signal = self._interpret_signal(variation)

        return {
            "odds": round(weighted_odds, 2),
            "variation": round(variation, 3),
            "signal": signal,
            "source": odds_collected[0]["source"] if len(odds_collected) == 1 else "multi",
            "sources_count": len(odds_collected)
        }

    def _scrape_source(self, base_url: str, horse_name: str, race_number: int) -> float:
        """
        Scrape une source web pour trouver la cote d'un cheval.
        Retourne la cote (float) ou None si non trouvé.
        """
        headers = {"User-Agent": self.ua.random}

        # Recherche par nom de cheval
        search_url = f"{base_url}/search?q={horse_name.replace(' ', '+')}"

        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Patterns de scraping communs pour les sites de courses
        odds_selectors = [
            ".cote", ".odds", ".ratio", "[data-odds]",
            ".partant-cote", ".horse-odds", ".bet-odds"
        ]

        for selector in odds_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                try:
                    odds_val = float(text.replace(",", "."))
                    if 1.0 < odds_val < 500.0:  # Validation plage réaliste
                        return odds_val
                except ValueError:
                    continue

        return None

    def _update_history(self, horse_name: str, current_odds: float):
        """Met à jour l'historique des cotes pour un cheval."""
        if horse_name not in self.odds_history:
            self.odds_history[horse_name] = []
        self.odds_history[horse_name].append(current_odds)
        # Garder seulement les 10 dernières valeurs
        self.odds_history[horse_name] = self.odds_history[horse_name][-10:]

    def _compute_variation(self, horse_name: str, current_odds: float) -> float:
        """
        Calcule la variation de cote par rapport à la première valeur connue.
        Variation positive = cote monte (cheval moins joué)
        Variation négative = cote descend (cheval plus joué)
        """
        history = self.odds_history.get(horse_name, [])
        if len(history) < 2:
            return 0.0

        first_odds = history[0]
        if first_odds == 0:
            return 0.0

        return (current_odds - first_odds) / first_odds

    def _interpret_signal(self, variation: float) -> str:
        """
        Interprète la variation de cote en signal.
        """
        drop_threshold = self.config.get("hades", {}).get("odds_drop_threshold", 0.30)
        spike_threshold = self.config.get("hades", {}).get("odds_spike_threshold", 0.50)

        if variation <= -drop_threshold:
            return "value_bet"         # Cote en forte baisse = cheval très joué = possible valeur
        elif variation >= spike_threshold:
            return "market_alert"      # Cote en forte hausse = anomalie à investiguer
        elif variation < -0.10:
            return "positive"          # Légère baisse = tendance favorable
        elif variation > 0.10:
            return "caution"           # Légère hausse = prudence
        else:
            return "neutral"

    def get_odds_movement_report(self) -> list:
        """
        Retourne un rapport des mouvements de cotes significatifs.
        Utilisé par HADES pour détecter les anomalies.
        """
        alerts = []
        for horse_name, history in self.odds_history.items():
            if len(history) >= 2:
                variation = (history[-1] - history[0]) / history[0]
                if abs(variation) >= 0.15:
                    alerts.append({
                        "horse": horse_name,
                        "initial_odds": history[0],
                        "current_odds": history[-1],
                        "variation_pct": round(variation * 100, 1),
                        "signal": self._interpret_signal(variation)
                    })
        return sorted(alerts, key=lambda x: abs(x["variation_pct"]), reverse=True)
