# ============================================================
# HYPERION PRO v1 — Feature Engineering
# src/features/engineer.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Calcule les features predictives pour chaque cheval."""

    def __init__(self, config: dict):
        self.config = config
        logger.info("FeatureEngineer initialise")

    def compute(self, fused_horses: list) -> list:
        """Enrichit chaque cheval avec des features calculees."""
        enriched = []
        for horse in fused_horses:
            try:
                h = {**horse}
                h["feature_weight_penalty"] = self._weight_penalty(h)
                h["feature_age_factor"]     = self._age_factor(h)
                h["feature_distance_fit"]   = self._distance_fit(h)
                h["feature_jcurve"]         = self._jcurve(h)
                enriched.append(h)
            except Exception as e:
                logger.warning(f"Feature engineering echoue pour {horse.get('horse_name')}: {e}")
                enriched.append(horse)

        logger.info(f"  FeatureEngineer : {len(enriched)} chevaux enrichis")
        return enriched

    def _weight_penalty(self, horse: dict) -> float:
        """Penalite si le cheval porte un poids eleve."""
        weight = horse.get("weight", 56)
        if weight is None:
            return 0.0
        if weight > 60:
            return -0.15
        elif weight > 58:
            return -0.05
        return 0.0

    def _age_factor(self, horse: dict) -> float:
        """Score age : les chevaux de 4-6 ans sont generalement au pic."""
        age = horse.get("age", 5)
        if age is None:
            return 0.0
        if 4 <= age <= 6:
            return 0.10
        elif age == 3 or age == 7:
            return 0.0
        return -0.10

    def _distance_fit(self, horse: dict) -> float:
        """Adequation distance course vs distance preferee du cheval."""
        best = horse.get("web_data", {}).get("best_distance")
        race_dist = horse.get("distance")
        if not best or not race_dist:
            return 0.0
        diff = abs(best - race_dist)
        if diff <= 100:
            return 0.15
        elif diff <= 300:
            return 0.05
        elif diff > 600:
            return -0.10
        return 0.0

    def _jcurve(self, horse: dict) -> float:
        """
        Detecte la J-curve : cheval en progression apres une baisse.
        Signal positif si les 2 derniers resultats sont meilleurs que les precedents.
        """
        last_races = horse.get("web_data", {}).get("last_races", [])
        if len(last_races) < 4:
            return 0.0
        recent = [r.get("position", 10) for r in last_races[:2]]
        older  = [r.get("position", 10) for r in last_races[2:4]]
        if sum(recent) < sum(older):
            return 0.12  # En progression
        return 0.0
