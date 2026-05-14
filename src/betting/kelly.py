# ============================================================
# HYPERION PRO v1 — Critere de Kelly Adaptatif
# src/betting/kelly.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class KellyCriterion:
    """
    Calcule la mise optimale selon le critere de Kelly fractionnel.
    Adapte la fraction selon le niveau de confiance HADES + MC.
    Ne recommande un pari que si EV > seuil minimum configure.
    """

    def __init__(self, config: dict):
        betting_cfg = config.get("kelly", {})
        self.fraction      = betting_cfg.get("fraction", 0.25)
        self.max_bet_pct   = betting_cfg.get("max_bet_pct", 0.05)
        self.min_ev        = betting_cfg.get("min_ev", 0.05)
        self.bankroll      = self._load_bankroll()
        logger.info(
            f"Kelly init : fraction={self.fraction} | "
            f"max_bet={self.max_bet_pct:.0%} | bankroll={self.bankroll}"
        )

    def compute(self, ev_scores: list) -> list:
        """
        Calcule les mises Kelly pour chaque pari avec EV positif.
        Retourne la liste enrichie avec : kelly_fraction, bet_amount, recommendation
        """
        bets = []
        for horse in ev_scores:
            if horse.get("hades_status") == "blocked":
                continue

            ev = horse.get("ev", 0.0)
            if ev < self.min_ev:
                continue

            bet = self._compute_horse_bet(horse)
            if bet:
                bets.append(bet)

        bets.sort(key=lambda x: x.get("ev", 0), reverse=True)
        logger.info(f"  Kelly : {len(bets)} paris recommandes")
        return bets

    def _compute_horse_bet(self, horse: dict) -> dict:
        """Calcule la mise Kelly pour un cheval specifique."""
        prob   = horse.get("mc_win_prob", 0.0)
        odds   = horse.get("live_odds", {}).get("odds") or horse.get("odds_lonab", 2.0)
        ev     = horse.get("ev", 0.0)

        if prob <= 0 or odds <= 1.0:
            return None

        # Formule Kelly : f = (b*p - q) / b
        b = odds - 1.0   # profit net si gagnant
        q = 1.0 - prob   # probabilite de perdre
        kelly_f = (b * prob - q) / b

        if kelly_f <= 0:
            return None

        # Appliquer la fraction adaptative selon confiance
        adaptive_fraction = self._adaptive_fraction(horse)
        final_fraction = kelly_f * adaptive_fraction

        # Plafonner a max_bet_pct de la bankroll
        final_fraction = min(final_fraction, self.max_bet_pct)

        bet_amount = round(self.bankroll * final_fraction, 2)

        if bet_amount < 100:  # Mise minimum 100 FCFA
            return None

        stars = horse.get("mc_confidence", 1)
        star_str = "⭐" * stars

        return {
            **horse,
            "kelly_raw":    round(kelly_f, 4),
            "kelly_final":  round(final_fraction, 4),
            "bet_amount":   bet_amount,
            "bet_pct":      round(final_fraction * 100, 2),
            "recommendation": self._build_recommendation(horse, bet_amount, stars, star_str),
            "confidence_stars": stars,
            "priority": self._priority(ev, stars),
        }

    def _adaptive_fraction(self, horse: dict) -> float:
        """
        Adapte la fraction Kelly selon la confiance.
        3 etoiles = fraction pleine | 2 etoiles = 60% | 1 etoile = 30%
        """
        confidence = horse.get("mc_confidence", 1)
        hades      = horse.get("hades_status", "clear")

        fraction = self.fraction

        if confidence == 3:
            fraction *= 1.0
        elif confidence == 2:
            fraction *= 0.60
        else:
            fraction *= 0.30

        if hades == "warning":
            fraction *= 0.50

        return fraction

    def _build_recommendation(
        self, horse: dict, amount: float, stars: int, star_str: str
    ) -> str:
        name  = horse.get("horse_name", "?")
        race  = horse.get("race_number", "?")
        odds  = horse.get("live_odds", {}).get("odds") or horse.get("odds_lonab", "?")
        prob  = horse.get("mc_win_prob", 0)
        ev    = horse.get("ev", 0)
        return (
            f"{star_str} R{race} - {name} | "
            f"Cote: {odds} | Prob: {prob:.1%} | "
            f"EV: +{ev:.1%} | Mise: {amount:.0f} FCFA"
        )

    def _priority(self, ev: float, stars: int) -> str:
        if ev >= 0.20 and stars == 3:
            return "HAUTE"
        elif ev >= 0.10 or stars >= 2:
            return "MOYENNE"
        else:
            return "BASSE"

    def _load_bankroll(self) -> float:
        """Charge la bankroll depuis le fichier de suivi."""
        try:
            with open("data/bankroll.txt", "r") as f:
                return float(f.read().strip())
        except Exception:
            return 50000.0  # Bankroll par defaut : 50 000 FCFA

    def save_bankroll(self, new_amount: float):
        """Sauvegarde la bankroll mise a jour."""
        import os
        os.makedirs("data", exist_ok=True)
        with open("data/bankroll.txt", "w") as f:
            f.write(str(new_amount))
        self.bankroll = new_amount
        logger.info(f"  Bankroll mise a jour : {new_amount:.0f} FCFA")
