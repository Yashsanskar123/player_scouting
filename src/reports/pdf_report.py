"""PDF reports (reportlab platypus). Inputs are the same dicts the API endpoints return."""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.reports.common import DISCLAIMER, generated_stamp, money, number, pdf_safe, percentile_label, season_label

NAVY, ACCENT, GREY, LIGHT = colors.HexColor("#0B1F3A"), colors.HexColor("#1F6FEB"), colors.HexColor("#5B6777"), colors.HexColor("#EEF2F7")
_styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_styles["Title"], fontSize=20, leading=24, textColor=NAVY, alignment=0, spaceAfter=2)
SUB = ParagraphStyle("sub", parent=_styles["Normal"], fontSize=9.5, textColor=GREY, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=_styles["Heading2"], fontSize=12, textColor=NAVY, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("body", parent=_styles["Normal"], fontSize=9, leading=12)
SMALL = ParagraphStyle("small", parent=_styles["Normal"], fontSize=7.5, leading=10, textColor=GREY)
CELL = ParagraphStyle("cell", parent=_styles["Normal"], fontSize=8.5, leading=11)


def _p(text, style=BODY):
    return Paragraph(pdf_safe(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def _table(data, widths, header=True, zebra=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
             ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DBE3"))]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def _kpi_strip(items: list[tuple[str, str]]):
    cells = [[Paragraph(f'<font size="7.5" color="#5B6777">{pdf_safe(k)}</font><br/><font size="12"><b>{pdf_safe(v)}</b></font>', CELL) for k, v in items]]
    t = Table(cells, colWidths=[(A4[0] - 36 * mm) / len(items)] * len(items))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DBE3")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DBE3")),
                           ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _bars(rows: list[tuple[str, float | None]], width: float = 90 * mm):
    """Horizontal 0-100 bars: [label | bar | value]."""
    data = []
    for label, value in rows:
        d = Drawing(width, 8)
        d.add(Rect(0, 1, width, 6, fillColor=colors.HexColor("#E3E8EF"), strokeColor=None))
        if value is not None:
            v = max(0.0, min(100.0, float(value)))
            d.add(Rect(0, 1, width * v / 100, 6, fillColor=ACCENT if v >= 50 else colors.HexColor("#E5A13A"), strokeColor=None))
        data.append([_p(label, CELL), d, number(value, 0)])
    t = Table(data, colWidths=[58 * mm, width + 2 * mm, 12 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 10 * mm, f"ScoutIQ · {doc.title}")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build(title: str, story: list) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=pdf_safe(title), author="ScoutIQ")
    story += [Spacer(1, 8), _p(DISCLAIMER, SMALL)]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


COMPONENTS = [("component_attacking", "Attacking"), ("component_chance_creation", "Chance creation"), ("component_passing", "Passing"),
              ("component_progression", "Progression"), ("component_defending", "Defending"), ("component_physical", "Physical"),
              ("component_goalkeeping", "Goalkeeping")]


# Outfield attacking/chance-creation numbers are not meaningful for goalkeepers.
GK_COMPONENTS = {"component_goalkeeping", "component_passing", "component_physical"}
GK_PERCENTILES = {"performance_saves", "performance_savepct", "performance_cspct", "total_cmp", "total_cmppct", "long_cmppct", "clr", "crs_pa"}


def player_report_pdf(player: dict, percentiles: dict | None, history: list | None, tm: dict | None, season: int | None) -> bytes:
    name = player.get("short_name") or "Player"
    story = [_p(name, H1),
             _p(f"{player.get('canonical_position') or player.get('player_positions') or '—'} · {player.get('club_name') or '—'} · {player.get('league_name') or '—'} · "
                f"Age {number(player.get('age_fifa'), 0)} · {player.get('nationality_name') or '—'} · Season {season_label(season or player.get('season'))}", SUB),
             _kpi_strip([("Performance", number(player.get("performance_score"))), ("Development potential", number(player.get("development_potential"))),
                         ("Expected in 12 months", number(player.get("expected_performance_12m"))), ("Market value", money(player.get("value_eur"))),
                         ("Fair value", money(player.get("fair_value_eur"))), ("Value gap", number(player.get("value_gap_pct"), 0, "%"))])]

    is_gk = str(player.get("canonical_position") or player.get("player_positions") or "").upper().startswith("GK")
    comps = [(label, player.get(key)) for key, label in COMPONENTS
             if player.get(key) is not None and (not is_gk or key in GK_COMPONENTS)]
    if comps:
        story += [_p("Performance profile (0-100)", H2), _bars(comps)]

    pct = {k: v for k, v in (percentiles or {}).items()
           if v is not None and (not is_gk or k.removeprefix("per_90_minutes_") in GK_PERCENTILES)}
    if pct:
        ranked = sorted(pct.items(), key=lambda kv: kv[1], reverse=True)
        n = min(5, len(ranked) // 2) or 1
        top, low = ranked[:n], list(reversed(ranked[-n:]))
        story += [_p("Peer percentiles (versus same position and season)", H2),
                  _table([["Strongest", "Pctl", "Weakest", "Pctl"]] + [[percentile_label(a[0]), number(a[1], 0), percentile_label(b[0]), number(b[1], 0)]
                                                                      for a, b in zip(top, low + [("", None)] * (len(top) - len(low)))],
                         [60 * mm, 18 * mm, 60 * mm, 18 * mm])]

    hist = sorted(history or [], key=lambda r: r.get("season") or 0)
    if hist:
        story += [_p("Season history", H2),
                  _table([["Season", "Club", "Min", "Perf.", "Potential", "Value"]] +
                         [[season_label(r.get("season")), pdf_safe(r.get("club_name"))[:28], number(r.get("playing_time_min"), 0), number(r.get("performance_score")),
                           number(r.get("development_potential")), money(r.get("value_eur"))] for r in hist[-8:]],
                         [22 * mm, 56 * mm, 18 * mm, 18 * mm, 24 * mm, 28 * mm])]

    if tm and tm.get("available"):
        c, m, pr = tm.get("contract") or {}, tm.get("market") or {}, tm.get("profile") or {}
        story += [_p("Contract and market (Transfermarkt, current snapshot)", H2),
                  _table([["Contract ends", "Status", "TM value", "% of peak", "12-month change", "Current club"],
                          [c.get("expires") or "—", pdf_safe(c.get("status")), money(m.get("current_value_eur")), number(m.get("pct_of_peak"), 0, "%"),
                           number(m.get("change_12m_pct"), 1, "%"), pdf_safe(pr.get("current_club"))[:24]]],
                         [26 * mm, 40 * mm, 22 * mm, 20 * mm, 28 * mm, 38 * mm], zebra=False),
                  _p("Transfermarkt data is a point-in-time snapshot and may differ from the selected season's club.", SMALL)]

    notes = []
    if "exploratory" in str(player.get("potential_projection_status", "")).lower():
        notes.append("Potential, breakout and decline projections are exploratory and not yet validated by backtests.")
    notes.append(f"Sample reliability: {player.get('sample_reliability_tier') or '—'} ({number(player.get('sample_reliability_score'), 0)}/100). "
                 f"Recruitment risk: {player.get('recruitment_risk_tier') or '—'} ({number(player.get('recruitment_risk_score'), 0)}/100).")
    story += [_p("Evidence and caveats", H2)] + [_p("• " + n) for n in notes]
    return _build(f"{name} - scouting report", story)


def club_report_pdf(overview: dict) -> bytes:
    profile = overview.get("profile") or {}
    club = profile.get("club_name") or "Club"
    story = [_p(f"{club} - squad report", H1),
             _p(f"{overview.get('league_name') or '—'} · Formation {profile.get('formation') or '—'} · Season {season_label(overview.get('season'))}", SUB),
             _kpi_strip([("Squad size", str(overview.get("roster_size", "—"))), ("Average age", number(overview.get("average_age"))),
                         ("Avg performance", number(overview.get("average_performance"))), ("Squad value", money(overview.get("squad_market_value_eur"))),
                         ("Transfer budget", money(profile.get("transfer_budget_eur")) if profile.get("transfer_budget_eur") is not None else "Not set")])]
    positions = overview.get("positions") or {}
    if positions:
        story += [_p("Squad by position", H2), _table([["Position", "Players"]] + [[k, str(v)] for k, v in positions.items()], [40 * mm, 25 * mm])]
    prio = overview.get("recruitment_priorities") or []
    if prio:
        story += [_p("Top recruitment priorities", H2)] + [_p(f"• [{p.get('severity', '')}] {p.get('category', '')}: {p.get('need', '')}") for p in prio]
    co = overview.get("contract_outlook") or {}
    if co.get("available"):
        b = co.get("buckets", {})
        story += [_p("Contract outlook", H2),
                  _table([["< 6 months", "6-12 months", "1-2 years", "2+ years", "Expired", "No data"],
                          [str(b.get("within_6m", 0)), str(b.get("within_12m", 0)), str(b.get("within_24m", 0)), str(b.get("longer", 0)),
                           str(b.get("expired_or_unrenewed", 0)), str(b.get("unknown", 0))]], [28 * mm] * 6, zebra=False)]
        exp = co.get("expiring_within_12m") or []
        if exp:
            story += [Spacer(1, 4), _table([["Player", "Pos", "Contract ends", "Months left", "TM value"]] +
                                           [[pdf_safe(e.get("short_name")), e.get("canonical_position") or "—", e.get("contract_expires") or "—",
                                             number(e.get("contract_months_left")), money(e.get("tm_value_eur"))] for e in exp[:12]],
                                           [50 * mm, 18 * mm, 32 * mm, 26 * mm, 28 * mm])]
        story += [_p(co.get("note", ""), SMALL)]
    story += [_p(f"Generated {generated_stamp()}", SMALL)]
    return _build(f"{club} - squad report", story)
