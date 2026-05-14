# ============================================================
# HYPERION PRO v1 — Detection de patterns
# src/features/patterns.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class PatternDetector:
    """Detecte les configurations historiquement gagnantes."""

    def __init__(self, config: dict):
        self.config = config
        logger.info("PatternDetector initialise")

    def detect(self, horses: list) -> dict:
        """
        Detecte les patterns pour tous les chevaux.
        Retourne un dict horse_name -> liste de patterns detectes.
        """
        patterns = {}
        for horse in horses:
            name = horse.get("horse_name", "")
            detected = self._detect_horse_patterns(horse)
            if detected:
                patterns[name] = detected
                logger.info(f"  Pattern detecte pour {name} : {detected}")
        return patterns

    def _detect_horse_patterns(self, horse: dict) -> list:
        found = []

        # Pattern 1 : Tous les signaux alignes (forme + cotes + jockey)
        if (horse.get("score_forme", 0) > 0.7 and
                horse.get("score_cotes", 0) > 0.6 and
                horse.get("score_jockey", 0) > 0.6):
            found.append("TRIPLE_SIGNAL")

        # Pattern 2 : Value bet (cote en baisse + bonne forme)
        signal = horse.get("live_odds", {}).get("signal", "neutral")
        if signal == "value_bet" and horse.get("score_forme", 0) > 0.6:
            found.append("VALUE_BET_FORME")

        # Pattern 3 : J-curve confirmee
        if horse.get("feature_jcurve", 0) > 0.10:
            found.append("JCURVE")

        # Pattern 4 : Specialiste de la distance
        if horse.get("feature_distance_fit", 0) >= 0.15:
            found.append("DISTANCE_SPECIALIST")

        # Pattern 5 : Cheval en pleine forme (win_rate > 30%)
        win_rate = horse.get("web_data", {}).get("win_rate", 0) or 0
        if win_rate > 0.30:
            found.append("HIGH_WIN_RATE")

        return found
