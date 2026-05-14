# ============================================================
# HYPERION PRO v1 — HADES : Système Anti-Pièges
# src/hades/detector.py
# ============================================================

import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class HADESDetector:
    """
    HADES — Hyperion Anomaly Detection & Expert System.
    Filtre les prédictions en détectant :
    - Favoris suspects, anomalies de marché, courses incertaines
    - Chevaux avec données insuffisantes
    Chaque cheval reçoit un statut : clear / warning / blocked
    """

    def __init__(self, config: dict):
        self.config = config
        hades_cfg = config.get("hades", {})
        self.odds_drop_threshold  = hades_cfg.get("odds_drop_threshold", 0.30)
        self.odds_spike_threshold = hades_cfg.get("odds_spike_threshold", 0.50)
        self.min_runners          = hades_cfg.get("min_runners", 5)
        self.max_uncertainty      = hades_cfg.get("max_uncertainty_score", 0.75)
        self.min_confidence       = config.get("pipeline", {}).get("min_confidence_score", 2)
        logger.info("✅ HADES initialisé")

    def filter(self, predictions: list, live_odds: dict = None) -> list:
        races = defaultdict(list)
        for horse in predictions:
            races[horse.get("race_number", 0)].append(horse)

        filtered = []
        for race_num, race_horses in races.items():

            # Filtre 1 : Trop peu de partants
            if len(race_horses) < self.min_runners:
                logger.warning(f"  HADES R{race_num} : {len(race_horses)} partants -> ignoree")
                for h in race_horses:
                    h["hades_status"] = "blocked"
                    h["hades_reason"] = f"Trop peu de partants ({len(race_horses)})"
                filtered.extend(race_horses)
                continue

            # Filtre 2 : Incertitude de la course
            uncertainty = self._compute_uncertainty(race_horses)
            if uncertainty > self.max_uncertainty:
                for h in race_horses:
                    h.setdefault("hades_status", "warning")
                    h["hades_uncertainty"] = uncertainty

            # Filtres individuels
            for horse in race_horses:
                self._apply_horse_filters(horse, live_odds or {})

            filtered.extend(race_horses)

        n_blocked = sum(1 for h in filtered if h.get("hades_status") == "blocked")
        n_warning = sum(1 for h in filtered if h.get("hades_status") == "warning")
        n_clear   = sum(1 for h in filtered if h.get("hades_status") == "clear")
        logger.info(f"  HADES : {n_clear} clear | {n_warning} warning | {n_blocked} blocked")
        return filtered

    def _apply_horse_filters(self, horse: dict, live_odds: dict):
        if horse.get("hades_status") == "blocked":
            return

        reasons = []
        status = horse.get("hades_status", "clear")

        mc_conf = horse.get("mc_confidence", 1)
        if mc_conf < self.min_confidence:
            reasons.append(f"Confiance MC insuffisante (etoiles={mc_conf})")
            status = "warning"

        coverage = horse.get("data_coverage", 1.0)
        if coverage < 0.3:
            reasons.append(f"Donnees insuffisantes ({coverage:.0%})")
            status = "warning"

        name = horse.get("horse_name", "")
        odds_data = live_odds.get(name, {})
        variation = odds_data.get("variation", 0.0)
        signal    = odds_data.get("signal", "neutral")

        if signal == "market_alert":
            reasons.append(f"Anomalie cotes : {variation*100:+.1f}%")
            status = "warning"

        if variation <= -self.odds_drop_threshold:
            reasons.append(f"Cote en forte baisse ({variation*100:.1f}%)")
            if status == "clear":
                status = "warning"

        odds_val = odds_data.get("odds") or horse.get("odds_lonab", 99)
        if odds_val and odds_val < 1.5 and coverage < 0.5:
            reasons.append(f"Favori suspect : cote={odds_val} + donnees faibles")
            status = "blocked"

        composite = horse.get("score_composite", 0.5)
        if composite < 0.25:
            reasons.append(f"Score composite trop faible ({composite:.2f})")
            status = "blocked"

        horse["hades_status"] = status
        horse["hades_reasons"] = reasons
        horse["hades_score"] = self._compute_hades_score(horse, variation, coverage)

    def _compute_uncertainty(self, race_horses: list) -> float:
        probs = [h.get("mc_win_prob", 0) for h in race_horses if h.get("mc_win_prob", 0) > 0]
        if not probs:
            return 1.0
        probs_arr = np.array(probs) / sum(probs)
        entropy = -np.sum(probs_arr * np.log2(probs_arr + 1e-10))
        max_entropy = np.log2(len(probs_arr))
        return round(entropy / max_entropy if max_entropy > 0 else 1.0, 3)

    def _compute_hades_score(self, horse: dict, variation: float, coverage: float) -> float:
        score = 1.0
        score -= abs(variation) * 0.3
        score -= (1 - coverage) * 0.2
        score -= (3 - horse.get("mc_confidence", 2)) * 0.15
        return round(max(0.0, min(1.0, score)), 3)

    def get_clear_horses(self, predictions: list) -> list:
        return [h for h in predictions if h.get("hades_status") == "clear"]

    def get_warnings(self, predictions: list) -> list:
        return [h for h in predictions if h.get("hades_status") == "warning"]

    def get_blocked_horses(self, predictions: list) -> list:
        return [h for h in predictions if h.get("hades_status") == "blocked"]
