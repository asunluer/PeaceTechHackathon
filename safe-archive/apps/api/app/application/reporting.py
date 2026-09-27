"""Render a structured preservation report without changing source evidence."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _font_name() -> str:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        pdfmetrics.getFont("ArchiveSans")
    except KeyError:
        try:
            pdfmetrics.registerFont(TTFont("ArchiveSans", path))
        except (OSError, TTFError):
            return "Helvetica"
    return "ArchiveSans"


def _safe(value: object, limit: int = 4000) -> str:
    return escape(str(value if value is not None else "—")[:limit]).replace("\n", "<br/>")


def build_case_report(case, evidence_rows: list, files_by_evidence: dict, analyses_by_evidence: dict) -> bytes:
    buffer = BytesIO()
    font = _font_name()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ArchiveTitle", fontName=font, fontSize=18, leading=23, textColor=colors.HexColor("#23364D"), spaceAfter=12))
    styles.add(ParagraphStyle(name="ArchiveHeading", fontName=font, fontSize=11, leading=16, textColor=colors.HexColor("#23364D"), spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="ArchiveBody", fontName=font, fontSize=9, leading=14, textColor=colors.HexColor("#243447"), spaceAfter=6))
    styles.add(ParagraphStyle(name="ArchiveSmall", fontName=font, fontSize=7, leading=11, textColor=colors.HexColor("#536274"), spaceAfter=5))
    story = [
        Paragraph("SAFE-ARCHIVE | Case report", styles["ArchiveTitle"]),
        Paragraph("Structured preservation record. This report does not certify forensic validity or legal admissibility.", styles["ArchiveSmall"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CAD3DD")),
        Spacer(1, 8),
        Paragraph("Case summary", styles["ArchiveHeading"]),
        Paragraph(f"<b>Case ID:</b> {_safe(case.id)}", styles["ArchiveBody"]),
        Paragraph(f"<b>Title:</b> {_safe(case.title)}", styles["ArchiveBody"]),
        Paragraph(f"<b>Status:</b> {_safe(case.status)}", styles["ArchiveBody"]),
        Paragraph(f"<b>Created:</b> {_safe(case.created_at)}", styles["ArchiveBody"]),
        Paragraph("Victim statement", styles["ArchiveHeading"]),
        Paragraph(_safe(case.victim_statement or "No statement was provided."), styles["ArchiveBody"]),
        Paragraph("Evidence index", styles["ArchiveHeading"]),
    ]
    if evidence_rows:
        index = [["Evidence ID", "Platform", "Status", "Captured"]]
        for evidence in evidence_rows:
            index.append([str(evidence.id), evidence.platform, evidence.capture_status, str(evidence.capture_timestamp or "—")[:19]])
        table = Table(index, colWidths=[66 * mm, 28 * mm, 26 * mm, 47 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#CAD3DD")),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No evidence has been submitted.", styles["ArchiveBody"]))
    story.append(Paragraph("Timeline", styles["ArchiveHeading"]))
    story.append(Paragraph(f"{_safe(case.created_at)} — Case created", styles["ArchiveBody"]))
    for evidence in evidence_rows:
        story.append(Paragraph(f"{_safe(evidence.created_at)} — Evidence {_safe(evidence.id)} submitted", styles["ArchiveBody"]))
        if evidence.capture_timestamp:
            story.append(Paragraph(f"{_safe(evidence.capture_timestamp)} — Public page captured", styles["ArchiveBody"]))
    for evidence in evidence_rows:
        block = [
            Paragraph(f"Evidence {_safe(evidence.id)}", styles["ArchiveHeading"]),
            Paragraph(f"<b>Original URL:</b> {_safe(evidence.original_url, 2048)}", styles["ArchiveBody"]),
            Paragraph(f"<b>Platform:</b> {_safe(evidence.platform)} | <b>Capture status:</b> {_safe(evidence.capture_status)}", styles["ArchiveBody"]),
            Paragraph(f"<b>Capture timestamp:</b> {_safe(evidence.capture_timestamp)}", styles["ArchiveBody"]),
            Paragraph(f"<b>Evidence package SHA-256:</b> {_safe(evidence.hash_sha256)}", styles["ArchiveSmall"]),
            Paragraph(f"<b>Page title:</b> {_safe(evidence.page_title)}", styles["ArchiveBody"]),
            Paragraph(f"<b>Visible author:</b> {_safe(evidence.visible_author)}", styles["ArchiveBody"]),
            Paragraph(f"<b>Visible timestamp:</b> {_safe(evidence.visible_timestamp)}", styles["ArchiveBody"]),
            Paragraph("Visible text excerpt", styles["ArchiveHeading"]),
            Paragraph(_safe(evidence.visible_text or "No visible text captured.", 5000), styles["ArchiveBody"]),
        ]
        story.append(KeepTogether(block[:5]))
        story.extend(block[5:])
        story.append(Paragraph("Preserved files", styles["ArchiveHeading"]))
        for item in files_by_evidence.get(evidence.id, []):
            story.append(Paragraph(f"{_safe(item.file_type)} · {item.size} bytes · SHA-256 {_safe(item.hash_sha256)}", styles["ArchiveSmall"]))
        analyses = analyses_by_evidence.get(evidence.id, [])
        if analyses:
            story.append(Paragraph("AI assistance — derived material, requires human review", styles["ArchiveHeading"]))
            for analysis in analyses:
                story.append(Paragraph(f"<b>Model:</b> {_safe(analysis.model_name)} | <b>Generated:</b> {_safe(analysis.created_at)}", styles["ArchiveSmall"]))
                story.append(Paragraph(_safe(analysis.summary), styles["ArchiveBody"]))
                story.append(Paragraph(f"<b>Suggested tags:</b> {_safe(', '.join(analysis.tags))}", styles["ArchiveSmall"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#536274"))
        canvas.drawString(20 * mm, 13 * mm, "SAFE-ARCHIVE • Structured preservation, not forensic certification")
        canvas.drawRightString(190 * mm, 13 * mm, f"Page {document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=22 * mm)
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
