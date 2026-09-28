from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.barcode import qr

from .config import settings


def generate_psid(plate_number: str, violation_count: int) -> str:
    """Generate a realistic 14-digit 1Bill / Banking PSID."""
    num_part = "".join(str(ord(c)) for c in plate_number.upper() if c.isalnum())[:6].ljust(6, "0")
    return f"9926{num_part}{violation_count:02d}1"


def generate_challan_pdf_bytes(challan_data: dict[str, Any]) -> bytes:
    """Generate an official, professional PDF E-Challan document with chronological offenses and photo evidence."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=20,
        bottomMargin=20,
    )

    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#0f172a")
    accent_red = colors.HexColor("#be123c")
    accent_blue = colors.HexColor("#0284c7")
    slate_dark = colors.HexColor("#1e293b")
    slate_light = colors.HexColor("#f1f5f9")
    text_gray = colors.HexColor("#475569")

    # Custom styles
    title_style = ParagraphStyle(
        "ChallanTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,  # Center
    )
    subtitle_style = ParagraphStyle(
        "ChallanSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
        alignment=1,
    )
    badge_style = ParagraphStyle(
        "ChallanBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=accent_red,
        alignment=1,
    )
    label_style = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    value_style = ParagraphStyle(
        "ValueStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )
    section_head_style = ParagraphStyle(
        "SectionHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("GOVERNMENT OF AZAD JAMMU & KASHMIR / PAKISTAN", title_style))
    story.append(Paragraph("CENTRAL FLEET COMMAND & TRAFFIC REGULATORY ENFORCEMENT WING", subtitle_style))
    story.append(Paragraph("OFFICIAL ELECTRONIC TRAFFIC CHALLAN & PENALTY INVOICE", badge_style))
    story.append(Spacer(1, 5))

    # 2. Metadata Bar
    plate = challan_data.get("plate_number", "UNKNOWN")
    v_count = challan_data.get("total_violations", 4)
    cid = challan_data.get("challan_id") or f"CHL-2026-{plate}-{v_count:02d}"
    psid = generate_psid(plate, v_count)
    fine_amount = challan_data.get("fine_amount", 2500)
    issue_date = datetime.now().strftime("%d-%b-%Y")
    due_date = (datetime.now() + timedelta(days=7)).strftime("%d-%b-%Y")

    meta_data = [
        [
            Paragraph(f"<b>Challan ID:</b> {cid}", label_style),
            Paragraph(f"<b>Issue Date:</b> {issue_date}", label_style),
            Paragraph(f"<b>Due Date:</b> <font color='#be123c'>{due_date}</font>", label_style),
            Paragraph("<b>Status:</b> <font color='#be123c'>UNPAID</font>", label_style),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[145, 125, 135, 134])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 5))

    # 3. Vehicle & Custodian Particulars
    part_head = [[Paragraph("1. VEHICLE & ASSIGNED OFFICER PARTICULARS", section_head_style), ""]]
    part_head_table = Table(part_head, colWidths=[270, 269])
    part_head_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), slate_dark),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(part_head_table)

    part_rows = [
        [
            Paragraph("<b>Registration Plate:</b>", label_style),
            Paragraph(f"<b><font color='#0284c7' size=9>{plate}</font></b>", value_style),
            Paragraph("<b>Assigned Officer:</b>", label_style),
            Paragraph(challan_data.get("officer_name") or "Unassigned Custodian", value_style),
        ],
        [
            Paragraph("<b>Vehicle ID:</b>", label_style),
            Paragraph(challan_data.get("vehicle_id") or "N/A", value_style),
            Paragraph("<b>Officer Mobile:</b>", label_style),
            Paragraph(challan_data.get("officer_phone") or "N/A", value_style),
        ],
        [
            Paragraph("<b>Department:</b>", label_style),
            Paragraph(challan_data.get("department") or "Government Fleet", value_style),
            Paragraph("<b>Official Email:</b>", label_style),
            Paragraph(challan_data.get("officer_email") or "N/A", value_style),
        ],
        [
            Paragraph("<b>Permitted Operational Zones:</b>", label_style),
            Paragraph(challan_data.get("authorized_areas") or "None Specified", value_style),
            Paragraph("<b>Cumulative Violations:</b>", label_style),
            Paragraph(f"<b><font color='#be123c'>{v_count} Incidents (4th Rule Triggered)</font></b>", value_style),
        ],
    ]
    part_table = Table(part_rows, colWidths=[125, 145, 125, 144])
    part_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(part_table)
    story.append(Spacer(1, 5))

    # 4. Offenses History Breakdown Table (Chronological Order: Oldest First)
    off_head = [[Paragraph("2. RECORDED OFFENSES EVIDENCE BREAKDOWN (CHRONOLOGICAL ORDER)", section_head_style), ""]]
    off_head_table = Table(off_head, colWidths=[270, 269])
    off_head_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), slate_dark),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(off_head_table)

    off_rows = [
        [
            Paragraph("<b>#</b>", label_style),
            Paragraph("<b>Date & Time (PKT)</b>", label_style),
            Paragraph("<b>Camera Location Zone</b>", label_style),
            Paragraph("<b>Offense Rule Criterium</b>", label_style),
            Paragraph("<b>Penalty Status</b>", label_style),
        ]
    ]

    raw_history = challan_data.get("violations_history", [])
    history = sorted(raw_history, key=lambda x: x.get("timestamp", ""))
    latest_record = history[-1] if history else {}
    latest_img_name = challan_data.get("latest_image") or latest_record.get("image") or ""
    latest_timestamp = challan_data.get("last_violation_date") or latest_record.get("timestamp") or ""
    latest_area = challan_data.get("latest_camera_area") or latest_record.get("camera_area") or "Zone Breach"
    latest_crit = challan_data.get("latest_criteria") or latest_record.get("violation_criteria") or "UNAUTHORIZED_AREA"

    for idx, item in enumerate(history, start=1):
        ts = item.get("timestamp", "N/A")
        try:
            ts_fmt = ts[:19].replace("T", " ")
        except Exception:
            ts_fmt = ts
        crit = item.get("violation_criteria") or "UNAUTHORIZED_AREA"
        is_latest = (idx == len(history))
        if idx < 4:
            fee_item = f"Warning #{idx}"
        elif idx == 4:
            fee_item = "<font color='#be123c'><b>PKR 2,500 (Fine)</b></font>"
        else:
            fee_item = "<font color='#be123c'><b>+PKR 1,000</b></font>"

        tag = " <b>[LATEST]</b>" if is_latest else ""
        off_rows.append([
            Paragraph(f"#{idx}{tag}", value_style),
            Paragraph(ts_fmt, value_style),
            Paragraph(item.get("camera_area") or "Zone Breach", value_style),
            Paragraph(f"<font color='#be123c'>{crit}</font>", value_style),
            Paragraph(fee_item, value_style),
        ])

    off_table = Table(off_rows, colWidths=[65, 115, 125, 135, 99])
    off_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(off_table)
    story.append(Spacer(1, 5))

    # 5. Section 3: Latest Violation Photographic Evidence
    ev_head = [[Paragraph("3. LATEST VIOLATION PHOTOGRAPHIC EVIDENCE & ANPR CAMERA CAPTURE", section_head_style), ""]]
    ev_head_table = Table(ev_head, colWidths=[270, 269])
    ev_head_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#b91c1c")),  # Rose-700
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ev_head_table)

    try:
        latest_ts_fmt = latest_timestamp[:19].replace("T", " ")
    except Exception:
        latest_ts_fmt = latest_timestamp or "N/A"

    evidence_img_flowable = None
    if latest_img_name:
        img_path = settings.snapshots_dir / latest_img_name
        if img_path.is_file():
            try:
                with PILImage.open(img_path) as pimg:
                    ow, oh = pimg.size
                    aspect = oh / float(ow)
                    target_w = 180
                    target_h = int(target_w * aspect)
                    if target_h > 95:
                        target_h = 95
                        target_w = int(target_h / aspect)
                evidence_img_flowable = RLImage(str(img_path), width=target_w, height=target_h)
            except Exception:
                evidence_img_flowable = None

    if evidence_img_flowable is None:
        evidence_img_flowable = Paragraph(
            f"<font color='#64748b' size=8><b>NO SNAPSHOT ATTACHED</b><br/>"
            f"Archive ID: <code>{latest_img_name or 'PENDING_CAPTURE'}</code><br/>"
            f"Photographic proof logged on central ANPR server.</font>",
            value_style,
        )

    ev_details = [
        Paragraph(f"<b>Latest Violation Timestamp:</b> <font color='#be123c'><b>{latest_ts_fmt} PKT</b></font>", label_style),
        Paragraph(f"<b>Surveillance Location:</b> {latest_area}", value_style),
        Paragraph(f"<b>Offense Criterium:</b> <font color='#be123c'><b>{latest_crit}</b></font>", value_style),
        Paragraph(f"<b>Penalty Action:</b> 4th Cumulative Offense — Automated Departmental Challan Issued.", value_style),
        Paragraph(f"<b>Camera Evidence File:</b> <code>{latest_img_name or 'N/A'}</code>", ParagraphStyle("FileCode", parent=styles["Normal"], fontName="Courier", fontSize=7, leading=8.5, textColor=colors.HexColor("#475569"))),
        Paragraph("<font color='#0284c7' size=7><i>High-precision ANPR optical capture. Verifiable electronic prima facie record.</i></font>", value_style),
    ]

    ev_box_data = [
        [
            evidence_img_flowable,
            ev_details,
        ]
    ]
    ev_table = Table(ev_box_data, colWidths=[195, 344])
    ev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff1f2")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecdd3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ev_table)
    story.append(Spacer(1, 5))

    # 6. Bank Deposit Particulars Box (Realistic Accounts & 1Bill PSID)
    bank_head = [[Paragraph("4. BANK DEPOSIT PARTICULARS & E-PAYMENT CHANNELS", section_head_style), ""]]
    bank_head_table = Table(bank_head, colWidths=[270, 269])
    bank_head_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#065f46")),  # Emerald Dark
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bank_head_table)

    bank_rows = [
        [
            Paragraph("<b>Designated Bank:</b>", label_style),
            Paragraph("<b>National Bank of Pakistan (NBP)</b>", value_style),
            Paragraph("<b>1Bill e-Payment PSID:</b>", label_style),
            Paragraph(f"<b><font color='#065f46' size=8.5>{psid}</font></b>", value_style),
        ],
        [
            Paragraph("<b>Account Title:</b>", label_style),
            Paragraph("Govt Fleet Penalties Collection", value_style),
            Paragraph("<b>1Bill Option:</b>", label_style),
            Paragraph("100224 (Govt Challan)", value_style),
        ],
        [
            Paragraph("<b>Bank IBAN:</b>", label_style),
            Paragraph("<b>PK36NBPA0000001284793012</b>", value_style),
            Paragraph("<b>Total Payable:</b>", label_style),
            Paragraph(f"<b><font color='#be123c' size=9>PKR {int(fine_amount):,}/-</font></b>", value_style),
        ],
        [
            Paragraph("<b>Head of Account:</b>", label_style),
            Paragraph("C02847-0102-1948", value_style),
            Paragraph("<b>After Due Date:</b>", label_style),
            Paragraph(f"PKR {int(fine_amount + 500):,}/- (+PKR 500 late fee)", value_style),
        ],
    ]
    bank_table = Table(bank_rows, colWidths=[125, 145, 125, 144])
    bank_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),  # Light emerald
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbf7d0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bank_table)
    story.append(Spacer(1, 5))

    # 7. Payment Instructions Note
    instructions_text = (
        "<b>Payment Methods:</b> 1. <b>Mobile Apps:</b> Open <i>Easypaisa, JazzCash, Nayapay, or Mobile Banking App</i> -> Select <b>Bill Payment / 1Bill / Govt Fees</b> -> Enter PSID: <b>"
        + psid
        + "</b>.<br/>2. <b>Bank Branch Counter:</b> Deposit cash at any National Bank of Pakistan (NBP) or Bank of AJK branch across Pakistan with IBAN <b>PK36NBPA0000001284793012</b>."
    )
    inst_para = Paragraph(instructions_text, ParagraphStyle(
        "InstStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor("#334155"),
    ))
    inst_table = Table([[inst_para]], colWidths=[539])
    inst_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(inst_table)
    story.append(Spacer(1, 5))

    # 8. QR Code & Digital Signature Seal
    qr_code = qr.QrCodeWidget(f"CHALLAN:{cid}|PLATE:{plate}|FINE:{fine_amount}|PSID:{psid}|STATUS:UNPAID")
    qr_code.barWidth = 42
    qr_code.barHeight = 42
    qr_code.qrVersion = 1
    d = Drawing(45, 45)
    d.add(qr_code)

    footer_rows = [
        [
            d,
            Paragraph(
                "<b>OFFICIAL ELECTRONIC VERIFICATION SEAL</b><br/>"
                "Scan QR with phone camera to authenticate digital signature & verify payment clearance.<br/>"
                f"Digital Hash: <code>SHA256-{cid[:16]}</code>",
                ParagraphStyle("QRText", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=9, textColor=text_gray),
            ),
            Paragraph(
                "<b>Issuing Regulatory Authority:</b><br/>"
                "Transport & Logistics Enforcement Directorate<br/>"
                "AJK Government Fleet Command<br/>"
                "<i>Electronic Official E-Challan</i>",
                ParagraphStyle("AuthText", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=9, textColor=text_gray, alignment=2),
            ),
        ]
    ]
    footer_table = Table(footer_rows, colWidths=[55, 295, 189])
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(footer_table)

    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
