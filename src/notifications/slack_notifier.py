"""Slack webhook notification sender."""

import logging
from typing import Any, Optional

import httpx

from config.settings import NotificationSettings

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Sends notifications to Slack via webhook."""

    def __init__(self, settings: NotificationSettings):
        """Initialize the Slack notifier.

        Args:
            settings: Notification settings
        """
        self.webhook_url = (
            settings.slack_webhook_url.get_secret_value()
            if settings.slack_webhook_url
            else None
        )
        self._enabled = bool(self.webhook_url)

    @property
    def is_enabled(self) -> bool:
        """Check if Slack notifications are enabled."""
        return self._enabled

    async def send(
        self,
        message: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        """Send a message to Slack.

        Args:
            message: Fallback text message
            blocks: Optional Slack blocks for rich formatting

        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.warning("Slack notifications not configured")
            return False

        try:
            payload = {"text": message}
            if blocks:
                payload["blocks"] = blocks

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info("Slack notification sent")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def send_research_complete(
        self,
        run_id: str,
        summary: str,
        picks: list[dict[str, Any]],
    ) -> bool:
        """Send research completion notification with rich formatting.

        Args:
            run_id: Research run ID
            summary: Summary text
            picks: Final picks list

        Returns:
            True if sent successfully
        """
        # Build rich blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎯 AI Equity Research Complete",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Run ID:* `{run_id}`",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Top 3 Investment Recommendations:*",
                },
            },
        ]

        # Add picks
        for i, pick in enumerate(picks[:3], 1):
            ticker = pick.get("ticker", "N/A")
            company = pick.get("company_name", "Unknown")
            conviction = pick.get("conviction_score", 0)

            emoji = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else "•"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{ticker}* - {company}\n_Conviction: {conviction:.0f}%_",
                },
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": summary,
                },
            ],
        })

        return await self.send(summary, blocks)

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
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ AI Research Error",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Run ID:* `{run_id}`\n*Error:* {error}",
                },
            },
        ]

        return await self.send(f"Research error: {error}", blocks)
