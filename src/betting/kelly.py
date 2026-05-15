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
    """

    def __init__(self, config: dict):
        betting_cfg = config.get("kelly", {})
        self.fraction    = betting_cfg.get("fraction", 0.25)
        self.max_bet_pct = betting_cfg.get("max_bet_pct", 0.05)
        self.min_ev      = betting_cfg.get("min_ev", 0.05)
        self.bankroll    = self._load_bankroll()
        logger.info(
            f"Kelly init : fraction={self.fraction} | "
            f"max_bet={self.max_bet_pct:.0%} | bankroll={self.bankroll}"
        )

    def compute(self, ev_scores: list) -> list:
        """
        Calcule les mises Kelly pour chaque pari avec EV positif.
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
        prob = horse.get("final_score") or horse.get("mc_win_prob", 0.0)

        # Recuperer la cote — fallback intelligent si manquante
        odds = (
            horse.get("live_odds", {}).get("odds")
            or horse.get("odds_lonab")
            or self._estimate_fair_odds(horse)
        )

        try:
            odds = float(odds)
        except (TypeError, ValueError):
            odds = self._estimate_fair_odds(horse)

        if prob <= 0 or odds <= 1.0:
            return None

        # Formule Kelly : f* = (b*p - q) / b
        b = odds - 1.0
        q = 1.0 - prob
        kelly_f = (b * prob - q) / b

        if kelly_f <= 0:
            return None

        # Fraction adaptative selon confiance
        adaptive_fraction = self._adaptive_fraction(horse)
        final_fraction = kelly_f * adaptive_fraction

        # Plafonner a max_bet_pct
        final_fraction = min(final_fraction, self.max_bet_pct)

        bet_amount = round(self.bankroll * final_fraction, 2)

        # Mise minimum 50 FCFA
        if bet_amount < 50:
            return None

        stars = horse.get("mc_confidence", 1)
        star_str = "⭐" * stars

        return {
            **horse,
            "kelly_raw":         round(kelly_f, 4),
            "kelly_final":       round(final_fraction, 4),
            "bet_amount":        bet_amount,
            "bet_pct":           round(final_fraction * 100, 2),
            "odds_used":         odds,
            "recommendation":    self._build_recommendation(horse, bet_amount, stars, star_str, odds),
            "confidence_stars":  stars,
            "priority":          self._priority(horse.get("ev", 0), stars),
        }

    def _estimate_fair_odds(self, horse: dict) -> float:
        """
        Estime une cote equitable si non disponible.
        Basee sur la probabilite MC : fair_odds = 1 / mc_win_prob
        avec une marge de 15% pour le bookmaker.
        """
        mc_prob = horse.get("mc_win_prob", 0.0)
        if mc_prob and mc_prob > 0.01:
            # Cote fair avec marge bookmaker de 15%
            fair = (1.0 / mc_prob) * 0.85
            return round(max(fair, 1.10), 2)
        # Fallback : cote neutre de 3.5
        return 3.5

    def _adaptive_fraction(self, horse: dict) -> float:
        """
        Adapte la fraction Kelly selon la confiance.
        3 etoiles = fraction pleine
        2 etoiles = 60%
        1 etoile  = 40% (releve de 30% a 40%)
        warning   = 70% (releve de 50% a 70%)
        """
        confidence = horse.get("mc_confidence", 1)
        hades      = horse.get("hades_status", "clear")

        fraction = self.fraction

        if confidence == 3:
            fraction *= 1.00
        elif confidence == 2:
            fraction *= 0.60
        else:
            fraction *= 0.40  # 1 etoile — releve

        if hades == "warning":
            fraction *= 0.70  # warning — releve

        return fraction

    def _build_recommendation(self, horse, amount, stars, star_str, odds) -> str:
        name  = horse.get("horse_name", "?")
        race  = horse.get("race_number", "?")
        prob  = horse.get("final_score", horse.get("mc_win_prob", 0))
        ev    = horse.get("ev", 0)
        src   = "(estimee)" if not horse.get("odds_lonab") else ""
        return (
            f"{star_str} R{race} - {name} | "
            f"Cote: {odds}{src} | Prob: {prob:.1%} | "
            f"EV: +{ev:.1%} | Mise: {amount:.0f} FCFA"
        )

    def _priority(self, ev: float, stars: int) -> str:
        if ev >= 0.20 and stars == 3:
            return "HAUTE"
        elif ev >= 0.10 or stars >= 2:
            return "MOYENNE"
        return "BASSE"

    def _load_bankroll(self) -> float:
        try:
            with open("data/bankroll.txt") as f:
                return float(f.read().strip())
        except Exception:
            return 50000.0

    def save_bankroll(self, new_amount: float):
        import os
        os.makedirs("data", exist_ok=True)
        with open("data/bankroll.txt", "w") as f:
            f.write(str(new_amount))
        self.bankroll = new_amount
        logger.info(f"  Bankroll mise a jour : {new_amount:.0f} FCFA")
