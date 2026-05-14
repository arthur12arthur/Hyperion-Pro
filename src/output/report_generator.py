# ============================================================
# HYPERION PRO v1 — Generateur de rapport
# src/output/report_generator.py
# ============================================================

import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Genere le rapport quotidien structure en JSON et Markdown.
    Utilise par TelegramBot pour la livraison.
    """

    def __init__(self, config: dict):
        self.config = config
        logger.info("ReportGenerator initialise")

    def generate(self, predictions: list, bets: list,
                 patterns: dict, run_date: str) -> dict:
        """Genere le rapport complet du jour."""

        report = {
            "date": run_date,
            "generated_at": datetime.now().isoformat(),
            "races": self._count_races(predictions),
            "total_horses": len(predictions),
            "validated_horses": sum(1 for h in predictions if h.get("is_validated")),
            "hades_blocked": sum(1 for h in predictions if h.get("hades_status") == "blocked"),
            "hades_warnings": sum(1 for h in predictions if h.get("hades_status") == "warning"),
            "bets": bets,
            "predictions": predictions,
            "patterns": patterns,
            "top_picks": self._get_top_picks(predictions),
            "summary": self._build_summary(predictions, bets),
        }

        # Sauvegarder le rapport JSON
        self._save_report(report, run_date)

        logger.info(
            f"  Rapport genere : {report['races']} courses | "
            f"{len(bets)} paris | {report['hades_blocked']} bloques HADES"
        )
        return report

    def _get_top_picks(self, predictions: list) -> list:
        """Top 3 chevaux toutes courses confondues."""
        validated = [
            h for h in predictions
            if h.get("is_validated") and h.get("hades_status") != "blocked"
        ]
        sorted_horses = sorted(
            validated,
            key=lambda x: x.get("final_score", 0),
            reverse=True
        )
        return sorted_horses[:3]

    def _build_summary(self, predictions: list, bets: list) -> str:
        n_races = self._count_races(predictions)
        n_bets  = len(bets)
        total_mise = sum(b.get("bet_amount", 0) for b in bets)

        if not bets:
            return f"{n_races} courses analysees. Aucun pari recommande aujourd'hui."

        return (
            f"{n_races} courses analysees. "
            f"{n_bets} paris recommandes. "
            f"Mise totale suggeree : {total_mise:.0f} FCFA."
        )

    def _count_races(self, predictions: list) -> int:
        return len(set(h.get("race_number") for h in predictions if h.get("race_number")))

    def _save_report(self, report: dict, run_date: str):
        os.makedirs("reports", exist_ok=True)
        path = f"reports/report_{run_date}.json"
        # Enlever les objets non serializables
        safe_report = {
            k: v for k, v in report.items()
            if k not in ("predictions", "patterns")
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(safe_report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le rapport : {e}")
