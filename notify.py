"""
Delivery — send the daily digest to Telegram and/or Email.

Both channels are optional and independent: each fires only if its credentials
are set. If neither is configured, delivery is skipped (the report file is still
written to data/). Never crashes the run.
"""
import os
import ssl
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _telegram_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER")
                and os.getenv("SMTP_PASSWORD") and os.getenv("EMAIL_TO"))


def _digest_text(run_date, top_a, type_b, fb=None) -> str:
    lines = [
        f"Pain Point Scout — {run_date}",
        f"{len(top_a)} conversations to reply to today · {len(type_b)} build signals.",
        "",
    ]
    if not top_a:
        lines.append("(No engagement opportunities found today.)")
    for r in top_a:
        draft = (r.draft_response or "").strip().replace("\n", " ")
        lines.append(f"#{r.rank}  [{r.source}]  {r.title}")
        lines.append(f"    {r.url}")
        lines.append(f"    Draft: {draft[:600]}")
        lines.append("")
    if type_b:
        lines.append("— Build signals (ideas for Veto+) —")
        for r in type_b[:10]:
            lines.append(f"• {(r.pattern or r.title)}  ({r.source})")
    if fb:
        lines.append("")
        lines.append("— Facebook post ideas (post BY HAND, rotate) —")
        for item in fb:
            lines.append(f"[{item.get('group','')}]")
            lines.append(item.get('post', ''))
            lines.append("")
    return "\n".join(lines)


def _send_telegram(text, logger) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    # Telegram caps messages at 4096 chars — send in chunks.
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [text]
    ok = True
    for chunk in chunks:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=20,
            )
            if r.status_code != 200:
                logger.error(f"Telegram: send failed HTTP {r.status_code}: {r.text[:200]}")
                ok = False
        except Exception as e:
            logger.error(f"Telegram: error {e}")
            ok = False
    if ok:
        logger.info("Telegram: digest sent.")
    return ok


def _send_email(subject, body, md_path, logger) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pw = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_FROM", user)
    to = os.getenv("EMAIL_TO")
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if md_path and os.path.exists(md_path):
            with open(md_path, encoding="utf-8") as f:
                report = f.read()
            att = MIMEText(report, "plain", "utf-8")
            att.add_header("Content-Disposition", "attachment", filename=os.path.basename(md_path))
            msg.attach(att)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, pw)
            s.sendmail(sender, [a.strip() for a in to.split(",")], msg.as_string())
        logger.info("Email: digest sent.")
        return True
    except Exception as e:
        logger.error(f"Email: error {e}")
        return False


def deliver(run_date, top_a, type_b, logger, md_path=None, fb=None):
    if not (_telegram_configured() or _email_configured()):
        logger.info("Notify: no Telegram/email credentials set — skipping delivery "
                    "(report still saved in data/).")
        return
    text = _digest_text(run_date, top_a, type_b, fb=fb)
    subject = f"Pain Point Scout — {run_date}: {len(top_a)} to reply to"
    if _telegram_configured():
        _send_telegram(text, logger)
    if _email_configured():
        _send_email(subject, text, md_path, logger)
