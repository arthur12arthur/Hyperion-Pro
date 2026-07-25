# ============================================================
# HYPERION PRO v1 — Bot Telegram interactif
# src/output/telegram_bot.py
# ============================================================

import os
import logging
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Envoie les rapports Hyperion Pro sur Telegram.
    Commandes : /start, /top3, /analyse, /bankroll, /historique
    """

    def __init__(self, config: dict):
        self.config   = config
        self.token    = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id  = os.getenv("TELEGRAM_CHAT_ID")
        self.bot      = Bot(token=self.token) if self.token else None
        self._last_report = None
        self._last_bets   = []
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN manquant — envoi desactive")
        else:
            logger.info("Bot Telegram initialise")

    # ── Envoi rapport quotidien ────────────────────────────────────

    def send_report(self, report: dict):
        if not self.bot:
            logger.warning("Bot non configure — rapport non envoye")
            return
        self._last_report = report
        self._last_bets   = report.get("bets", [])
        message = self._format_report(report)
        self._send(message, parse_mode="Markdown")
        logger.info("Rapport envoye sur Telegram")

    def send_error(self, error_msg: str):
        if not self.bot:
            return
        message = f"*HYPERION PRO — ERREUR*\n\n`{error_msg}`"
        self._send(message, parse_mode="Markdown")

    def send_odds_alert(self, horse_name: str, race_num: int,
                        variation_pct: float, signal: str):
        if not self.bot:
            return
        emoji = "📉" if variation_pct < 0 else "📈"
        message = (
            f"{emoji} *ALERTE COTES*\n\n"
            f"Cheval : *{horse_name}*\n"
            f"Course : R{race_num}\n"
            f"Variation : {variation_pct:+.1f}%\n"
            f"Signal : {signal.upper()}"
        )
        self._send(message, parse_mode="Markdown")

    # ── Commandes interactives ─────────────────────────────────────

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "*HYPERION PRO v1*\n\n"
            "Commandes disponibles :\n"
            "/top3 — Top 3 pronostics du jour\n"
            "/analyse R1 — Analyse d'une course\n"
            "/bankroll — Statut de la bankroll\n"
            "/historique — 7 derniers jours\n"
            "/alerte on|off — Alertes cotes",
            parse_mode="Markdown"
        )

    async def cmd_top3(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._last_bets:
            await update.message.reply_text("Aucun pronostic disponible pour aujourd'hui.")
            return

        top3 = sorted(
            self._last_bets,
            key=lambda x: (x.get("mc_confidence", 1), x.get("ev", 0)),
            reverse=True
        )[:3]

        lines = ["*TOP 3 PRONOSTICS DU JOUR*\n"]
        for i, bet in enumerate(top3, 1):
            stars   = "⭐" * bet.get("mc_confidence", 1)
            num     = bet.get("horse_number", "?")
            name    = bet.get("horse_name", "?")
            lines.append(
                f"{i}. {stars} N°{num} *{name}*\n"
                f"   Cote: {bet.get('odds_used', bet.get('odds_lonab', '?'))} | "
                f"EV: +{bet.get('ev', 0):.1%} | "
                f"Mise: {bet.get('bet_amount', 0):.0f} FCFA\n"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_analyse(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        args = ctx.args
        if not args:
            await update.message.reply_text("Usage : /analyse R1")
            return

        race_str = args[0].upper().replace("R", "")
        try:
            race_num = int(race_str)
        except ValueError:
            await update.message.reply_text("Numero de course invalide.")
            return

        if not self._last_report:
            await update.message.reply_text("Aucun rapport disponible.")
            return

        race_horses = [
            h for h in self._last_report.get("predictions", [])
            if h.get("race_number") == race_num
        ]

        if not race_horses:
            await update.message.reply_text(f"Course R{race_num} introuvable.")
            return

        sorted_horses = sorted(race_horses, key=lambda x: x.get("mc_win_prob", 0), reverse=True)
        lines = [f"*ANALYSE COURSE {race_num}*\n"]

        for h in sorted_horses[:6]:
            status_emoji = {"clear": "✅", "warning": "⚠️", "blocked": "🚫"}.get(
                h.get("hades_status", "clear"), "✅"
            )
            num  = h.get("horse_number", "?")
            name = h.get("horse_name", "?")
            lines.append(
                f"{status_emoji} N°{num} *{name}*\n"
                f"   Prob victoire: {h.get('mc_win_prob', 0):.1%} | "
                f"Top3: {h.get('mc_show_prob', 0):.1%}\n"
                f"   Score: {h.get('final_score', h.get('score_composite', 0)):.2f}\n"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_bankroll(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            with open("data/bankroll.txt") as f:
                bankroll = float(f.read().strip())
            await update.message.reply_text(
                f"*BANKROLL ACTUELLE*\n\n{bankroll:,.0f} FCFA",
                parse_mode="Markdown"
            )
        except Exception:
            await update.message.reply_text("Bankroll non disponible.")

    async def cmd_historique(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "*HISTORIQUE 7 JOURS*\n\n"
            "Disponible apres les 7 premiers jours d'utilisation.",
            parse_mode="Markdown"
        )

    # ── Demarrage bot interactif ───────────────────────────────────

    def run_interactive(self):
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN manquant")
            return
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start",      self.cmd_start))
        app.add_handler(CommandHandler("top3",       self.cmd_top3))
        app.add_handler(CommandHandler("analyse",    self.cmd_analyse))
        app.add_handler(CommandHandler("bankroll",   self.cmd_bankroll))
        app.add_handler(CommandHandler("historique", self.cmd_historique))
        logger.info("Bot Telegram demarre en mode interactif")
        app.run_polling()

    # ── Utilitaires ────────────────────────────────────────────────

    def _send(self, text: str, parse_mode: str = None):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=parse_mode
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"Erreur envoi Telegram : {e}")

    def _format_report(self, report: dict) -> str:
        """Formate le rapport complet avec numeros de chevaux."""
        date  = report.get("date", datetime.now().strftime("%Y-%m-%d"))
        bets  = report.get("bets", [])
        races = report.get("races", 0)

        lines = [
            f"*HYPERION PRO v1 — {date}*",
            f"_{races} courses analysees — {len(bets)} paris recommandes_\n",
        ]

        if not bets:
            lines.append("_Aucun pari recommande aujourd'hui (HADES ou EV insuffisant)._")
            return "\n".join(lines)

        # Trier par course puis par probabilite decroissante
        sorted_bets = sorted(
            bets,
            key=lambda x: (x.get("race_number", 99), -x.get("mc_win_prob", 0))
        )

        current_race = None
        for bet in sorted_bets:
            race_num = bet.get("race_number")
            if race_num != current_race:
                current_race = race_num
                lines.append(f"\n*--- COURSE {race_num} ---*")

            stars      = "⭐" * bet.get("mc_confidence", 1)
            hades_ico  = {"clear": "✅", "warning": "⚠️"}.get(
                bet.get("hades_status", "clear"), "✅"
            )
            num        = bet.get("horse_number", "?")
            name       = bet.get("horse_name", "?")
            odds       = bet.get("odds_used") or bet.get("odds_lonab", "?")
            prob       = bet.get("final_score", bet.get("mc_win_prob", 0))
            ev         = bet.get("ev", 0)
            mise       = bet.get("bet_amount", 0)
            reduced    = " *(mise reduite)*" if bet.get("bet_warning_reduced") else ""

            lines.append(
                f"{hades_ico} {stars} N°{num} *{name}*\n"
                f"   Cote: {odds} | Prob: {prob:.1%} | EV: +{ev:.1%}\n"
                f"   Mise suggeree: *{mise:.0f} FCFA*{reduced}"
            )

        lines.append("\n_Hyperion Pro v1 — LONAB Burkina Faso_")
        return "\n".join(lines)
