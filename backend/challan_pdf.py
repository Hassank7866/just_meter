"""Render a reviewed case once, at issuance. Banking integration is not assumed."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .config import settings


def render_issued_challan(data):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    paragraph = lambda text: Paragraph(escape(str(text)), styles["BodyText"])
    content = [Paragraph("GovTrack / Just Meter — E-Challan", styles["Title"]),
               paragraph("Issued application record. Check the case register for current appeal/cancellation status."), Spacer(1, 15)]
    for label, key in (("Reference", "challan_id"), ("Vehicle registration at review", "plate_number"),
                       ("Department at capture", "department"), ("Issued at", "issued_at"),
                       ("Due at", "due_at"), ("Approved by", "approved_by"), ("Issued by", "issued_by"),
                       ("Fine (PKR)", "fine_amount"), ("Charged observation", "charged_sighting_id")):
        content.append(paragraph(f"{label}: {data.get(key, '')}"))
    content.extend([Spacer(1, 15), paragraph("Supporting violation history (the fine applies to the charged observation):")])
    rows = [[paragraph(x) for x in ("Observed", "Plate at capture", "Criteria")]]
    for row in data.get("violations_history", []):
        rows.append([paragraph(row.get(k, "")) for k in ("timestamp", "plate_number", "violation_criteria")])
    table = Table(rows, colWidths=[145, 120, 230], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]))
    content.extend([table, Spacer(1, 12), paragraph("Evidence references and SHA-256 hashes:")])
    for item in data.get("evidence", []):
        content.append(paragraph(f"{item['evidence_id']}: {item['full_image_sha256']}"))
    if data.get("evidence") and data["evidence"][-1].get("plate_crop"):
        photo = data["evidence"][-1]
        path = (settings.snapshots_dir / photo["plate_crop"]).resolve()
        if settings.snapshots_dir.resolve() not in path.parents:
            raise ValueError("Evidence image is outside the archive")
        image = Image(str(path))
        scale = min(495 / image.imageWidth, 250 / image.imageHeight)
        image.drawWidth, image.drawHeight = image.imageWidth * scale, image.imageHeight * scale
        content.extend([Spacer(1, 12), paragraph(f"Supporting evidence image: {photo['evidence_id']}"), image])
    content.extend([Spacer(1, 12), paragraph("Payment collection is not integrated. This document has no banking PSID or bank account instructions.")])
    SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40).build(content)
    return buffer.getvalue()
