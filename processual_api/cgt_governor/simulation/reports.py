"""CGT Governor — Supervision PDF Report Generator."""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .agents import ALL_AGENTS
from .engine import SimulationResult


def generate_supervision_pdf(
    report: SimulationResult,
    signature: str | None = None,
) -> bytes:
    """Generate a supervision PDF from a simulation result.

    Args:
        report: The SimulationResult to render.
        signature: SHA3-256 signature to embed in footer.

    Returns:
        PDF content as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
    )

    title_style = ParagraphStyle("SupTitle", fontSize=16, spaceAfter=4, textColor=colors.HexColor("#1a1a2e"))
    h2 = ParagraphStyle("SupH2", fontSize=12, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#16213e"))
    h3 = ParagraphStyle("SupH3", fontSize=10, spaceBefore=6, spaceAfter=2, textColor=colors.HexColor("#0f3460"))
    normal = ParagraphStyle("SupNormal", fontSize=9, spaceAfter=3, leading=13)
    small = ParagraphStyle("SupSmall", fontSize=7, textColor=colors.HexColor("#888888"), spaceBefore=6)
    tiny = ParagraphStyle("SupTiny", fontSize=6, textColor=colors.HexColor("#aaaaaa"))

    elements = []

    # ── Title ──
    elements.append(Paragraph("CGT Supervision Report", title_style))
    elements.append(Paragraph(f"Generated: {report.ts}", small))
    elements.append(Spacer(1, 3 * mm))

    # ── Summary stats ──
    elements.append(Paragraph("Summary", h2))
    risk_label = f"⚠ {report.risk_count} agent(s) at risk" if report.risk_count else "✓ All agents stable"
    summary_rows = [
        ["Total agents evaluated", str(len(report.evaluations))],
        ["Average reward", f"{report.avg_reward:+.4f}"],
        ["Risk level", risk_label],
    ]
    st = Table(summary_rows, colWidths=[70 * mm, 100 * mm])
    st.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elements.append(st)
    elements.append(Spacer(1, 3 * mm))

    # ── Rank distribution bar chart (text version) ──
    elements.append(Paragraph("Rank Distribution", h2))

    rank_color_map = {
        "flourishing": colors.HexColor("#27ae60"),
        "stable": colors.HexColor("#2980b9"),
        "hybrid": colors.HexColor("#f39c12"),
        "distorted": colors.HexColor("#e67e22"),
        "transient": colors.HexColor("#95a5a6"),
        "extinct": colors.HexColor("#e74c3c"),
    }
    rank_emoji = {
        "flourishing": "✦",
        "stable": "✓",
        "hybrid": "⟳",
        "distorted": "△",
        "transient": "↧",
        "extinct": "✕",
    }

    total = len(report.evaluations) or 1
    dist_data = [["Rank", "Count", "Distribution"]]
    ordered_ranks = ["flourishing", "stable", "hybrid", "distorted", "transient", "extinct"]
    for r in ordered_ranks:
        cnt = report.rank_distribution.get(r, 0)
        if cnt == 0:
            continue
        bar_len = max(1, int(40 * cnt / total))
        color = rank_color_map.get(r, colors.black)
        emj = rank_emoji.get(r, " ")
        dist_data.append(
            [
                Paragraph(f"{emj} <font color='#{color.hexval()[:6]}'><b>{r.title()}</b></font>", normal),
                str(cnt),
                f"{'█' * bar_len} ({cnt})",
            ]
        )

    dt = Table(dist_data, colWidths=[50 * mm, 20 * mm, 100 * mm])
    dt.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f5")),
                ("GRID", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(dt)
    elements.append(Spacer(1, 4 * mm))

    # ── Per-agent cards ──
    elements.append(Paragraph("Agent Evaluations", h2))

    for i, ev in enumerate(report.evaluations):
        agent = ev.agent

        # Rank badge
        rank_color = rank_color_map.get(ev.rank, colors.grey)
        emj = rank_emoji.get(ev.rank, " ")

        elements.append(
            Paragraph(
                f"[{i + 1}] <b>{agent.name}</b> <i>({agent.role})</i> — "
                f"<font color='#{rank_color.hexval()[:6]}'>{emj} {ev.rank.title()}</font>",
                h3,
            )
        )

        card_rows = [
            ["Scenario", ev.scenario_title],
            ["Language", agent.language.upper()],
            ["Reward", f"{ev.reward:+.4f}"],
            ["Policy", ev.policy_label],
        ]
        # Fate vector
        for key in ("stability", "distortion", "extinction", "flourishing"):
            val = ev.fate_vector.get(key, 0)
            card_rows.append([f"Fate: {key.title()}", f"{val:.4f}"])

        ct = Table(card_rows, colWidths=[45 * mm, 125 * mm])
        ct.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.3, colors.HexColor("#dddddd")),
                ]
            )
        )
        elements.append(ct)

        # Repair prompt if applicable
        if ev.repair_prompt:
            elements.append(
                Paragraph(
                    f"<i>Repair: {ev.repair_prompt[:120]}...</i>",
                    ParagraphStyle(
                        "RepairText", parent=normal, fontSize=7, textColor=colors.HexColor("#666666"), leftIndent=4 * mm
                    ),
                )
            )

        elements.append(Spacer(1, 2 * mm))

    # ── Recommendations ──
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("Recommendations", h2))

    recs = []
    best_agent_id = report.highest_agent
    worst_agent_id = report.lowest_agent

    for agent in ALL_AGENTS:
        if agent.agent_id == worst_agent_id:
            recs.append(
                f"⚠ <b>{agent.name}</b> ({agent.role}) — requires immediate "
                f"retraining or removal from production. "
                f"Reward: {report.avg_reward:.2f} (lowest)."
            )
        elif agent.agent_id == best_agent_id:
            recs.append(
                f"✓ <b>{agent.name}</b> ({agent.role}) — performing well. Consider expanding to more scenarios."
            )

    if report.risk_count > 0:
        recs.append(
            f"⚠ {report.risk_count} of {len(report.evaluations)} agents are at risk "
            f"(distorted or extinct). Review and re-train before production deployment."
        )

    if not recs:
        recs.append("All agents performing within acceptable thresholds.")

    for rec in recs:
        elements.append(Paragraph(rec, normal))

    # ── Signature ──
    if signature:
        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(
                f"<b>SHA3-256 Signature:</b><br/>{signature}",
                tiny,
            )
        )
        elements.append(
            Paragraph(
                "Signed with Processual Crypto Envelope v2.0.0",
                tiny,
            )
        )

    doc.build(elements)
    return buf.getvalue()
