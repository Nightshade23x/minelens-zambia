"""Source-backed, single-record PDF briefs for MineLens Project Intelligence.

Uses the existing typed project-intelligence catalog (USGS facility OR verified
project evidence). Never calls Ollama, the network, or ingestion. It does not
merge similar-looking records or infer current operational status, exact site
coordinates, production from capacity, or monetary totals.
"""
from __future__ import annotations

from datetime import date
from html import escape
from io import BytesIO
from typing import Any, Mapping

from app.research_report import _plain, _p, MAX_NOTE_CHARS, MAX_TITLE_CHARS


QUALIFIERS = {
    "lower_bound_strict": "Greater than (strict lower bound)",
    "approximately": "Approximately",
    "expected": "Expected",
    "estimated": "Estimated",
    "expansion target": "Expansion target",
    "production potential": "Production potential",
}


def friendly_qualifier(value: object) -> str:
    text = str(value or "").strip()
    return QUALIFIERS.get(text, text.replace("_", " ") or "Source-reported")


def _joined(value: object, missing: str = "Not established in this source") -> str:
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(x).strip() for x in value if str(x).strip())
    else:
        text = str(value or "").strip()
    return text or missing


def _url(value: object) -> str:
    text = str(value or "").strip()
    # ReportLab permits clickable hyperlinks. Only link external http(s) URLs.
    return text if text.startswith(("https://", "http://")) and not any(
        character in text for character in ('"', "'", "<", ">", "\n", "\r")
    ) else ""


def prepare_intelligence_profile(
    record: Mapping[str, Any], *, report_title: str = "MineLens | Mining Intelligence Profile",
    analyst_notes: str = "",
) -> dict[str, Any]:
    """Validate a catalog record and preserve its reported fields and source scope."""
    if not isinstance(record, Mapping):
        raise ValueError("A selected project-intelligence record is required")
    kind = record.get("kind")
    identity = str(record.get("id") or "")
    if kind == "USGS facility":
        if not identity.startswith("USGS:"):
            raise ValueError("Invalid USGS facility record ID")
    elif kind == "Verified project evidence":
        if not identity.startswith("PROJECT:"):
            raise ValueError("Invalid verified project record ID")
    else:
        raise ValueError("Unsupported project-intelligence record type")
    if not str(record.get("name") or "").strip():
        raise ValueError("The selected record has no name")
    if not str(record.get("source_title") or "").strip():
        raise ValueError("The selected record has no source title")
    if not str(record.get("source_scope") or "").strip():
        raise ValueError("The selected record lacks source limitations")

    title = str(report_title).strip()
    notes = str(analyst_notes or "").strip()
    if not 1 <= len(title) <= MAX_TITLE_CHARS:
        raise ValueError("Report title must be 1-110 characters")
    if len(notes) > MAX_NOTE_CHARS:
        raise ValueError("Analyst notes must not exceed 1200 characters")

    claims = list(record.get("claims") or [])
    capacities = list(record.get("capacity_records") or [])
    if kind == "USGS facility":
        if claims:
            raise ValueError("USGS facility records cannot include verified project claims")
        if not _url(record.get("source_url")):
            raise ValueError("USGS facility source URL missing or invalid")
    else:
        if capacities:
            raise ValueError("Project evidence cannot include USGS facility capacity records")
        if not claims:
            raise ValueError("No source-verified documentary claims available for this project")
        for number, claim in enumerate(claims, 1):
            if not isinstance(claim, dict) or not all(str(claim.get(key) or "").strip()
                for key in ("value", "document", "pages", "source_title", "excerpt")
            ):
                raise ValueError(f"Missing documentary provenance for claim {number}")
            if str(claim.get("project") or record["name"]) != record["name"]:
                raise ValueError(f"Claim {number} belongs to another project")

    return {
        "record": dict(record), "kind": kind, "title": title, "notes": notes,
        "claims": claims, "capacities": capacities,
        "sources": list(dict.fromkeys(
            [_url(record.get("source_url"))]
            + [_url(u) for u in record.get("supporting_urls") or []]
            + [_url(c.get("source_url")) for c in claims]
        )),
    }


def generate_intelligence_profile_pdf(
    record: Mapping[str, Any], *, report_title: str = "MineLens | Mining Intelligence Profile",
    analyst_notes: str = "", generated_on: date | None = None,
) -> bytes:
    """Render a sourced A4 PDF for one existing facility or verified project."""
    prepared = prepare_intelligence_profile(
        record, report_title=report_title, analyst_notes=analyst_notes,
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, KeepTogether, PageTemplate,
        Paragraph, Spacer, Table, TableStyle,
    )

    NAVY = colors.HexColor("#15304A")
    INK = colors.HexColor("#233142")
    BLUE = colors.HexColor("#2C80B8")
    LIGHT = colors.HexColor("#EBF3F8")
    BORDER = colors.HexColor("#DCE5EC")
    MUTED = colors.HexColor("#60758A")

    styles = getSampleStyleSheet()
    for name, size, leading, before, after, font, color in [
        ("MLProfileTitle", 20, 26, 0, 10, "Helvetica-Bold", NAVY),
        ("MLProfileHeading", 12, 17, 14, 7, "Helvetica-Bold", NAVY),
        ("MLProfileSub", 10, 15, 11, 6, "Helvetica-Bold", NAVY),
        ("MLProfileBody", 9, 13, 0, 7, "Helvetica", INK),
        ("MLProfileSmall", 8, 12, 0, 6, "Helvetica", INK),
        ("MLProfileMuted", 8, 12, 0, 7, "Helvetica", MUTED),
    ]:
        styles.add(ParagraphStyle(
            name=name, fontName=font, fontSize=size, leading=leading,
            spaceBefore=before, spaceAfter=after, textColor=color,
            alignment=TA_LEFT, keepWithNext=name.endswith(("Heading", "Sub")),
        ))

    def txt(value: object, style: str = "MLProfileBody") -> Paragraph:
        return Paragraph(_p(value), styles[style])

    def rich(content: str, style: str = "MLProfileBody") -> Paragraph:
        return Paragraph(content, styles[style])

    buf = BytesIO()
    page_w, page_h = A4
    left = right = 19 * mm
    bottom, top = 19 * mm, 23 * mm
    usable = page_w - left - right
    doc = BaseDocTemplate(
        buf, pagesize=A4, leftMargin=left, rightMargin=right,
        topMargin=top, bottomMargin=bottom, title=_plain(prepared["title"]),
        author="MineLens Zambia", subject="Historical source-backed mining profile, not live status",
        pageCompression=1,
    )
    frame = Frame(left, bottom, usable, page_h - bottom - top,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    r = prepared["record"]

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
        canvas.drawString(left, 10 * mm, "Source year: " + _plain(r.get("publication_year")))
        canvas.drawRightString(page_w - right, 10 * mm, f"Page {page_doc.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="profile", frames=[frame], onPage=decorate)])
    story: list[Any] = []

    def rows_table(rows: list[list[object]], widths: list[float] | None = None):
        data = [[txt(cell, "MLProfileSmall") for cell in row] for row in rows]
        tab = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1, splitByRow=1)
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("LINEBELOW", (0, 0), (-1, -1), .35, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return tab

    story.append(txt(prepared["title"], "MLProfileTitle"))
    generated = generated_on or date.today()
    story.append(txt(
        f"{r['name']} | {prepared['kind']} | Source year: {r['publication_year']} | "
        f"Generated: {generated.isoformat()}", "MLProfileMuted"
    ))
    story.append(rich(
        "<b>Research scope.</b> This PDF reorganizes a single existing MineLens catalog "
        "record. It is not a live verification, feasibility study, investment advice, "
        "or a consolidated entity record. Similar names are not automatically merged."
    ))
    story.append(rich("Record overview", "MLProfileHeading"))
    overview = [
        ["Field", "Source-reported information"],
        ["Name", r["name"]],
        ["Record type / ID", f"{prepared['kind']} / {r['id']}"],
        ["Operator / developer", _joined(r.get("operator"))],
        ["Commodity", _joined(r.get("commodities"))],
        ["Province / district", " / ".join(filter(None, [str(r.get("province") or ""), str(r.get("district") or "")])) or "Not established in this source"],
        ["Source-reported status", _joined(r.get("status"))],
        ["Facility type", _joined(r.get("feature_types"), "Not established / not applicable")],
        ["Recorded equity owners", _joined(r.get("owners"))],
        ["Location description", _joined(r.get("location_description"))],
    ]
    story.append(rows_table(overview, [usable * .34, usable * .66]))
    story.append(Spacer(1, 8))
    story.append(txt(r["source_scope"], "MLProfileSmall"))

    if r.get("map_lat") is not None or r.get("map_lon") is not None:
        story.append(rich(
            "<b>Coordinate caution:</b> Any map coordinate in the explorer is a district "
            "centroid, not an exact facility location. Coordinates are omitted from this PDF.",
            "MLProfileSmall"
        ))
    if prepared["notes"]:
        story.append(rich("Analyst notes (user-supplied; not verified)", "MLProfileHeading"))
        story.append(txt(prepared["notes"]))

    if prepared["kind"] == "USGS facility":
        story.append(rich("USGS-reported annual capacities", "MLProfileHeading"))
        story.append(txt(
            "Distinct source capacity groups only. They are not measured annual output, "
            "do not establish current plant or mine operation, and must not be added as "
            "a total. Units and product form are preserved where reported.",
            "MLProfileMuted"
        ))
        if prepared["capacities"]:
            capacity_rows = [["Commodity", "Reported capacity", "Product / form"]]
            for item in prepared["capacities"]:
                if not isinstance(item, dict):
                    raise ValueError("Unexpected capacity record")
                capacity_rows.append([
                    item.get("commodity") or "Not reported",
                    f"{item.get('capacity') if item.get('capacity') is not None else 'Not reported'} "
                    f"{item.get('capacity_unit') or '(unit not specified)'}",
                    item.get("form") or item.get("descriptor") or item.get("type") or "Not reported",
                ])
            story.append(rows_table(capacity_rows, [usable*.27, usable*.34, usable*.39]))
            story.append(Spacer(1, 8))
            for item in prepared["capacities"]:
                if item.get("capacity_notes"):
                    story.append(txt(
                        f"Capacity note ({item.get('commodity') or 'unspecified'}): "
                        f"{item['capacity_notes']}", "MLProfileSmall"
                    ))
        else:
            story.append(txt("No annual capacity was reported in the loaded structured record."))
    else:
        story.append(rich("Verified documentary claims", "MLProfileHeading"))
        story.append(txt(
            "Each numbered claim was previously checked against a saved source passage "
            "by the project-comparison data layer. Estimates, targets, strict lower "
            "bounds, and historical production are different types of evidence; do "
            "not combine them as a current total.", "MLProfileMuted"
        ))
        claim_rows = [["Ref", "Reported claim", "Qualification / source pages"]]
        for n, claim in enumerate(prepared["claims"], 1):
            claim_rows.append([
                f"[{n}]",
                f"{claim.get('label') or claim.get('kind') or 'Claim'}: {claim['value']}",
                f"{friendly_qualifier(claim.get('qualifier'))} | "
                f"{claim['source_title']} p. {claim['pages']}",
            ])
        story.append(rows_table(claim_rows, [usable*.10, usable*.48, usable*.42]))
        story.append(rich("Evidence register", "MLProfileHeading"))
        for n, claim in enumerate(prepared["claims"], 1):
            blocks = [rich(
                f"<b>[{n}] {_p(claim.get('label') or claim.get('kind') or 'Claim')}: "
                f"{_p(claim['value'])}</b>", "MLProfileSmall"
            ), txt(
                f"{claim['source_title']} | {claim['document']} | p. {claim['pages']}" +
                (f" | source date: {claim['source_date']}" if claim.get("source_date") else ""),
                "MLProfileMuted"
            ), txt(claim["excerpt"], "MLProfileSmall")]
            link = _url(claim.get("source_url"))
            if link:
                blocks.append(rich(
                    f'<link href="{escape(link, quote=True)}" color="#2C80B8">Open recorded source URL</link>',
                    "MLProfileSmall"
                ))
            else:
                blocks.append(txt(
                    "No external URL recorded for this claim; supporting passage stored locally.",
                    "MLProfileMuted"
                ))
            story.append(KeepTogether(blocks))
            story.append(Spacer(1, 5))

    story.append(rich("Source register", "MLProfileHeading"))
    story.append(txt(r["source_title"], "MLProfileSmall"))
    for source_index, link in enumerate(filter(None, prepared["sources"]), 1):
        story.append(rich(
            f'<link href="{escape(link, quote=True)}" color="#2C80B8">'
            f'Open recorded source {source_index}</link>',
            "MLProfileSmall"
        ))
    if not any(prepared["sources"]):
        story.append(txt("Source citations are documented above; no public link is recorded."))

    story.append(rich("Method and limitations", "MLProfileHeading"))
    story.append(txt(
        "This report uses pre-existing structured MineLens records. USGS operator, "
        "ownership, facility status and capacity fields are historical source statements. "
        "Project claims retain their original quotations, scope and pages. "
        "None of these data establish a live operating status. Missing facts are "
        "left missing. Capacity is not production; district centroids are not facility coordinates."
    ))
    doc.build(story)
    pdf = buf.getvalue()
    if not pdf.startswith(b"%PDF-") or b"%%EOF" not in pdf[-256:]:
        raise RuntimeError("The PDF could not be generated")
    return pdf
