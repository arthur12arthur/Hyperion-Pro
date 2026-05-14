# ============================================================
# HYPERION PRO v1 — Assemblage dataset final
# src/data/data_merger.py
# ============================================================

import logging

logger = logging.getLogger(__name__)


class DataMerger:
    """
    Assemble les donnees du PDF LONAB avec les donnees web
    (cotes live, historiques, sentiment) en un dataset unifie par cheval.
    """

    def __init__(self, config: dict):
        self.config = config
        logger.info("DataMerger initialise")

    def merge(self, lonab_data: dict, live_odds: dict, web_data: dict) -> dict:
        """
        Fusionne toutes les sources en un dataset unifie.
        Retourne la structure lonab_data enrichie.
        """
        merged = {**lonab_data}

        for race in merged.get("races", []):
            for horse in race.get("horses", []):
                name = horse.get("horse_name", "")

                # Injecter les cotes live
                if name in live_odds:
                    horse["live_odds"] = live_odds[name]

                # Injecter les donnees web (historique, pronostics)
                if name in web_data:
                    horse["web_data"] = web_data[name]

                # Injecter les stats jockey depuis web_data si disponibles
                jockey = horse.get("jockey", "")
                if jockey and name in web_data:
                    horse["jockey_stats"] = web_data[name].get("jockey_stats", {})

        total_horses = sum(
            len(r.get("horses", [])) for r in merged.get("races", [])
        )
        logger.info(f"  DataMerger : {total_horses} chevaux enrichis")
        return merged
