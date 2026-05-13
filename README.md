# ⚡ HYPERION PRO v1

> Système de prédiction hippique intelligent pour les courses LONAB (Burkina Faso)  
> Multi-sources · Monte Carlo · ML Ensemble · HADES Anti-Pièges · Telegram

---

## 🧠 Architecture

```
PDF LONAB → Web Intelligence → Fusion → Prédiction → HADES → Kelly/EV → Telegram
```

Hyperion Pro v1 est la première version du système à intégrer une **couche de recherche web active** :
cotes en temps réel, historiques des chevaux, sentiment des parieurs — en plus du programme officiel LONAB.

---

## 🚀 Fonctionnalités

| Module | Description |
|--------|-------------|
| 📄 **LONAB Adapter** | Extraction PDF via Gemini Vision (partants, jockeys, poids, terrain) |
| 🌐 **Live Fetcher** | Cotes en temps réel + détection de variations significatives |
| 🔍 **Web Scraper** | Historiques chevaux/jockeys depuis sources externes |
| 💬 **Sentiment Analyzer** | Analyse du sentiment parieurs (forums, Telegram) |
| 🔀 **Fusion Engine** | Fusion pondérée multi-sources en dataset unifié |
| 🎯 **Feature Engineering** | J-curve, forme récente, indice jockey, score terrain |
| 🧮 **Monte Carlo** | N simulations pour probabilités victoire/placé/top3 |
| 🤖 **ML Ensemble** | XGBoost + LightGBM + Random Forest + Meta-Learner |
| 🛡️ **HADES** | Détection pièges, anomalies marché et sociales |
| 💰 **Kelly Adaptatif** | Calcul mise optimale selon EV et niveau confiance |
| 📱 **Telegram Bot** | Rapport quotidien + commandes interactives + alertes |
| 🔄 **Backtesting** | Walk-forward pour validation continue des modèles |

---

## 📁 Structure du projet

```
Hyperion-Pro/
├── config/
│   ├── config.yaml              # Configuration principale
│   └── sources.yaml             # Sources web par marché
├── src/
│   ├── core/
│   │   ├── hyperion_pro.py      # Classe principale orchestratrice
│   │   └── pipeline.py          # Pipeline complet
│   ├── data/
│   │   ├── lonab_adapter.py     # Extraction PDF LONAB
│   │   ├── live_fetcher.py      # Cotes temps réel
│   │   ├── web_scraper.py       # Historiques & pronostics web
│   │   ├── sentiment_analyzer.py
│   │   ├── fusion_engine.py     # Fusion pondérée multi-sources
│   │   └── data_merger.py       # Assemblage dataset final
│   ├── features/
│   │   ├── engineer.py
│   │   └── patterns.py
│   ├── models/
│   │   ├── monte_carlo.py
│   │   ├── ml_ensemble.py
│   │   ├── rule_based.py
│   │   └── double_validation.py
│   ├── hades/
│   │   ├── detector.py
│   │   ├── market_anomaly.py
│   │   └── social_anomaly.py
│   ├── betting/
│   │   ├── ev_calculator.py
│   │   ├── kelly.py
│   │   └── risk_manager.py
│   ├── backtesting/
│   │   ├── engine.py
│   │   └── metrics.py
│   └── output/
│       ├── report_generator.py
│       └── telegram_bot.py
├── scripts/
│   ├── daily_run.py             # Script principal
│   └── backtest_full.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── historical/
├── .github/
│   └── workflows/
│       └── daily-run.yml        # Automatisation GitHub Actions
├── requirements.txt
└── .gitignore
```

---

## ⚙️ Installation

```bash
git clone https://github.com/TON_USERNAME/Hyperion-Pro.git
cd Hyperion-Pro
pip install -r requirements.txt
```

---

## 🔑 Variables d'environnement

Crée un fichier `.env` à la racine (ne jamais committer) :

```env
GEMINI_API_KEY=ta_cle_gemini
TELEGRAM_BOT_TOKEN=ton_token_telegram
TELEGRAM_CHAT_ID=ton_chat_id
LONAB_PDF_URL=url_du_programme_lonab
```

Pour GitHub Actions, ajoute ces valeurs dans **Settings → Secrets → Actions**.

---

## 🤖 Utilisation

### Lancement manuel

```bash
python scripts/daily_run.py
```

### Automatisation (GitHub Actions)
Le workflow `.github/workflows/daily-run.yml` se déclenche automatiquement chaque matin.

### Commandes Telegram Bot

| Commande | Action |
|----------|--------|
| `/start` | Démarrer le bot |
| `/top3` | Top 3 pronostics du jour |
| `/analyse R1` | Analyse détaillée de la course 1 |
| `/bankroll` | Statut de la bankroll |
| `/historique` | Résultats des 7 derniers jours |
| `/alerte on` | Activer alertes variations de cotes |

---

## 📊 Scoring de confiance

Chaque pronostic reçoit un score de confiance :

| Score | Signification |
|-------|---------------|
| ⭐⭐⭐ | Haute confiance — tous les signaux alignés |
| ⭐⭐ | Confiance modérée — majorité des signaux positifs |
| ⭐ | Faible confiance — signaux contradictoires |
| 🚫 | HADES alerte — ne pas jouer |

---

## 🛡️ HADES — Système Anti-Pièges

HADES (Hyperion Anomaly Detection & Expert System) surveille :
- Les variations de cotes suspectes (manipulation probable)
- Les favoris statistiquement peu fiables
- Les courses à trop forte incertitude
- Les buzz sociaux artificiels

---

## 📈 Backtesting

```bash
python scripts/backtest_full.py --start 2024-01-01 --end 2024-12-31
```

Métriques produites : ROI, précision top1/top3, taux HADES, calibration Kelly.

---

## 🗺️ Roadmap

- [x] Architecture multi-sources
- [x] Intégration Gemini Vision
- [x] Monte Carlo + ML Ensemble
- [x] HADES Anti-Pièges
- [x] Kelly Adaptatif
- [x] Bot Telegram interactif
- [ ] Dashboard web (React)
- [ ] Version mobile PWA
- [ ] Support multi-marchés (France PMU)
- [ ] Modèle de deep learning (LSTM séries temporelles)

---

## ⚠️ Avertissement

Ce système est développé à des fins d'analyse et de recherche.
Les paris comportent des risques financiers. Jouer de manière responsable.

---

*Hyperion Pro v1 — LONAB Burkina Faso · Powered by Gemini AI & GitHub Actions*
