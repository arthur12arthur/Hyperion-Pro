# ============================================================
# HYPERION PRO v1 — Chargeur de configuration
# src/utils/config_loader.py
# ============================================================

import yaml
import os
import logging

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/config.yaml") -> dict:
    """
    Charge la configuration principale YAML.
    Injecte automatiquement les sources depuis sources.yaml.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Fichier de configuration introuvable : {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Charger les sources
    sources_path = os.path.join(os.path.dirname(config_path), "sources.yaml")
    if os.path.exists(sources_path):
        with open(sources_path, "r", encoding="utf-8") as f:
            config["sources"] = yaml.safe_load(f)

    logger.info(f"Configuration chargee depuis {config_path}")
    return config
