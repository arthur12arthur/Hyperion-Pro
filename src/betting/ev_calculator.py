# ============================================================
# HYPERION PRO v1 — Calcul Expected Value (EV)
# src/betting/ev_calculator.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class EVCalculator:
    """
    Calcule la valeur esperee (Expected Value) de chaque pari.
    EV = (probabilite_victoire x cote) - 1
    Ne recommande que les paris EV positif au-dessus du seuil configure.
    """

    def __init__(self, config: dict):
        self.config = config
        self.min_ev = config.get("kelly", {}).get("min_ev", 0.05)
        logger.info(f"EVCalculator initialise — EV minimum : {self.min_ev:.0%}")

    def calculate(self, predictions: list) -> list:
        """
        Calcule l'EV pour chaque cheval valide.
        Retourne la liste enrichie avec ev et ev_positive.
        """
        results = []

        for horse in predictions:
            h = {**horse}

            # Probabilite de victoire finale
            prob = h.get("final_score") or h.get("mc_win_prob", 0.0)

            # Cote disponible
            odds = (
                h.get("live_odds", {}).get("odds") or
                h.get("odds_lonab") or
                2.0
            )

            # Calcul EV
            ev = (prob * odds) - 1.0
            h["ev"] = round(ev, 4)
            h["ev_positive"] = ev >= self.min_ev
            h["implied_prob"] = round(1.0 / odds, 4) if odds > 0 else 0
            h["edge"] = round(prob - h["implied_prob"], 4)

            results.append(h)

        n_positive = sum(1 for h in results if h.get("ev_positive"))
        logger.info(f"  EVCalculator : {n_positive}/{len(results)} paris EV positif")
        return results
