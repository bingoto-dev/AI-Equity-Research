"""Email notification sender."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from config.settings import NotificationSettings

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Sends email notifications."""

    def __init__(self, settings: NotificationSettings):
        """Initialize the email notifier.

        Args:
            settings: Notification settings
        """
        self.settings = settings
        self._enabled = (
            settings.email_enabled
            and settings.email_smtp_host
            and settings.email_username
            and settings.email_password
            and settings.email_from
            and settings.email_to
        )

    @property
    def is_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return bool(self._enabled)

    async def send(
        self,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """Send an email notification.

        Args:
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body

        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.warning("Email notifications not configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.settings.email_from
            msg["To"] = self.settings.email_to

            # Add plain text part
            msg.attach(MIMEText(body, "plain"))

            # Add HTML part if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            # Send via SMTP
            with smtplib.SMTP(
                self.settings.email_smtp_host,
                self.settings.email_smtp_port,
            ) as server:
                server.starttls()
                server.login(
                    self.settings.email_username,
                    self.settings.email_password.get_secret_value(),
                )
                server.send_message(msg)

            logger.info(f"Email sent: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_research_complete(
        self,
        run_id: str,
        summary: str,
        report_path: Optional[str] = None,
    ) -> bool:
        """Send research completion notification.

        Args:
            run_id: Research run ID
            summary: Summary text
            report_path: Optional path to full report

        Returns:
            True if sent successfully
        """
        subject = f"[AI Research] Analysis Complete - {run_id}"

        body = f"""AI Equity Research Analysis Complete

{summary}

Run ID: {run_id}
"""
        if report_path:
            body += f"\nFull report available at: {report_path}"

        return await self.send(subject, body)

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
        subject = f"[AI Research] Error - {run_id}"

        body = f"""AI Equity Research Error

Run ID: {run_id}

Error:
{error}

Please check the logs for more details.
"""
        return await self.send(subject, body)
