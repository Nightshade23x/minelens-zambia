"""Render source-cited MineLens project briefs as PDFs.

Read-only. Input is the verified output of app.project_comparison_data.load_comparison.
Never calls Ollama, the network, router, or data ingestion. Unsupported values
are not inferred and user notes are visibly separated from source-derived facts.
"""
from __future__ import annotations

from datetime import date
from html import escape
from io import BytesIO
from typing import Mapping
import unicodedata

from app.project_comparison_data import Claim

SNAPSHOT_DATE = "19 November 2026"
MAX_NOTE_CHARS = 1200
MAX_TITLE_CHARS = 110


def _plain(value: object) -> str:
    """Keep text readable in the PDF core fonts without bundling font files."""
    raw = str(value or "")
    subs = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2212": "-", "\u2248": "~",
        "\u223c": "~", "\u2265": ">=", "\u2264": "<=", "\u00a0": " ",
        "\u2022": "-", "\u2026": "...", "\ufb01": "fi", "\ufb02": "fl",
    }
    for old, new in subs.items():
        raw = raw.replace(old, new)
    return unicodedata.normalize("NFKD", raw).encode("latin-1", "replace").decode("latin-1")


def _p(value: object) -> str:
    return escape(_plain(value), quote=True)


def prepare_report(
    projects: Mapping[str, dict],
    selected: list[str],
    *,
    report_title: str = "Zambia Mining | Project Research Brief",
    analyst_notes: str = "",
) -> dict:
    """Validate scope and create claim-numbered report data without mutating inputs."""
    if not selected:
        raise ValueError("Select at least one project")
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate project selection")
    if len(selected) > 3:
        raise ValueError("This report supports up to three projects")
    if any(name not in projects for name in selected):
        raise ValueError("Unknown project in report selection")
    title = str(report_title).strip()
    if not title or len(title) > MAX_TITLE_CHARS:
        raise ValueError("Report title must be 1-110 characters")
    notes = str(analyst_notes or "").strip()
    if len(notes) > MAX_NOTE_CHARS:
        raise ValueError("Notes are limited to 1200 characters")
    entries: list[dict] = []
    register: list[dict] = []
    counter = 1
    for name in selected:
        project = projects[name]
        claims = project.get("claims", [])
        capex = [c for c in claims if c.kind == "capex"]
        capacity = [c for c in claims if c.kind == "capacity"]
        historical = [c for c in claims if c.kind == "historical"]
        if len(capex) != 2 or len(capacity) != 1:
            raise ValueError(f"Incomplete verified evidence for {name}")
        if not all(isinstance(c, Claim) for c in claims):
            raise ValueError(f"Invalid claim objects for {name}")
        ids = {}
        for claim in claims:
            if claim.project != name or not claim.excerpt or not claim.document or not claim.pages:
                raise ValueError(f"Incomplete claim provenance for {name}")
            if claim.kind == "capex" and claim.usd_billions is None:
                raise ValueError(f"Missing estimate amount for {name}")
            if claim.kind == "capacity" and claim.capacity_tpa is None:
                raise ValueError(f"Missing capacity for {name}")
            ids[id(claim)] = counter
            register.append({"n": counter, "claim": claim})
            counter += 1
        entries.append({
            "name": name,
            "developer": project["developer"],
            "commodity": project["commodity"],
            "capex": capex,
            "capacity": capacity[0],
            "historical": historical,
            "ids": ids,
        })
    return {
        "title": title,
        "selected": tuple(selected),
        "notes": notes,
        "entries": entries,
        "references": register,
    }


def generate_project_report_pdf(
    projects: Mapping[str, dict],
    selected: list[str],
    *,
    report_title: str = "Zambia Mining | Project Research Brief",
    analyst_notes: str = "",
    generated_on: date | None = None,
) -> bytes:
    """Return an A4 PDF that explicitly separates estimated, potential, and actual data.

    Requires the optional reportlab dependency: pip install -r requirements-report.txt
    """
    report = prepare_report(
        projects, selected, report_title=report_title, analyst_notes=analyst_notes
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, Flowable,
    )

    NAVY = colors.HexColor("#15304A")
    INK = colors.HexColor("#233142")
    BLUE = colors.HexColor("#2C80B8")
    LIGHT = colors.HexColor("#EBF3F8")
    BORDER = colors.HexColor("#DCE5EC")
    MUTED = colors.HexColor("#60758A")
    AMBER = colors.HexColor("#FFF3D8")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MLTitle", fontName="Helvetica-Bold", fontSize=20, leading=26,
        textColor=NAVY, spaceAfter=9,
    ))
    styles.add(ParagraphStyle(
        name="MLSub", fontName="Helvetica", fontSize=10, leading=15,
        textColor=MUTED, spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="MLH1", fontName="Helvetica-Bold", fontSize=13, leading=18,
        textColor=NAVY, spaceBefore=14, spaceAfter=8, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="MLH2", fontName="Helvetica-Bold", fontSize=11, leading=15,
        textColor=NAVY, spaceBefore=13, spaceAfter=6, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="MLBody", fontName="Helvetica", fontSize=9, leading=14,
        textColor=INK, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="MLSmall", fontName="Helvetica", fontSize=8, leading=12,
        textColor=INK, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="MLMuted", fontName="Helvetica", fontSize=8, leading=12,
        textColor=MUTED, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="MLTable", fontName="Helvetica", fontSize=8, leading=11,
        textColor=INK,
    ))

    buf = BytesIO()
    page_w, page_h = A4
    left = 19 * mm
    right = 19 * mm
    usable = page_w - left - right
    bottom = 19 * mm
    top = 23 * mm

    doc = BaseDocTemplate(
        buf, pagesize=A4, leftMargin=left, rightMargin=right,
        topMargin=top, bottomMargin=bottom,
        title=_plain(report["title"]), author="MineLens Zambia",
        subject="Source-cited research snapshot, not a live mine-status report",
        pageCompression=1,
    )
    frame = Frame(left, bottom, usable, page_h - bottom - top,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def decorate(canvas, page_doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, page_h - 9 * mm, page_w, 9 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.white)
        canvas.drawString(left, page_h - 6 * mm, "MINELENS  /  ZAMBIA MINING INTELLIGENCE")
        canvas.setStrokeColor(BORDER)
        canvas.line(left, 14 * mm, page_w - right, 14 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(left, 10 * mm, "Evidence snapshot: " + SNAPSHOT_DATE)
        canvas.drawRightString(page_w - right, 10 * mm, f"Page {page_doc.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=decorate)])
    story = []
    text = lambda value, style="MLBody": Paragraph(_p(value), styles[style])
    rich = lambda value, style="MLBody": Paragraph(value, styles[style])

    def table(rows, widths=None):
        rendered = [
            [rich(f"<b>{_p(cell)}</b>", "MLTable") if r == 0 else text(cell, "MLTable")
             for cell in row]
            for r, row in enumerate(rows)
        ]
        obj = Table(rendered, colWidths=widths, hAlign="LEFT", repeatRows=1, splitByRow=1)
        obj.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, BORDER),
            ("LINEBELOW", (0, 1), (-1, -1), 0.35, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return obj

    class HorizontalBars(Flowable):
        def __init__(self, entries, metric):
            super().__init__()
            self.entries = entries
            self.metric = metric
            self.width = usable
            self.height = 25 + 38 * len(entries)

        def draw(self):
            canvas = self.canv
            chart_x = 94
            chart_end = self.width - 88
            max_width = chart_end - chart_x
            max_value = max((entry["capex"][0].usd_billions if self.metric == "capex"
                             else entry["capacity"].capacity_tpa)
                            for entry in self.entries) * 1.07
            for i, entry in enumerate(self.entries):
                y = self.height - 31 - i * 38
                value = (entry["capex"][0].usd_billions if self.metric == "capex"
                         else entry["capacity"].capacity_tpa)
                label = (f"${value:.2f}B" if self.metric == "capex"
                         else f"{value:,} tpa")
                canvas.setFont("Helvetica-Bold", 8.6)
                canvas.setFillColor(INK)
                canvas.drawString(0, y + 5, entry["name"])
                canvas.setFillColor(LIGHT)
                canvas.roundRect(chart_x, y, max_width, 16, 4, stroke=0, fill=1)
                canvas.setFillColor(BLUE)
                canvas.roundRect(chart_x, y, max(3, max_width * value / max_value),
                                 16, 4, stroke=0, fill=1)
                canvas.setFillColor(NAVY)
                canvas.drawRightString(self.width - 2, y + 5, label)

    generated = generated_on if generated_on is not None else date.today()
    story.append(rich(_p(report["title"]), "MLTitle"))
    story.append(text(
        f"Projects: {', '.join(report['selected'])}  |  Source snapshot: {SNAPSHOT_DATE}  |  "
        f"PDF generated: {generated.isoformat()}", "MLSub"
    ))
    story.append(rich("<b>Research scope.</b> This brief summarizes reported estimates and historical figures "
                      "from the saved MineLens source snapshot. It is not a live status update, "
                      "a feasibility assessment, or investment advice."))
    story.append(rich("<b>Executive summary</b>", "MLH1"))
    for entry in report["entries"]:
        c1, c2 = entry["capex"]
        cap = entry["capacity"]
        a, b, k = entry["ids"][id(c1)], entry["ids"][id(c2)], entry["ids"][id(cap)]
        story.append(rich(
            f"<b>{_p(entry['name'])}:</b> {_p(entry['developer'])}; "
            f"reported investment {_p(c1.value)} [{a}] versus {_p(c2.value)} [{b}]; "
            f"announced capacity/potential {_p(cap.value)} [{k}].",
            "MLBody"
        ))

    if report["notes"]:
        story.append(rich("<b>Analyst notes (user-supplied; not verified)</b>", "MLH1"))
        story.append(text(report["notes"]))

    story.append(rich("<b>Reported CapEx - declaration estimates</b>", "MLH1"))
    story.append(text(
        "USD billions. Bars show the 2026 country's compact declaration only. "
        "They do not show final cost or actual expenditure.", "MLMuted"
    ))
    story.append(HorizontalBars(report["entries"], "capex"))
    if "Mingomba" in report["selected"]:
        story.append(rich(
            "<b>Material qualification:</b> Mingomba's declaration says expected $2 billion; "
            "the annex says greater than $2.0B. The chart uses the declaration value only. "
            "The annex is a strict lower bound, not an exact estimate.", "MLSmall"
        ))
    story.append(rich("<b>Announced copper capacity or potential</b>", "MLH1"))
    story.append(text(
        "Tonnes per year (tpa) from 2026 statements. These are expansion targets or "
        "production potential, not 2024 measured copper output.", "MLMuted"
    ))
    story.append(HorizontalBars(report["entries"], "capacity"))

    for entry in report["entries"]:
        claims = entry["capex"]
        cap = entry["capacity"]
        labels = [
            ["Field", "Source-reported detail"],
            ["Developer / commodity", f"{entry['developer']} / {entry['commodity']}"],
            ["CapEx - declaration", f"{claims[0].value}  [{entry['ids'][id(claims[0])]}]"],
            ["CapEx - annex", f"{claims[1].value}  [{entry['ids'][id(claims[1])]}]"],
            ["Announced capacity / potential", f"{cap.value}  [{entry['ids'][id(cap)]}]"],
        ]
        if entry["historical"]:
            for hist in entry["historical"]:
                labels.append(["2024 source-reported output",
                               f"{hist.value}  [{entry['ids'][id(hist)]}]"])
        else:
            labels.append(["2024 source-reported output", "Not established in selected evidence"])
        detail_blocks = [
            rich(f"<b>{_p(entry['name'])}</b>", "MLH2"),
            table(labels, widths=[usable * .32, usable * .68]),
        ]
        if entry is report["entries"][0]:
            # Keep the section heading with the first detail table, not alone
            # at the end of the chart page.
            detail_blocks.insert(0, rich("<b>Project detail and historical output</b>", "MLH1"))
        story.append(KeepTogether(detail_blocks))
    story.append(Spacer(1, 9))
    story.append(KeepTogether([rich(
        "<b>Comparison cautions.</b> Copper concentrates and copper cathode are different "
        "product categories and should not be added together or compared directly "
        "with announced annual capacity. Two CapEx claims from pages 8 and 25-26 of "
        "the same compact are <b>not</b> independent confirmations. The compact's "
        "declaration describes expansions as in progress while the annex labels "
        "Kansanshi and Lumwana expansions completed; neither passage verifies current status.",
        "MLSmall"
    )]))

    # Single-project briefs are shorter: flow the evidence register naturally,
    # avoiding a nearly empty orphan page before the source appendix.
    if len(report["entries"]) > 1:
        story.append(PageBreak())
    story.append(rich("<b>Evidence register</b>", "MLH1"))
    story.append(text(
        "Bracketed numbers in this report identify specific project claims below. "
        "They are stable within this PDF and are not the session-scoped [S1] IDs "
        "from MineLens search responses.", "MLMuted"
    ))
    for record in report["references"]:
        c: Claim = record["claim"]
        number = record["n"]
        source = (f"[{number}] {c.project} - {c.kind}: {c.value}")
        detail = f"{c.source_title} | {c.document} | p. {c.pages}"
        if c.source_date:
            detail += " | source date " + c.source_date
        entry_bits = [
            rich(f"<b>{_p(source)}</b>", "MLSmall"),
            text(detail, "MLMuted"),
            text(c.excerpt, "MLSmall"),
        ]
        if c.source_url:
            entry_bits.append(rich(
                f'<link href="{_p(c.source_url)}" color="#2C80B8">Open recorded source URL</link>',
                "MLSmall"
            ))
        else:
            entry_bits.append(text("External URL not recorded in this snapshot; source passage is stored locally.", "MLMuted"))
        story.append(KeepTogether(entry_bits))
        story.append(Spacer(1, 6))
    story.append(rich("<b>Method and limitations</b>", "MLH1"))
    story.append(text(
        "Claims were extracted from a saved local MineLens evidence snapshot and "
        "checked against the cited source passage by the existing project comparison "
        "data layer. Figures retain reported qualifiers such as approximately, "
        "expected and greater than. Missing measurements remain missing. "
        "Document titles and page references identify provenance; a blank source URL "
        "does not imply public availability. The report does not independently "
        "verify project status, costs, production or document currency."
    ))

    doc.build(story)
    data = buf.getvalue()
    if not data.startswith(b"%PDF-") or len(data) < 2000:
        raise RuntimeError("PDF generation failed")
    return data
