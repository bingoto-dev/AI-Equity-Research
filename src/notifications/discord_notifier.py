"""Discord webhook notification sender."""

import logging
from typing import Any, Optional

import httpx

from config.settings import NotificationSettings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Sends notifications to Discord via webhook."""

    def __init__(self, settings: NotificationSettings):
        """Initialize the Discord notifier.

        Args:
            settings: Notification settings
        """
        self.webhook_url = (
            settings.discord_webhook_url.get_secret_value()
            if settings.discord_webhook_url
            else None
        )
        self._enabled = bool(self.webhook_url)

    @property
    def is_enabled(self) -> bool:
        """Check if Discord notifications are enabled."""
        return self._enabled

    async def send(
        self,
        content: str,
        embeds: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        """Send a message to Discord.

        Args:
            content: Message content
            embeds: Optional Discord embeds for rich formatting

        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.warning("Discord notifications not configured")
            return False

        try:
            payload = {"content": content}
            if embeds:
                payload["embeds"] = embeds

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info("Discord notification sent")
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    async def send_research_complete(
        self,
        run_id: str,
        summary: str,
        picks: list[dict[str, Any]],
    ) -> bool:
        """Send research completion notification with rich embed.

        Args:
            run_id: Research run ID
            summary: Summary text
            picks: Final picks list

        Returns:
            True if sent successfully
        """
        # Build picks text
        picks_text = ""
        medals = ["🥇", "🥈", "🥉"]
        for i, pick in enumerate(picks[:3]):
            ticker = pick.get("ticker", "N/A")
            company = pick.get("company_name", "Unknown")
            conviction = pick.get("conviction_score", 0)
            medal = medals[i] if i < 3 else "•"
            picks_text += f"{medal} **{ticker}** - {company} ({conviction:.0f}%)\n"

        embed = {
            "title": "🎯 AI Equity Research Complete",
            "color": 0x00FF00,  # Green
            "fields": [
                {
                    "name": "Run ID",
                    "value": f"`{run_id}`",
                    "inline": True,
                },
                {
                    "name": "Top 3 Recommendations",
                    "value": picks_text or "No picks",
                    "inline": False,
                },
            ],
            "footer": {
                "text": summary,
            },
        }

        # Add thesis for top pick
        if picks:
            top_pick = picks[0]
            thesis = top_pick.get("thesis", "")
            if thesis:
                embed["fields"].append({
                    "name": f"📊 {top_pick.get('ticker', 'N/A')} Thesis",
                    "value": thesis[:1024],  # Discord field limit
                    "inline": False,
                })

        return await self.send("", [embed])

    async def send_error(
        self,
        run_id: str,
        error: str,
    ) -> bool:
        """Send error notification.

        Args:
            run_id: Research run ID
            error: Error message

        Returns:
            True if sent successfully
        """
        embed = {
            "title": "⚠️ AI Research Error",
            "color": 0xFF0000,  # Red
            "fields": [
                {
                    "name": "Run ID",
                    "value": f"`{run_id}`",
                    "inline": True,
                },
                {
                    "name": "Error",
                    "value": error[:1024],
                    "inline": False,
                },
            ],
        }

        return await self.send("", [embed])

    async def send_progress(
        self,
        run_id: str,
        loop_number: int,
        status: str,
    ) -> bool:
        """Send progress update.

        Args:
            run_id: Research run ID
            loop_number: Current loop number
            status: Current status

        Returns:
            True if sent successfully
        """
        embed = {
            "title": "🔄 Research Progress",
            "color": 0x0099FF,  # Blue
            "fields": [
                {
                    "name": "Run ID",
                    "value": f"`{run_id}`",
                    "inline": True,
                },
                {
                    "name": "Loop",
                    "value": str(loop_number),
                    "inline": True,
                },
                {
                    "name": "Status",
                    "value": status,
                    "inline": True,
                },
            ],
        }

        return await self.send("", [embed])
