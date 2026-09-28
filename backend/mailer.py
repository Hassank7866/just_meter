from __future__ import annotations

import os
import smtplib
import urllib.parse
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .config import PROJECT_ROOT
from .pdf_generator import generate_psid

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ENV_FILE = PROJECT_ROOT / ".env"


def reload_environment() -> None:
    """Reload environment variables from .env file if it exists."""
    if ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE, override=True)
    else:
        load_dotenv(override=True)


def _smtp_settings() -> dict[str, Any]:
    """Read SMTP settings dynamically on every call so runtime configuration is immediately honored."""
    reload_environment()
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.getenv("SMTP_PORT", "587").strip())
    except (ValueError, TypeError):
        port = 587

    user = os.getenv("SMTP_USER", "").strip()
    raw_password = os.getenv("SMTP_PASSWORD", "")
    # Strip spaces from password (often pasted from Gmail App Passwords like "abcd efgh ijkl mnop")
    password = raw_password.replace(" ", "").strip()
    sender_email = os.getenv("SMTP_FROM", "").strip() or user
    sender_name = os.getenv("SMTP_FROM_NAME", "ANPR Fleet Command").strip()

    use_ssl = os.getenv("SMTP_USE_SSL", "").strip().lower() in ("true", "1", "yes") or port == 465
    use_tls = os.getenv("SMTP_USE_TLS", "").strip().lower() in ("true", "1", "yes") if "SMTP_USE_TLS" in os.environ else (port != 465)

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "configured": bool(user and password),
    }


def get_smtp_config_status() -> dict[str, Any]:
    """Return current SMTP settings for frontend display with passwords masked."""
    settings = _smtp_settings()
    has_pwd = bool(settings["password"])
    return {
        "configured": settings["configured"],
        "host": settings["host"],
        "port": settings["port"],
        "user": settings["user"],
        "sender_email": settings["sender_email"],
        "sender_name": settings["sender_name"],
        "use_tls": settings["use_tls"],
        "use_ssl": settings["use_ssl"],
        "has_password": has_pwd,
        "password_preview": "••••••••" if has_pwd else "",
    }


def save_smtp_settings_to_env(
    host: str,
    port: int,
    user: str,
    password: str | None = None,
    sender_email: str | None = None,
    sender_name: str | None = "ANPR Fleet Command",
    use_tls: bool = True,
    use_ssl: bool = False,
) -> dict[str, Any]:
    """Persist SMTP settings into the project's .env file and reload environment."""
    user = user.strip()
    sender_email = (sender_email or user).strip()
    sender_name = (sender_name or "ANPR Fleet Command").strip()
    host = host.strip()

    # Determine password to write
    current_settings = _smtp_settings()
    final_password = current_settings["password"]
    if password is not None and password.strip() and password.strip() != "••••••••":
        final_password = password.replace(" ", "").strip()

    # Read existing .env lines or create fresh template
    existing_lines: list[str] = []
    if ENV_FILE.exists():
        try:
            existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        except Exception:
            existing_lines = []

    keys_to_set = {
        "SMTP_HOST": host,
        "SMTP_PORT": str(port),
        "SMTP_USER": user,
        "SMTP_PASSWORD": final_password,
        "SMTP_FROM": sender_email,
        "SMTP_FROM_NAME": sender_name,
        "SMTP_USE_TLS": "true" if use_tls else "false",
        "SMTP_USE_SSL": "true" if use_ssl else "false",
    }

    # If BASE_URL not present, ensure it exists
    has_base_url = any(line.startswith("BASE_URL=") for line in existing_lines)
    if not has_base_url:
        keys_to_set["BASE_URL"] = os.getenv("BASE_URL", "http://127.0.0.1:8000")

    updated_keys = set()
    new_lines = []

    for line in existing_lines:
        line_clean = line.strip()
        matched_key = None
        for k in keys_to_set:
            if line_clean.startswith(f"{k}=") or line_clean.startswith(f"#{k}="):
                matched_key = k
                break
        if matched_key:
            new_lines.append(f"{matched_key}={keys_to_set[matched_key]}")
            updated_keys.add(matched_key)
        else:
            new_lines.append(line)

    # Append any keys that weren't in the file
    for k, val in keys_to_set.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={val}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    reload_environment()

    return {
        "success": True,
        "message": "SMTP settings saved successfully to .env and applied immediately.",
        "config": get_smtp_config_status(),
    }


def format_whatsapp_message(
    plate_number: str,
    officer_name: str,
    department: str,
    violation_count: int,
    message_type: str,
    fine_amount: float | None = None,
    challan_id: str | None = None,
    custom_message: str | None = None,
) -> str:
    """Generate a clean, official text message for WhatsApp dispatch with PDF link and bank particulars."""
    officer_greeting = f"Officer {officer_name}" if officer_name else "Vehicle Custodian"
    dept_str = f"({department})" if department else ""
    psid = generate_psid(plate_number, violation_count)
    pdf_link = f"{BASE_URL}/api/challan/pdf/{urllib.parse.quote(plate_number)}"

    if message_type == "challan" or violation_count >= 4:
        cid = challan_id or f"CHL-2026-{plate_number}"
        fine_str = f"PKR {int(fine_amount):,}" if fine_amount else "PKR 2,500"
        msg = (
            f"🚨 *OFFICIAL TRAFFIC / FLEET E-CHALLAN*\n"
            f"🏛 *AJK / PK Government Fleet Command*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Attention: *{officer_greeting}* {dept_str}\n"
            f"Vehicle Plate: *{plate_number}*\n"
            f"Challan Number: *{cid}*\n"
            f"Total Recorded Violations: *{violation_count}*\n"
            f"Status: *4th Violation Policy Exceeded*\n"
            f"Fine Penalty Levied: *{fine_str}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 *PAYMENT & BANK PARTICULARS*:\n"
            f"• Designated Bank: *National Bank of Pakistan (NBP)*\n"
            f"• Account Title: *Govt Fleet - Traffic Penalty Collection*\n"
            f"• Bank IBAN: *PK36NBPA0000001284793012*\n"
            f"• 1Bill / Online PSID: *{psid}*\n"
            f"• Online Payment: *Easypaisa / JazzCash / 1Bill / Banking Apps*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 *Download Official PDF Challan*:\n{pdf_link}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
        )
        if custom_message:
            msg += f"📝 *Command Note*: {custom_message}\n"
        msg += (
            f"\nPlease deposit the penalty within 7 business days.\n"
            f"— *Automated Mobile ANPR Surveillance System*"
        )
    else:
        tier_label = f"Warning #{violation_count}" if violation_count in (1, 2, 3) else "Official Warning"
        msg = (
            f"⚠️ *GOVERNMENT FLEET COMPLIANCE NOTICE*\n"
            f"🏛 *AJK / PK Government Fleet Command*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Attention: *{officer_greeting}* {dept_str}\n"
            f"Vehicle Plate: *{plate_number}*\n"
            f"Violation Tier: *{tier_label} (Total: {violation_count}/3)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Notice: This vehicle was spotted in breach of authorized operational areas or duty schedule. "
            f"This serves as an official formal warning.\n\n"
            f"⚡ *Policy Warning*: Accumulating 4 or more violations will result in an automated Departmental Fee Challan and disciplinary review.\n"
        )
        if custom_message:
            msg += f"\n📝 *Command Note*: {custom_message}\n"
        msg += f"\n— *Automated Mobile ANPR Fleet Command*"

    return msg


def generate_whatsapp_url(phone: str, message: str) -> str:
    """Generate universal WhatsApp direct link for web and mobile app."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if digits.startswith("0") and len(digits) == 11:
        digits = "92" + digits[1:]
    elif len(digits) == 10 and digits.startswith("3"):
        digits = "92" + digits

    encoded = urllib.parse.quote(message)
    if digits:
        return f"https://api.whatsapp.com/send?phone={digits}&text={encoded}"
    return f"https://api.whatsapp.com/send?text={encoded}"


def generate_email_html(
    plate_number: str,
    officer_name: str,
    department: str,
    violation_count: int,
    message_type: str,
    violations_history: list[dict[str, Any]],
    fine_amount: float | None = None,
    challan_id: str | None = None,
    custom_message: str | None = None,
) -> str:
    """Generate a sleek, responsive HTML email template for warnings and challans."""
    is_challan = message_type == "challan" or violation_count >= 4
    header_color = "#e11d48" if is_challan else "#f59e0b"
    badge_text = "OFFICIAL E-CHALLAN ISSUED" if is_challan else f"FORMAL WARNING #{violation_count}"
    badge_bg = "#881337" if is_challan else "#78350f"
    cid = challan_id or f"CHL-2026-{plate_number}"
    fine_str = f"PKR {int(fine_amount):,}" if fine_amount else "PKR 2,500"
    psid = generate_psid(plate_number, violation_count)
    pdf_link = f"{BASE_URL}/api/challan/pdf/{urllib.parse.quote(plate_number)}"

    history_rows = ""
    for idx, v in enumerate(violations_history[-5:], start=1):
        raw_time = v.get("timestamp", "N/A")
        try:
            formatted_time = raw_time[:19].replace("T", " ")
        except Exception:
            formatted_time = raw_time
        history_rows += f"""
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 10px; font-size: 12px; color: #94a3b8;">#{idx}</td>
            <td style="padding: 10px; font-size: 12px; color: #f8fafc; font-family: monospace;">{formatted_time}</td>
            <td style="padding: 10px; font-size: 12px; color: #38bdf8;">{v.get('camera_area', 'N/A')}</td>
            <td style="padding: 10px; font-size: 12px; color: #f43f5e;">{v.get('violation_criteria', 'UNAUTHORIZED_AREA')}</td>
        </tr>
        """

    bank_section = f"""
    <div style="background-color: #064e3b; border: 1px solid #059669; border-radius: 8px; padding: 16px; margin: 20px 0;">
        <div style="font-size: 12px; font-weight: bold; color: #a7f3d0; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
            🏦 Bank Deposit &amp; 1Bill Online Payment Particulars
        </div>
        <table style="width: 100%; font-size: 12px; color: #ecfdf5; border-collapse: collapse;">
            <tr><td style="padding: 4px 0; color: #a7f3d0;">Designated Bank:</td><td style="font-weight: bold;">National Bank of Pakistan (NBP)</td></tr>
            <tr><td style="padding: 4px 0; color: #a7f3d0;">Account Title:</td><td style="font-weight: bold;">Govt Fleet - Traffic Penalties Collection</td></tr>
            <tr><td style="padding: 4px 0; color: #a7f3d0;">Account IBAN:</td><td style="font-family: monospace; font-weight: bold; color: #34d399;">PK36NBPA0000001284793012</td></tr>
            <tr><td style="padding: 4px 0; color: #a7f3d0;">1Bill / e-Payment PSID:</td><td style="font-family: monospace; font-weight: bold; color: #6ee7b7; font-size: 14px;">{psid}</td></tr>
            <tr><td style="padding: 4px 0; color: #a7f3d0;">Payment Options:</td><td>Easypaisa, JazzCash, 1Bill, Mobile Banking Apps, or NBP Branch</td></tr>
        </table>
        <div style="margin-top: 12px; text-align: center;">
            <a href="{pdf_link}" style="display: inline-block; background-color: #0284c7; color: #ffffff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 12px;">
                📄 Download Official PDF Challan
            </a>
        </div>
    </div>
    """ if is_challan else ""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #090d16; color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #0f172a; border-radius: 12px; border: 1px solid #1e293b; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .header {{ background: linear-gradient(135deg, {header_color} 0%, #0f172a 100%); padding: 24px; text-align: center; }}
            .badge {{ display: inline-block; padding: 6px 14px; background-color: {badge_bg}; color: #ffffff; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.2); }}
            .title {{ margin: 0; font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; }}
            .content {{ padding: 24px; }}
            .details-box {{ background-color: #1e293b; border-radius: 8px; padding: 16px; margin: 16px 0; border: 1px solid #334155; }}
            .label {{ color: #94a3b8; font-weight: 500; }}
            .value {{ color: #ffffff; font-weight: 600; text-align: right; }}
            .fine-box {{ background: linear-gradient(135deg, rgba(225, 29, 72, 0.2) 0%, rgba(15, 23, 42, 0.8) 100%); border: 1px solid #e11d48; border-radius: 8px; padding: 16px; text-align: center; margin: 20px 0; }}
            .fine-title {{ font-size: 12px; color: #fda4af; text-transform: uppercase; letter-spacing: 1px; }}
            .fine-amount {{ font-size: 28px; font-weight: 900; color: #ffffff; font-family: monospace; margin: 6px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
            th {{ background-color: #1e293b; padding: 8px 10px; font-size: 11px; color: #94a3b8; text-align: left; text-transform: uppercase; }}
            .footer {{ background-color: #090d16; padding: 16px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="badge">{badge_text}</div>
                <h1 class="title">Government Fleet Command Notice</h1>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: rgba(255,255,255,0.8);">Automated Mobile ANPR Violation System</p>
            </div>
            <div class="content">
                <p style="font-size: 14px; line-height: 1.5; color: #cbd5e1;">
                    Dear <strong>{officer_name or 'Vehicle Officer / Custodian'}</strong>,
                </p>
                <p style="font-size: 13px; line-height: 1.6; color: #94a3b8;">
                    {"This notification serves as a formal Electronic Traffic Challan for repeated unauthorized fleet movements." if is_challan else "This is an automated compliance warning regarding unauthorized movement of government fleet vehicle."}
                </p>

                <div class="details-box">
                    <table style="margin: 0;">
                        <tr><td class="label">Vehicle Plate:</td><td class="value" style="font-family: monospace; color: #38bdf8;">{plate_number}</td></tr>
                        <tr><td class="label">Department:</td><td class="value">{department or 'N/A'}</td></tr>
                        <tr><td class="label">Officer Assigned:</td><td class="value">{officer_name or 'N/A'}</td></tr>
                        <tr><td class="label">Total Violations:</td><td class="value" style="color: {header_color};">{violation_count} Incident(s)</td></tr>
                        {"<tr><td class='label'>Challan ID:</td><td class='value' style='font-family: monospace;'>" + cid + "</td></tr>" if is_challan else ""}
                    </table>
                </div>

                {f'''
                <div class="fine-box">
                    <div class="fine-title">Total Penalty Payable</div>
                    <div class="fine-amount">{fine_str}</div>
                    <div style="font-size: 11px; color: #cbd5e1;">Payable within 7 days at State Treasury / Transport Office / Online 1Bill</div>
                </div>
                ''' if is_challan else ''}

                {bank_section}

                {f'''
                <div style="background-color: #1e293b; border-left: 3px solid #38bdf8; padding: 12px; border-radius: 4px; margin: 16px 0; font-size: 12px; color: #e2e8f0;">
                    <strong>Command Directive:</strong> {custom_message}
                </div>
                ''' if custom_message else ''}

                <h3 style="font-size: 13px; text-transform: uppercase; color: #94a3b8; margin: 20px 0 8px 0;">Recent Violation Logs</h3>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Timestamp</th>
                            <th>Location Area</th>
                            <th>Criteria</th>
                        </tr>
                    </thead>
                    <tbody>
                        {history_rows}
                    </tbody>
                </table>
            </div>
            <div class="footer">
                Automated Mobile ANPR Command & Surveillance System • Islamic Republic of Pakistan & AJK Territory
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email_notification(
    recipient_email: str,
    subject: str,
    html_content: str,
    plain_text: str = "",
    pdf_attachment: bytes | None = None,
    attachment_filename: str = "E-Challan.pdf",
    custom_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send an email using SMTP (supporting STARTTLS and SSL with optional PDF attachment)."""
    recipient_email = (recipient_email or "").strip()
    if not recipient_email or "@" not in recipient_email:
        return {"success": False, "error": "Invalid recipient email address."}

    cfg = custom_config or _smtp_settings()
    smtp_host = cfg.get("host", "smtp.gmail.com")
    smtp_port = int(cfg.get("port", 587))
    smtp_user = cfg.get("user", "").strip()
    smtp_password = (cfg.get("password") or "").replace(" ", "").strip()
    smtp_from = cfg.get("sender_email", "").strip() or smtp_user
    smtp_from_name = cfg.get("sender_name", "ANPR Fleet Command").strip()
    use_ssl = cfg.get("use_ssl", False) or smtp_port == 465
    use_tls = cfg.get("use_tls", True) if smtp_port != 465 else False

    if not smtp_user or not smtp_password:
        return {
            "success": False,
            "mode": "not_configured",
            "error": "SMTP credentials are not configured. Please open Email Settings to enter your SMTP User & App Password.",
            "recipient": recipient_email,
            "subject": subject,
        }

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = formataddr((smtp_from_name, smtp_from)) if smtp_from_name else smtp_from
        msg["To"] = recipient_email

        body_part = MIMEMultipart("alternative")
        if plain_text:
            body_part.attach(MIMEText(plain_text, "plain", "utf-8"))
        body_part.attach(MIMEText(html_content, "html", "utf-8"))
        msg.attach(body_part)

        if pdf_attachment:
            pdf_part = MIMEApplication(pdf_attachment, _subtype="pdf")
            pdf_part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
            msg.attach(pdf_part)

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [recipient_email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [recipient_email], msg.as_string())

        return {
            "success": True,
            "mode": "smtp_live",
            "message": f"Official email successfully dispatched to {recipient_email}.",
            "recipient": recipient_email,
            "subject": subject,
        }
    except smtplib.SMTPAuthenticationError as exc:
        msg_str = str(exc)
        return {
            "success": False,
            "mode": "auth_error",
            "error": f"SMTP Authentication failed (535). Please verify your username and password. If using Gmail, ensure 2FA is active and use a generated 16-character Google App Password (not your personal password). Details: {msg_str}",
            "recipient": recipient_email,
        }
    except smtplib.SMTPConnectError as exc:
        return {
            "success": False,
            "mode": "connect_error",
            "error": f"Could not connect to SMTP server {smtp_host}:{smtp_port}. Please check the host and port settings. Details: {str(exc)}",
            "recipient": recipient_email,
        }
    except Exception as exc:
        return {
            "success": False,
            "mode": "error",
            "error": f"SMTP dispatch failed: {str(exc)}",
            "recipient": recipient_email,
        }


def send_test_email(recipient_email: str, custom_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a diagnostic test email to verify SMTP configuration and connectivity."""
    now_str = urllib.parse.quote("now")
    cfg = custom_config or _smtp_settings()
    host_display = cfg.get("host", "smtp.gmail.com")
    port_display = cfg.get("port", 587)
    user_display = cfg.get("user", "N/A")
    sender_display = cfg.get("sender_email", user_display)

    subject = "🧪 Test Notification: Mobile ANPR Fleet Command SMTP Active"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #090d16; color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 580px; margin: 0 auto; background-color: #0f172a; border-radius: 12px; border: 1px solid #1e293b; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #0284c7 0%, #1e1b4b 100%); padding: 24px; text-align: center; }}
            .content {{ padding: 24px; }}
            .badge {{ display: inline-block; padding: 5px 12px; background-color: #0284c7; color: white; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
            .card {{ background-color: #1e293b; border-radius: 8px; padding: 16px; margin: 16px 0; border: 1px solid #334155; }}
            table {{ width: 100%; border-collapse: collapse; }}
            td {{ padding: 6px 0; font-size: 13px; }}
            .label {{ color: #94a3b8; width: 40%; }}
            .val {{ color: #38bdf8; font-weight: 600; font-family: monospace; }}
            .footer {{ background-color: #090d16; padding: 16px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="badge">SMTP Connectivity Verified</div>
                <h2 style="margin: 8px 0 0 0; color: white;">ANPR Command Email Test</h2>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: rgba(255,255,255,0.8);">Automated Mobile ANPR Violation System</p>
            </div>
            <div class="content">
                <p style="font-size: 14px; color: #cbd5e1; line-height: 1.5;">
                    This is an official verification message confirming that the <strong>Automated Mobile ANPR Email Dispatch System</strong> has been configured correctly.
                </p>
                <div class="card">
                    <table>
                        <tr><td class="label">SMTP Host:</td><td class="val">{host_display}:{port_display}</td></tr>
                        <tr><td class="label">Authenticated User:</td><td class="val">{user_display}</td></tr>
                        <tr><td class="label">Sender Identity:</td><td class="val">{sender_display}</td></tr>
                        <tr><td class="label">Test Recipient:</td><td class="val">{recipient_email}</td></tr>
                        <tr><td class="label">Status:</td><td class="val" style="color: #34d399;">CONNECTED &amp; READY</td></tr>
                    </table>
                </div>
                <p style="font-size: 12px; color: #94a3b8;">
                    Warnings, Tier Escalate notices, and Official PDF E-Challans will be delivered from this account.
                </p>
            </div>
            <div class="footer">
                Automated Mobile ANPR Command &amp; Surveillance System • Islamic Republic of Pakistan &amp; AJK
            </div>
        </div>
    </body>
    </html>
    """
    plain_text = (
        f"Automated Mobile ANPR Fleet Command - SMTP Test\n"
        f"Status: Connected and ready\n"
        f"Host: {host_display}:{port_display}\n"
        f"User: {user_display}\n"
        f"Recipient: {recipient_email}\n"
    )

    return send_email_notification(
        recipient_email=recipient_email,
        subject=subject,
        html_content=html_content,
        plain_text=plain_text,
        custom_config=custom_config,
    )

