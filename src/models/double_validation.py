# ============================================================
# HYPERION PRO v1 — Double Validation
# src/models/double_validation.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class DoubleValidator:
    """
    Valide chaque prediction en croisant Monte Carlo, ML et regles expertes.
    Un pronostic n'est emis que si au moins 2 sources sont en accord.
    """

    def __init__(self, config: dict):
        self.config = config
        self.min_agreement = config.get("ml_ensemble", {}).get("min_agreement", 2)
        logger.info(f"DoubleValidator initialise — accord minimum : {self.min_agreement} sources")

    def validate(self, mc_results: list, ml_results: dict, rule_results: dict) -> list:
        """
        Croise les 3 sources de prediction et enrichit chaque cheval.
        Retourne la liste complete avec scores combines et flag de validation.
        """
        validated = []

        for horse in mc_results:
            name = horse.get("horse_name", "")
            h = {**horse}

            ml  = ml_results.get(name, {})
            rul = rule_results.get(name, {})

            # Injecter les scores ML et regles
            h["ml_win_prob"]  = ml.get("ml_win_prob", h.get("score_composite", 0.5))
            h["ml_confidence"]= ml.get("ml_confidence", 1)
            h["rule_score"]   = rul.get("rule_score", 0.5)
            h["rule_flags"]   = rul.get("rule_flags", [])

            # Score final combine (MC + ML + Regles)
            h["final_score"] = round(
                h.get("mc_win_prob", 0.0) * 0.40 +
                h["ml_win_prob"]          * 0.35 +
                h["rule_score"]           * 0.25,
                4
            )

            # Compter les sources en accord (score > seuil)
            threshold = 0.15
            agreement = sum([
                h.get("mc_win_prob", 0)  > threshold,
                h["ml_win_prob"]         > threshold,
                h["rule_score"]          > 0.55,
            ])

            h["sources_agreement"] = agreement
            h["is_validated"] = agreement >= self.min_agreement

            if h["is_validated"]:
                logger.info(
                    f"  Valide : {name} | final={h['final_score']:.3f} | "
                    f"accord={agreement}/3"
                )

            validated.append(h)

        n_val = sum(1 for h in validated if h.get("is_validated"))
        logger.info(f"  DoubleValidator : {n_val}/{len(validated)} chevaux valides")
        return validated
