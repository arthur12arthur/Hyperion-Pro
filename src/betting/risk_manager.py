# ============================================================
# HYPERION PRO v1 — Gestionnaire de risque
# src/betting/risk_manager.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Applique les limites de risque sur les mises calculees par Kelly.
    Protege la bankroll a tout moment.
    """

    def __init__(self, config: dict):
        self.config = config
        kelly_cfg = config.get("kelly", {})
        self.max_bet_pct    = kelly_cfg.get("max_bet_pct", 0.05)
        self.max_bets_day   = 5
        self.max_exposure   = 0.15  # Max 15% de la bankroll par jour
        logger.info("RiskManager initialise")

    def apply(self, bets: list) -> list:
        """
        Filtre et ajuste les mises selon les regles de gestion du risque.
        """
        if not bets:
            return []

        # Charger la bankroll
        bankroll = self._load_bankroll()

        # Filtrer uniquement les paris EV positif et valides
        eligible = [
            b for b in bets
            if b.get("ev_positive") and b.get("is_validated")
            and b.get("hades_status") != "blocked"
        ]

        # Trier par priorite et EV decroissant
        eligible.sort(key=lambda x: (
            x.get("priority", "BASSE") == "HAUTE",
            x.get("ev", 0)
        ), reverse=True)

        # Limiter le nombre de paris par jour
        eligible = eligible[:self.max_bets_day]

        # Verifier l'exposition totale
        total_exposure = sum(b.get("bet_amount", 0) for b in eligible)
        max_allowed = bankroll * self.max_exposure

        if total_exposure > max_allowed:
            scale = max_allowed / total_exposure
            for b in eligible:
                b["bet_amount"] = round(b["bet_amount"] * scale, 2)
                b["bet_amount_adjusted"] = True
            logger.info(f"  RiskManager : mises reduites (exposition max atteinte)")

        logger.info(
            f"  RiskManager : {len(eligible)} paris approuves | "
            f"exposition={sum(b.get('bet_amount',0) for b in eligible):.0f} FCFA"
        )
        return eligible

    def _load_bankroll(self) -> float:
        try:
            with open("data/bankroll.txt") as f:
                return float(f.read().strip())
        except Exception:
            return 50000.0
