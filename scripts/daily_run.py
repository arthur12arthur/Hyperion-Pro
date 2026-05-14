# ============================================================
# HYPERION PRO v1 — Script principal quotidien
# scripts/daily_run.py
# ============================================================

import os
import sys
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Ajouter le dossier racine au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.pipeline import HyperionPipeline
from src.utils.config_loader import load_config

load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"logs/hyperion_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Hyperion Pro v1 — Run quotidien")
    parser.add_argument(
        "--pdf", type=str, default=None,
        help="Chemin vers le PDF LONAB (optionnel, telecharge auto si absent)"
    )
    parser.add_argument(
        "--config", type=str, default="config/config.yaml",
        help="Chemin vers le fichier de configuration"
    )
    parser.add_argument(
        "--no-web", action="store_true",
        help="Desactiver la recherche web (mode offline)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simuler sans envoyer sur Telegram"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Creer les dossiers necessaires
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("reports", exist_ok=True)

    logger.info("=" * 60)
    logger.info("  HYPERION PRO v1 — DEMARRAGE")
    logger.info(f"  Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Mode web : {'OFF' if args.no_web else 'ON'}")
    logger.info(f"  Dry run  : {'OUI' if args.dry_run else 'NON'}")
    logger.info("=" * 60)

    # Charger et adapter la config
    config = load_config(args.config)

    if args.no_web:
        config["pipeline"]["run_web_intelligence"] = False
        config["pipeline"]["run_sentiment"] = False
        logger.info("Mode offline : recherche web desactivee")

    if args.dry_run:
        config["telegram"]["send_daily_report"] = False
        config["telegram"]["send_odds_alerts"] = False
        logger.info("Dry run : envoi Telegram desactive")

    # Lancer le pipeline
    try:
        pipeline = HyperionPipeline(config_path=args.config)
        results = pipeline.run(pdf_path=args.pdf)

        if results["status"] == "success":
            logger.info("=" * 60)
            logger.info("  PIPELINE TERMINE AVEC SUCCES")
            logger.info(f"  Courses analysees : {results.get('races', 0)}")
            logger.info(f"  Predictions       : {results.get('predictions', 0)}")
            logger.info(f"  Paris recommandes : {results.get('bets', 0)}")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error(f"Pipeline echoue : {results.get('error')}")
            sys.exit(1)

    except Exception as e:
        logger.critical(f"Erreur critique : {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
