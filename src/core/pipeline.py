# ============================================================
# HYPERION PRO v1 — Pipeline principal
# src/core/pipeline.py
# ============================================================

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from src.data.lonab_adapter import LONABAdapter
from src.data.live_fetcher import LiveFetcher
from src.data.web_scraper import WebScraper
from src.data.fusion_engine import FusionEngine
from src.data.data_merger import DataMerger
from src.features.engineer import FeatureEngineer
from src.features.patterns import PatternDetector
from src.models.monte_carlo import MonteCarloModel
from src.models.ml_ensemble import MLEnsemble
from src.models.rule_based import RuleBasedModel
from src.models.double_validation import DoubleValidator
from src.hades.detector import HADESDetector
from src.betting.ev_calculator import EVCalculator
from src.betting.kelly import KellyCriterion
from src.betting.risk_manager import RiskManager
from src.output.report_generator import ReportGenerator
from src.output.telegram_bot import TelegramBot
from src.utils.config_loader import load_config

load_dotenv()
logger = logging.getLogger(__name__)


class HyperionPipeline:
    """
    Pipeline complet Hyperion Pro v1.
    Orchestre toutes les étapes : Ingestion → Fusion → Prédiction → HADES → Betting → Livraison.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        self.run_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"🚀 Hyperion Pro v1 — Démarrage pipeline [{self.run_date}]")

        # Initialisation des modules
        self.lonab = LONABAdapter(self.config)
        self.live_fetcher = LiveFetcher(self.config)
        self.web_scraper = WebScraper(self.config)
        self.fusion_engine = FusionEngine(self.config)
        self.data_merger = DataMerger(self.config)
        self.feature_engineer = FeatureEngineer(self.config)
        self.pattern_detector = PatternDetector(self.config)
        self.monte_carlo = MonteCarloModel(self.config)
        self.ml_ensemble = MLEnsemble(self.config)
        self.rule_based = RuleBasedModel(self.config)
        self.validator = DoubleValidator(self.config)
        self.hades = HADESDetector(self.config)
        self.ev_calc = EVCalculator(self.config)
        self.kelly = KellyCriterion(self.config)
        self.risk_manager = RiskManager(self.config)
        self.report_gen = ReportGenerator(self.config)
        self.telegram = TelegramBot(self.config)

    def run(self, pdf_path: str = None) -> dict:
        """
        Lance le pipeline complet pour une journée de courses.
        Retourne le rapport final structuré.
        """
        results = {}

        try:
            # ── ÉTAPE 1 : INGESTION ──────────────────────────────────
            logger.info("📥 Étape 1 : Ingestion des données")

            # 1a. Extraction PDF LONAB
            lonab_data = self.lonab.extract(pdf_path)
            logger.info(f"  ✅ LONAB : {len(lonab_data.get('races', []))} courses extraites")

            # 1b. Cotes en temps réel (si activé)
            live_odds = {}
            if self.config["pipeline"]["run_web_intelligence"]:
                live_odds = self.live_fetcher.fetch(lonab_data["horses"])
                logger.info(f"  ✅ Cotes live : {len(live_odds)} chevaux mis à jour")

            # 1c. Historiques et pronostics web
            web_data = {}
            if self.config["pipeline"]["run_web_intelligence"]:
                web_data = self.web_scraper.scrape(lonab_data["horses"])
                logger.info(f"  ✅ Web : historiques récupérés pour {len(web_data)} chevaux")

            # ── ÉTAPE 2 : FUSION & ENRICHISSEMENT ────────────────────
            logger.info("🔀 Étape 2 : Fusion et enrichissement")

            merged = self.data_merger.merge(lonab_data, live_odds, web_data)
            fused = self.fusion_engine.fuse(merged)
            features = self.feature_engineer.compute(fused)
            patterns = self.pattern_detector.detect(features)
            logger.info(f"  ✅ Fusion : {len(features)} chevaux enrichis")

            # ── ÉTAPE 3 : PRÉDICTION ─────────────────────────────────
            logger.info("🧠 Étape 3 : Prédiction")

            mc_results = self.monte_carlo.simulate(features)
            ml_results = {}
            if self.config["pipeline"]["run_ml_ensemble"]:
                ml_results = self.ml_ensemble.predict(features)
            rule_results = self.rule_based.evaluate(features, patterns)
            validated = self.validator.validate(mc_results, ml_results, rule_results)
            logger.info(f"  ✅ Prédictions validées : {len(validated)} courses")

            # ── ÉTAPE 4 : HADES ──────────────────────────────────────
            logger.info("🛡️ Étape 4 : HADES Anti-Pièges")

            if self.config["pipeline"]["run_hades"]:
                validated = self.hades.filter(validated, live_odds)
                logger.info(f"  ✅ HADES : filtrage terminé")

            # ── ÉTAPE 5 : STRATÉGIE DE MISE ──────────────────────────
            logger.info("💰 Étape 5 : Stratégie de mise")

            ev_scores = self.ev_calc.calculate(validated)
            kelly_bets = self.kelly.compute(ev_scores)
            final_bets = self.risk_manager.apply(kelly_bets)
            logger.info(f"  ✅ Mises calculées : {len(final_bets)} paris recommandés")

            # ── ÉTAPE 6 : RAPPORT & LIVRAISON ────────────────────────
            logger.info("📤 Étape 6 : Génération rapport et livraison Telegram")

            report = self.report_gen.generate(
                predictions=validated,
                bets=final_bets,
                patterns=patterns,
                run_date=self.run_date
            )
            self.telegram.send_report(report)
            logger.info("  ✅ Rapport envoyé sur Telegram")

            results = {
                "status": "success",
                "date": self.run_date,
                "races": len(lonab_data.get("races", [])),
                "predictions": len(validated),
                "bets": len(final_bets),
                "report": report,
            }

        except Exception as e:
            logger.error(f"❌ Erreur pipeline : {e}", exc_info=True)
            self.telegram.send_error(str(e))
            results = {"status": "error", "error": str(e), "date": self.run_date}

        return results
