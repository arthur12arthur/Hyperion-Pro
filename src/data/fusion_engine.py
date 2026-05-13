# ============================================================
# HYPERION PRO v1 — Moteur de Fusion Multi-Sources
# src/data/fusion_engine.py
# ============================================================

import logging
import numpy as np
from typing import dict as Dict

logger = logging.getLogger(__name__)


class FusionEngine:
    """
    Fusionne les données de toutes les sources (PDF, web, cotes, sentiment)
    en un dataset unifié et pondéré par cheval.
    Produit un score composite pré-prédiction.
    """

    # Poids par type de source
    SOURCE_WEIGHTS = {
        "official_pdf":      1.00,  # Données LONAB officielles
        "live_odds":         0.90,  # Cotes en temps réel
        "historical_data":   0.85,  # Historique performances
        "expert_pronostics": 0.70,  # Pronostics experts
        "jockey_stats":      0.75,  # Stats jockey
        "sentiment":         0.40,  # Sentiment social
        "gemini_knowledge":  0.40,  # Connaissance Gemini
        "lonab_fallback":    0.60,  # Cote LONAB seule
    }

    def __init__(self, config: dict):
        self.config = config
        weights_cfg = config.get("sources", {}).get("source_weights", {})
        # Surcharger les poids par défaut avec la config
        self.SOURCE_WEIGHTS.update(weights_cfg)
        logger.info("✅ FusionEngine initialisé")

    def fuse(self, merged_data: dict) -> list:
        """
        Fusionne les données mergées en une liste de chevaux enrichis.
        Chaque cheval reçoit un score_composite et des scores par dimension.
        """
        fused_horses = []

        for race in merged_data.get("races", []):
            for horse in race.get("horses", []):
                try:
                    fused = self._fuse_horse(horse, race)
                    fused_horses.append(fused)
                except Exception as e:
                    logger.warning(f"  ⚠️ Fusion échouée pour {horse.get('horse_name')}: {e}")
                    fused_horses.append(horse)  # Garder les données brutes

        logger.info(f"  ✅ Fusion : {len(fused_horses)} chevaux traités")
        return fused_horses

    def _fuse_horse(self, horse: dict, race: dict) -> dict:
        """Fusionne toutes les dimensions pour un cheval."""
        fused = {**horse}  # Copie des données de base

        # ── Score forme (historique + récent) ─────────────────────
        fused["score_forme"] = self._compute_forme_score(horse)

        # ── Score cotes (signal marché) ────────────────────────────
        fused["score_cotes"] = self._compute_odds_score(horse)

        # ── Score jockey ───────────────────────────────────────────
        fused["score_jockey"] = self._compute_jockey_score(horse)

        # ── Score conditions (distance + terrain) ─────────────────
        fused["score_conditions"] = self._compute_conditions_score(horse, race)

        # ── Score sentiment ────────────────────────────────────────
        fused["score_sentiment"] = self._compute_sentiment_score(horse)

        # ── Score composite pondéré ────────────────────────────────
        fused["score_composite"] = self._compute_composite(fused)

        # ── Niveau de confiance données ────────────────────────────
        fused["data_coverage"] = self._compute_data_coverage(horse)

        # ── Signal cotes (value_bet, neutral, etc.) ────────────────
        fused["odds_signal"] = horse.get("live_odds", {}).get("signal", "neutral")

        return fused

    def _compute_forme_score(self, horse: dict) -> float:
        """Score forme basé sur historique web + forme PDF."""
        scores = []

        # Forme de base depuis PDF LONAB (form_score calculé par LONABAdapter)
        if horse.get("form_score") is not None:
            scores.append((horse["form_score"], self.SOURCE_WEIGHTS["official_pdf"]))

        # Historique depuis web
        web = horse.get("web_data", {})
        if web.get("win_rate") is not None:
            win_score = min(web["win_rate"] * 2, 1.0)  # Normaliser 0-1
            scores.append((win_score, self.SOURCE_WEIGHTS["historical_data"]))

        if web.get("place_rate") is not None:
            place_score = min(web["place_rate"] * 1.5, 1.0)
            scores.append((place_score, self.SOURCE_WEIGHTS["historical_data"] * 0.8))

        # Dernières courses
        last_races = web.get("last_races", [])
        if last_races:
            recent_score = self._score_recent_races(last_races[:5])
            scores.append((recent_score, self.SOURCE_WEIGHTS["historical_data"]))

        return self._weighted_average(scores)

    def _compute_odds_score(self, horse: dict) -> float:
        """Score basé sur les cotes (cote basse = favori = signal positif potentiel)."""
        live = horse.get("live_odds", {})
        lonab_odds = horse.get("odds_lonab")

        odds = live.get("odds") or lonab_odds
        if not odds or odds <= 0:
            return 0.5

        # Inverser la cote : cote basse → score élevé
        # Formule : 1/cote normalisée entre 0 et 1
        prob_implied = 1.0 / odds
        score = min(prob_implied * 2, 1.0)  # Normaliser

        # Bonus si la cote est en baisse (value_bet)
        signal = live.get("signal", "neutral")
        if signal == "value_bet":
            score = min(score * 1.2, 1.0)
        elif signal == "market_alert":
            score = score * 0.8

        return round(score, 3)

    def _compute_jockey_score(self, horse: dict) -> float:
        """Score basé sur les statistiques du jockey."""
        jockey_stats = horse.get("jockey_stats", {})

        if not jockey_stats:
            return 0.5  # Neutre si pas de données

        scores = []

        if jockey_stats.get("win_rate") is not None:
            scores.append((min(jockey_stats["win_rate"] * 3, 1.0),
                           self.SOURCE_WEIGHTS["jockey_stats"]))

        if jockey_stats.get("place_rate") is not None:
            scores.append((min(jockey_stats["place_rate"] * 2, 1.0),
                           self.SOURCE_WEIGHTS["jockey_stats"] * 0.7))

        recent_form = jockey_stats.get("recent_form", "moyenne")
        form_map = {"bonne": 0.9, "moyenne": 0.5, "mauvaise": 0.2}
        scores.append((form_map.get(recent_form, 0.5),
                       self.SOURCE_WEIGHTS["jockey_stats"]))

        return self._weighted_average(scores)

    def _compute_conditions_score(self, horse: dict, race: dict) -> float:
        """Score d'adéquation cheval/conditions de course."""
        web = horse.get("web_data", {})
        race_distance = race.get("distance", 0)
        race_terrain = race.get("terrain", "")

        score = 0.5
        boosts = 0

        # Adéquation distance
        best_dist = web.get("best_distance")
        if best_dist and race_distance:
            diff = abs(best_dist - race_distance)
            if diff <= 200:
                score += 0.2
                boosts += 1
            elif diff <= 400:
                score += 0.1
                boosts += 1
            elif diff > 800:
                score -= 0.1

        # Adéquation terrain
        best_terrain = web.get("best_terrain", "")
        if best_terrain and race_terrain:
            if best_terrain.lower() == race_terrain.lower():
                score += 0.2
                boosts += 1

        return round(min(max(score, 0.0), 1.0), 3)

    def _compute_sentiment_score(self, horse: dict) -> float:
        """Score sentiment depuis les réseaux sociaux."""
        sentiment = horse.get("sentiment", {})
        if not sentiment:
            return 0.5

        sentiment_map = {"positif": 0.8, "neutre": 0.5, "negatif": 0.2}
        raw_sentiment = sentiment.get("label", "neutre").lower()

        score = sentiment_map.get(raw_sentiment, 0.5)
        confidence = sentiment.get("confidence", 0.5)

        # Pondérer par la confiance du sentiment
        return round(0.5 + (score - 0.5) * confidence, 3)

    def _compute_composite(self, horse: dict) -> float:
        """Score composite final pondéré."""
        weights = {
            "score_forme":      0.30,
            "score_cotes":      0.25,
            "score_jockey":     0.20,
            "score_conditions": 0.15,
            "score_sentiment":  0.10,
        }

        total = 0.0
        for key, w in weights.items():
            total += horse.get(key, 0.5) * w

        return round(total, 4)

    def _compute_data_coverage(self, horse: dict) -> float:
        """
        Évalue la couverture des données disponibles (0-1).
        1.0 = toutes les sources disponibles.
        """
        checks = [
            bool(horse.get("form_score") is not None),
            bool(horse.get("live_odds")),
            bool(horse.get("web_data", {}).get("total_races")),
            bool(horse.get("jockey_stats")),
            bool(horse.get("sentiment")),
        ]
        return round(sum(checks) / len(checks), 2)

    def _score_recent_races(self, races: list) -> float:
        """Score basé sur les dernières courses (pondération décroissante)."""
        if not races:
            return 0.5

        scores = []
        for i, race in enumerate(races):
            pos = race.get("position", 10)
            total = race.get("total_runners", 10)
            if total > 0:
                # Score relatif : 1er = 1.0, dernier = 0.0
                relative_score = 1.0 - (pos - 1) / max(total - 1, 1)
                # Pondération : course la plus récente = poids le plus fort
                weight = 1.0 / (i + 1)
                scores.append((relative_score, weight))

        return self._weighted_average(scores)

    def _weighted_average(self, scores: list) -> float:
        """Calcule une moyenne pondérée depuis une liste de (valeur, poids)."""
        if not scores:
            return 0.5
        total_weight = sum(w for _, w in scores)
        if total_weight == 0:
            return 0.5
        return round(sum(v * w for v, w in scores) / total_weight, 3)
