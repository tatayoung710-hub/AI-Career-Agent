"""Explicitly enabled recruiting email. Ambiguous delivery must never be retried."""

import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from app.config import settings


def recruiting_recipient(jd_text: str) -> str:
    allowed = {x.strip().lower() for x in settings.smtp_recipient_allowlist.split(",") if x.strip()}
    candidates = re.findall(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", jd_text)
    for candidate in candidates:
        address = candidate.lower()
        if address in allowed:
            return address
    raise ValueError("JD 没有包含服务器收件允许名单中的招聘邮件地址")


def send_recruiting_email(jd_text: str, subject: str, body: str, attachment: Path) -> dict:
    if not settings.email_submit_enabled:
        raise ValueError("服务器尚未启用招聘邮件发送")
    if not settings.smtp_host or not settings.smtp_from:
        raise ValueError("SMTP_HOST 和 SMTP_FROM 尚未配置")
    recipient = recruiting_recipient(jd_text)
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject.replace("\r", " ").replace("\n", " ")
    message["Message-ID"] = make_msgid()
    message.set_content(body)
    message.add_attachment(attachment.read_bytes(), maintype="application", subtype="pdf", filename=attachment.name)
    sending_started = False
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_starttls:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            sending_started = True
            refused = server.send_message(message)
            if refused:
                return {"kind": "rejected", "recipient": recipient, "message_id": message["Message-ID"]}
    except Exception:
        if sending_started:
            return {
                "kind": "unknown", "recipient": recipient, "message_id": message["Message-ID"],
                "detail": "发送阶段出现异常，可能已经被邮件服务器受理；需要核实，不能自动重发。",
            }
        raise
    return {
        "kind": "mail_accepted", "recipient": recipient,
        "message_id": message["Message-ID"],
        "detail": "SMTP 服务器受理邮件，不代表 HR 已读或申请已受理。",
    }
