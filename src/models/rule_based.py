# ============================================================
# HYPERION PRO v1 — Regles expertes
# src/models/rule_based.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class RuleBasedModel:
    """Applique des regles expertes metier pour scorer chaque cheval."""

    def __init__(self, config: dict):
        self.config = config
        logger.info("RuleBasedModel initialise")

    def evaluate(self, horses: list, patterns: dict = None) -> dict:
        """
        Evalue chaque cheval selon les regles expertes.
        Retourne : horse_name -> {"rule_score": float, "rule_flags": list}
        """
        patterns = patterns or {}
        results = {}

        for horse in horses:
            name = horse.get("horse_name", "")
            score, flags = self._apply_rules(horse, patterns.get(name, []))
            results[name] = {
                "rule_score": round(score, 3),
                "rule_flags": flags
            }

        logger.info(f"  RuleBasedModel : {len(results)} chevaux evalues")
        return results

    def _apply_rules(self, horse: dict, patterns: list) -> tuple:
        score = 0.5
        flags = []

        # Regle 1 : Bonus patterns detectes
        bonus_map = {
            "TRIPLE_SIGNAL":      +0.20,
            "VALUE_BET_FORME":    +0.15,
            "JCURVE":             +0.12,
            "DISTANCE_SPECIALIST":+0.10,
            "HIGH_WIN_RATE":      +0.10,
        }
        for p in patterns:
            bonus = bonus_map.get(p, 0)
            score += bonus
            if bonus > 0:
                flags.append(f"+{p}")

        # Regle 2 : Penalite poids excessif
        weight_penalty = horse.get("feature_weight_penalty", 0)
        if weight_penalty < 0:
            score += weight_penalty
            flags.append("POIDS_ELEVE")

        # Regle 3 : Bonus age optimal
        age_factor = horse.get("feature_age_factor", 0)
        if age_factor > 0:
            score += age_factor
            flags.append("AGE_OPTIMAL")

        # Regle 4 : Penalite si pas de donnees historiques
        if not horse.get("web_data"):
            score -= 0.05
            flags.append("PAS_HISTORIQUE")

        # Regle 5 : Bonus si expert pronostic favorable
        expert = horse.get("web_data", {}).get("expert_pronostic", "")
        if expert == "favori":
            score += 0.10
            flags.append("EXPERT_FAVORI")
        elif expert == "outsider":
            score += 0.05
            flags.append("EXPERT_OUTSIDER")

        return min(max(score, 0.0), 1.0), flags
