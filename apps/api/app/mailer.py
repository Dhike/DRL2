import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("drl2.mailer")


def _open_connection() -> smtplib.SMTP:
    if settings.smtp_port == 465:
        return smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
    return smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)


def send_email(to: str, subject: str, text_body: str) -> None:
    if settings.email_backend == "console":
        logger.warning(
            "EMAIL (console backend) to=%s subject=%s\n%s", to, subject, text_body
        )
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)

    with _open_connection() as smtp:
        if settings.smtp_port != 465 and settings.smtp_use_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_verification_email(to: str, code: str) -> None:
    send_email(
        to,
        "Your DRL2 verification code",
        f"Your verification code is {code}.\n\n"
        "It expires in 10 minutes. If you did not create an account, "
        "you can ignore this email.\n",
    )


def send_password_reset_email(to: str, code: str) -> None:
    send_email(
        to,
        "Your DRL2 password reset code",
        f"Your password reset code is {code}.\n\n"
        "It expires in 10 minutes. If you did not request this, you can "
        "ignore this email and your password will not change.\n",
    )
