# ============================================================
# HYPERION PRO v1 — ML Ensemble
# src/models/ml_ensemble.py
# ============================================================

import logging
import numpy as np

logger = logging.getLogger(__name__)


class MLEnsemble:
    """
    Ensemble de modeles ML (XGBoost + LightGBM + RandomForest).
    Utilise les features calculees pour predire la probabilite de victoire.
    Si aucun modele entraine n'est disponible, utilise le score composite.
    """

    FEATURE_KEYS = [
        "score_forme", "score_cotes", "score_jockey",
        "score_conditions", "score_sentiment", "score_composite",
        "feature_weight_penalty", "feature_age_factor",
        "feature_distance_fit", "feature_jcurve",
        "mc_win_prob", "data_coverage",
    ]

    def __init__(self, config: dict):
        self.config = config
        self.models = {}
        self._try_load_models()
        logger.info(f"MLEnsemble initialise — {len(self.models)} modeles charges")

    def _try_load_models(self):
        """Tente de charger les modeles sauvegardes."""
        import os, joblib
        model_names = ["xgboost", "lightgbm", "random_forest"]
        for name in model_names:
            path = f"models/{name}.joblib"
            if os.path.exists(path):
                try:
                    self.models[name] = joblib.load(path)
                    logger.info(f"  Modele charge : {name}")
                except Exception as e:
                    logger.warning(f"  Impossible de charger {name} : {e}")

    def predict(self, horses: list) -> dict:
        """
        Predit les probabilites de victoire pour chaque cheval.
        Retourne : horse_name -> {"ml_win_prob": float, "ml_confidence": int}
        """
        results = {}

        if not self.models:
            # Pas de modeles entraines : fallback sur score composite
            logger.info("  MLEnsemble : aucun modele entraine, fallback score composite")
            for horse in horses:
                name = horse.get("horse_name", "")
                composite = horse.get("score_composite", 0.5)
                results[name] = {
                    "ml_win_prob": composite,
                    "ml_confidence": 1,
                    "ml_source": "composite_fallback"
                }
            return results

        for horse in horses:
            name = horse.get("horse_name", "")
            features = self._extract_features(horse)
            probs = []

            for model_name, model in self.models.items():
                try:
                    prob = model.predict_proba([features])[0][1]
                    probs.append(prob)
                except Exception:
                    pass

            if probs:
                avg_prob = float(np.mean(probs))
                confidence = 3 if len(probs) >= 3 else 2 if len(probs) == 2 else 1
                results[name] = {
                    "ml_win_prob": round(avg_prob, 4),
                    "ml_confidence": confidence,
                    "ml_source": "ensemble"
                }
            else:
                results[name] = {
                    "ml_win_prob": horse.get("score_composite", 0.5),
                    "ml_confidence": 1,
                    "ml_source": "composite_fallback"
                }

        logger.info(f"  MLEnsemble : {len(results)} predictions")
        return results

    def _extract_features(self, horse: dict) -> list:
        return [float(horse.get(k, 0.5) or 0.5) for k in self.FEATURE_KEYS]
