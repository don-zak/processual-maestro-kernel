"""CGT Governor — PDF Report Generator

Generates governance PDF reports using ReportLab with English and Arabic support.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_governance_pdf(
    evaluation: dict,
    language: str = "en",
    signature: str | None = None,
) -> bytes:
    """Generate a PDF governance report for a single evaluation.

    Args:
        evaluation: dict with keys: rank, reward, policy, policy_label,
                    policy_description, fate_vector (dict), repair_prompt (optional).
        language: "en" for English, "ar" for Arabic.
        signature: SHA3-256 signature to embed in the footer.

    Returns:
        PDF content as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    is_ar = language == "ar"

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#16213e"),
    )
    normal_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        leading=14,
    )
    label_style = ParagraphStyle(
        "LabelStyle",
        parent=normal_style,
        textColor=colors.HexColor("#555555"),
        fontSize=9,
    )
    signature_style = ParagraphStyle(
        "Signature",
        parent=normal_style,
        fontSize=7,
        textColor=colors.HexColor("#888888"),
        spaceBefore=8,
    )

    # ── PDF document metadata ──
    title = "تقرير حوكمة CGT" if is_ar else "CGT Governance Report"
    rank = evaluation.get("rank", "—")
    doc.title = title
    doc.author = "Processual Maestro Kernel v2.0.0"
    doc.subject = f"CGT Governance Report — {rank}"

    elements = []

    # ── Title ──
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 2 * mm))

    # ── Meta info ──
    ts = evaluation.get("ts", datetime.now(UTC).isoformat())
    lang_label = "العربية" if is_ar else "English"
    elements.append(
        Paragraph(
            f"<b>{'التاريخ' if is_ar else 'Date'}:</b> {ts} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>{'اللغة' if is_ar else 'Language'}:</b> {lang_label}",
            label_style,
        )
    )
    elements.append(Spacer(1, 4 * mm))

    # ── Rank / Reward / Policy ──
    reward = evaluation.get("reward", 0)
    policy = evaluation.get("policy_label", evaluation.get("policy", "—"))

    rank_label = "الرتبة الوجودية" if is_ar else "Existence Rank"
    reward_label = "المكافأة" if is_ar else "Reward"
    policy_label = "السياسة" if is_ar else "Policy"

    meta_data = [
        [Paragraph(f"<b>{rank_label}:</b>", label_style), Paragraph(rank, normal_style)],
        [Paragraph(f"<b>{reward_label}:</b>", label_style), Paragraph(str(reward), normal_style)],
        [Paragraph(f"<b>{policy_label}:</b>", label_style), Paragraph(policy, normal_style)],
    ]
    meta_table = Table(meta_data, colWidths=[55 * mm, 120 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 4 * mm))

    # ── Fate Vector Table ──
    fate = evaluation.get("fate_vector", {})
    fate_header = "متجه المصير" if is_ar else "Fate Vector"

    elements.append(Paragraph(fate_header, heading_style))

    en_labels = {
        "stability": "Stability",
        "hybridity": "Hybridity",
        "distortion": "Distortion",
        "extinction": "Extinction",
        "collapse": "Collapse",
        "flourishing": "Flourishing",
        "transient": "Transient",
    }
    ar_labels = {
        "stability": "الاستقرار",
        "hybridity": "الهجينة",
        "distortion": "التشويه",
        "extinction": "الانقراض",
        "collapse": "الانهيار",
        "flourishing": "الازدهار",
        "transient": "العابر",
    }
    labels = ar_labels if is_ar else en_labels

    table_data = [["", ""]]
    table_data[0][0] = labels.get("stability", "Stability")
    table_data[0][1] = labels.get("transient", "Transient")
    for key, en_name in en_labels.items():
        val = fate.get(key, 0)
        label = labels.get(key, en_name)
        table_data.append([Paragraph(label, normal_style), f"{val:.4f}"])

    fate_table = Table(table_data, colWidths=[80 * mm, 80 * mm])
    fate_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f5")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(fate_table)
    elements.append(Spacer(1, 4 * mm))

    # ── Repair Prompt ──
    repair = evaluation.get("repair_prompt")
    if repair:
        repair_header = "مطالبة الإصلاح" if is_ar else "Repair Prompt"
        elements.append(Paragraph(repair_header, heading_style))
        elements.append(Paragraph(repair, normal_style))
        elements.append(Spacer(1, 4 * mm))

    # ── Signature Footer ──
    if signature:
        sig_label = "توقيع SHA3-256" if is_ar else "SHA3-256 Signature"
        elements.append(
            Paragraph(
                f"<b>{sig_label}:</b><br/>{signature}",
                signature_style,
            )
        )
        elements.append(
            Paragraph(
                "مشفّر بـ Processual Crypto Envelope v2.0.0 — للتحقق من المصداقية"
                if is_ar
                else "Signed with Processual Crypto Envelope v2.0.0 — verify for authenticity",
                signature_style,
            )
        )

    doc.build(elements)
    return buf.getvalue()
