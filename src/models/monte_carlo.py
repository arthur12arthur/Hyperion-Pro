# ============================================================
# HYPERION PRO v1 — Simulation Monte Carlo
# src/models/monte_carlo.py
# ============================================================

import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class MonteCarloModel:
    """
    Simule N fois chaque course pour estimer les probabilités
    de victoire, de podium (top 3) et de place (top 2) de chaque cheval.
    Utilise les scores composites du FusionEngine comme base.
    """

    def __init__(self, config: dict):
        self.config = config
        self.n_simulations = config.get("monte_carlo", {}).get("n_simulations", 10000)
        self.seed = config.get("monte_carlo", {}).get("seed", 42)
        np.random.seed(self.seed)
        logger.info(f"✅ MonteCarloModel initialisé — {self.n_simulations} simulations")

    def simulate(self, horses: list) -> list:
        """
        Lance les simulations sur toutes les courses.
        Regroupe les chevaux par course, simule chaque course séparément.
        Retourne la liste des chevaux enrichis de probabilités MC.
        """
        # Grouper par course
        races = defaultdict(list)
        for horse in horses:
            race_num = horse.get("race_number", 0)
            races[race_num].append(horse)

        results = []
        for race_num, race_horses in races.items():
            logger.info(f"  🎲 Simulation course {race_num} : {len(race_horses)} partants")
            race_results = self._simulate_race(race_horses)
            results.extend(race_results)

        logger.info(f"  ✅ Monte Carlo : {len(races)} courses simulées")
        return results

    def _simulate_race(self, horses: list) -> list:
        """
        Simule une course N fois et calcule les probabilités pour chaque cheval.
        """
        if not horses:
            return []

        n = len(horses)
        names = [h.get("horse_name", f"Cheval_{i}") for i, h in enumerate(horses)]

        # Probabilités de base depuis score_composite
        base_probs = np.array([
            max(h.get("score_composite", 0.5), 0.01)
            for h in horses
        ])

        # Normaliser pour obtenir des probabilités qui somment à 1
        base_probs = base_probs / base_probs.sum()

        # Compteurs pour chaque position
        win_counts = defaultdict(int)
        place_counts = defaultdict(int)   # Top 2
        show_counts = defaultdict(int)    # Top 3

        # ── Boucle de simulation ──────────────────────────────────
        for _ in range(self.n_simulations):
            # Ajouter du bruit aléatoire pour simuler l'incertitude
            noise = np.random.dirichlet(base_probs * 10)
            # Tirage sans remise pour obtenir l'ordre d'arrivée
            order = np.random.choice(n, size=n, replace=False, p=noise)

            winner = names[order[0]]
            win_counts[winner] += 1

            if n >= 2:
                place_counts[names[order[1]]] += 1
                place_counts[winner] += 1

            if n >= 3:
                for i in range(min(3, n)):
                    show_counts[names[order[i]]] += 1

        # ── Calcul probabilités finales ───────────────────────────
        enriched = []
        for horse in horses:
            name = horse.get("horse_name", "")
            h = {**horse}

            h["mc_win_prob"] = round(win_counts.get(name, 0) / self.n_simulations, 4)
            h["mc_place_prob"] = round(place_counts.get(name, 0) / self.n_simulations, 4)
            h["mc_show_prob"] = round(show_counts.get(name, 0) / self.n_simulations, 4)

            # Rang MC dans la course
            h["mc_rank"] = self._compute_rank(name, win_counts, self.n_simulations)

            # Confiance MC (1-3 étoiles)
            h["mc_confidence"] = self._compute_confidence(
                h["mc_win_prob"], h.get("data_coverage", 0.5)
            )

            enriched.append(h)

        # Trier par probabilité de victoire décroissante
        enriched.sort(key=lambda x: x["mc_win_prob"], reverse=True)

        # Ajouter le rang dans la course
        for i, h in enumerate(enriched):
            h["mc_rank_in_race"] = i + 1

        return enriched

    def _compute_rank(self, name: str, win_counts: dict, n_sim: int) -> int:
        """Calcule le rang MC d'un cheval parmi tous les partants."""
        sorted_names = sorted(win_counts, key=win_counts.get, reverse=True)
        if name in sorted_names:
            return sorted_names.index(name) + 1
        return len(sorted_names) + 1

    def _compute_confidence(self, win_prob: float, data_coverage: float) -> int:
        """
        Score de confiance 1-3 étoiles.
        Basé sur la probabilité de victoire ET la couverture des données.
        """
        base_score = win_prob * data_coverage

        if base_score >= 0.15:
            return 3  # ⭐⭐⭐ Haute confiance
        elif base_score >= 0.08:
            return 2  # ⭐⭐ Confiance modérée
        else:
            return 1  # ⭐ Faible confiance

    def get_top_picks(self, results: list, top_n: int = 3) -> dict:
        """
        Retourne le top N par course selon les probabilités MC.
        Utilisé par le ReportGenerator.
        """
        races = defaultdict(list)
        for horse in results:
            races[horse.get("race_number", 0)].append(horse)

        top_picks = {}
        for race_num, race_horses in races.items():
            sorted_horses = sorted(
                race_horses,
                key=lambda x: x.get("mc_win_prob", 0),
                reverse=True
            )
            top_picks[race_num] = sorted_horses[:top_n]

        return top_picks

    def compute_race_uncertainty(self, race_horses: list) -> float:
        """
        Calcule l'indice d'incertitude d'une course (0 = certitude, 1 = chaos).
        Basé sur l'entropie de la distribution des probabilités.
        """
        probs = [h.get("mc_win_prob", 0) for h in race_horses]
        probs = [p for p in probs if p > 0]

        if not probs:
            return 1.0

        probs_arr = np.array(probs)
        probs_arr = probs_arr / probs_arr.sum()

        # Entropie de Shannon normalisée
        entropy = -np.sum(probs_arr * np.log2(probs_arr + 1e-10))
        max_entropy = np.log2(len(probs_arr))

        return round(entropy / max_entropy if max_entropy > 0 else 1.0, 3)
