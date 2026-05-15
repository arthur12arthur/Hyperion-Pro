# ============================================================
# HYPERION PRO v1 — Gestionnaire de risque
# src/betting/risk_manager.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Applique les limites de risque sur les mises calculees par Kelly.
    - clear   : mise normale
    - warning : mise reduite de 30% (releve de 50%)
    - blocked : exclus
    """

    def __init__(self, config: dict):
        self.config      = config
        kelly_cfg        = config.get("kelly", {})
        self.max_bet_pct  = kelly_cfg.get("max_bet_pct", 0.05)
        self.max_bets_day = 5
        self.max_exposure = 0.20     # Max 20% bankroll/jour
        self.warning_ratio = 0.70    # Mise a 70% pour les warnings
        self.min_bet      = 50.0     # Mise minimum 50 FCFA
        logger.info("RiskManager initialise")

    def apply(self, bets: list) -> list:
        if not bets:
            return []

        bankroll = self._load_bankroll()

        # Accepter : ev_positive + non blocked + (valide OU warning)
        eligible = [
            b for b in bets
            if b.get("ev_positive")
            and b.get("hades_status") != "blocked"
        ]

        if not eligible:
            logger.info("  RiskManager : aucun pari eligible")
            return []

        # Reduire la mise pour les warnings
        for b in eligible:
            if b.get("hades_status") == "warning":
                b["bet_amount"] = round(b.get("bet_amount", 0) * self.warning_ratio, 2)
                b["bet_warning_reduced"] = True

        # Trier : clear avant warning, puis par EV decroissant
        eligible.sort(key=lambda x: (
            x.get("hades_status") == "clear",
            x.get("ev", 0)
        ), reverse=True)

        # Limiter le nombre de paris
        eligible = eligible[:self.max_bets_day]

        # Verifier exposition totale
        total_exposure = sum(b.get("bet_amount", 0) for b in eligible)
        max_allowed = bankroll * self.max_exposure

        if total_exposure > max_allowed and total_exposure > 0:
            scale = max_allowed / total_exposure
            for b in eligible:
                b["bet_amount"] = round(b["bet_amount"] * scale, 2)
                b["bet_amount_adjusted"] = True
            logger.info("  RiskManager : mises reduites (exposition max atteinte)")

        # Filtrer mise minimum
        eligible = [b for b in eligible if b.get("bet_amount", 0) >= self.min_bet]

        logger.info(
            f"  RiskManager : {len(eligible)} paris approuves | "
            f"exposition={sum(b.get('bet_amount', 0) for b in eligible):.0f} FCFA"
        )
        return eligible

    def _load_bankroll(self) -> float:
        try:
            with open("data/bankroll.txt") as f:
                return float(f.read().strip())
        except Exception:
            return 50000.0
