# ============================================================
# HYPERION PRO v1 — Double Validation
# src/models/double_validation.py
# ============================================================

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class DoubleValidator:
    """
    Valide chaque prediction en croisant Monte Carlo, ML et regles expertes.
    Le threshold MC est adaptatif selon le nombre de partants.
    """

    def __init__(self, config: dict):
        self.config = config
        self.min_agreement = config.get("ml_ensemble", {}).get("min_agreement", 2)
        logger.info(f"DoubleValidator initialise — accord minimum : {self.min_agreement} sources")

    def validate(self, mc_results: list, ml_results: dict, rule_results: dict) -> list:
        """
        Croise les 3 sources de prediction et enrichit chaque cheval.
        """
        # Compter les partants par course pour threshold adaptatif
        race_counts = defaultdict(int)
        for horse in mc_results:
            race_counts[horse.get("race_number", 0)] += 1

        validated = []

        for horse in mc_results:
            name = horse.get("horse_name", "")
            h = {**horse}

            ml  = ml_results.get(name, {})
            rul = rule_results.get(name, {})

            h["ml_win_prob"]   = ml.get("ml_win_prob", h.get("score_composite", 0.5))
            h["ml_confidence"] = ml.get("ml_confidence", 1)
            h["rule_score"]    = rul.get("rule_score", 0.5)
            h["rule_flags"]    = rul.get("rule_flags", [])

            # Score final combine
            h["final_score"] = round(
                h.get("mc_win_prob", 0.0) * 0.40 +
                h["ml_win_prob"]          * 0.35 +
                h["rule_score"]           * 0.25,
                4
            )

            # Threshold MC adaptatif selon nombre de partants
            n_runners = race_counts.get(horse.get("race_number", 0), 10)
            # Seuil = 80% de la probabilite theorique uniforme
            mc_threshold = (1.0 / n_runners) * 0.80

            # Threshold ML : score composite > 0.45 suffit
            ml_threshold = 0.45

            # Threshold regles : > 0.48
            rule_threshold = 0.48

            agreement = sum([
                h.get("mc_win_prob", 0) > mc_threshold,
                h["ml_win_prob"]        > ml_threshold,
                h["rule_score"]         > rule_threshold,
            ])

            h["sources_agreement"] = agreement
            h["mc_threshold_used"] = round(mc_threshold, 4)
            h["is_validated"] = agreement >= self.min_agreement

            if h["is_validated"]:
                logger.info(
                    f"  Valide : {name} | final={h['final_score']:.3f} | "
                    f"accord={agreement}/3 | mc_thresh={mc_threshold:.3f}"
                )

            validated.append(h)

        n_val = sum(1 for h in validated if h.get("is_validated"))
        logger.info(f"  DoubleValidator : {n_val}/{len(validated)} chevaux valides")
        return validated
            
