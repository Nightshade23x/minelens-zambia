"""Read-only, evidence-checked comparison of three Zambian mining projects.

This file does not call Ollama or change MineLens routing. Facts are included only
when their exact project-specific supporting phrases occur in the saved document
passages. All values are source reports, not assertions of current status.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

COUNTRY_COMPACT = "zambia_metals_minerals_country_compact_2026.pdf"
USGS_YEARBOOK = "zambia_usgs_minerals_yearbook_2024.html"
DATA_PATH = Path("data/processed/project_comparison_evidence_20261119.json")


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(s)).split()).casefold()


@dataclass(frozen=True)
class Claim:
    project: str
    kind: str
    label: str
    value: str
    document: str
    pages: str
    excerpt: str
    source_title: str
    source_date: str
    source_url: str
    usd_billions: float | None = None
    capacity_tpa: int | None = None
    qualifier: str = ""


# Narrow source anchors include both the project name and its reported value.
# Exact source phrases are checked against the user's retrieved document passages.
FACTS = {
    "Kansanshi": {
        "developer": "First Quantum Minerals",
        "commodity": "Copper",
        "capex": (
            ("approximately $1.25 billion", 1.25, "approximately",
             COUNTRY_COMPACT, "8",
             "Kansanshi mine (approximately $1.25 billion CapEx), expanding to 200,000 tonnes per year"),
            ("approximately $1.25B", 1.25, "approximately",
             COUNTRY_COMPACT, "25-26",
             "Kansanshi Copper First Quantum Minerals Expansion to 200ktpa completed; mine life extension ∼$1.25B"),
        ),
        "capacity": (200000, "expansion target", COUNTRY_COMPACT, "8",
                     "Kansanshi mine (approximately $1.25 billion CapEx), expanding to 200,000 tonnes per year"),
        "historical": (
            ("136,007 t copper concentrates; 34,922 t copper cathode", USGS_YEARBOOK, "1",
             "Kansanshi Mine produced 136,007 t of copper concentrates and 34,922 t of copper cathode."),
        ),
    },
    "Lumwana": {
        "developer": "Barrick Gold",
        "commodity": "Copper",
        "capex": (
            ("estimated at $2 billion", 2.0, "estimated",
             COUNTRY_COMPACT, "8",
             "Lumwana mine (estimated at $2 billion CapEx), expanding to 240,000 tonnes per year"),
            ("approximately $2.0B", 2.0, "approximately",
             COUNTRY_COMPACT, "25-26",
             "Lumwana Copper Barrick Gold Expansion completed to 240ktpa ∼$2.0B"),
        ),
        "capacity": (240000, "expansion target", COUNTRY_COMPACT, "8",
                     "Lumwana mine (estimated at $2 billion CapEx), expanding to 240,000 tonnes per year"),
        "historical": (
            ("123,000 t copper concentrate", USGS_YEARBOOK, "1",
             "Barrick Gold Corp. of Canada produced 123,000 t of copper concentrate at the Lumwana Mine in 2024."),
        ),
    },
    "Mingomba": {
        "developer": "KoBold Metals",
        "commodity": "Copper",
        "capex": (
            ("expected $2 billion", 2.0, "expected",
             COUNTRY_COMPACT, "8",
             "Mingomba property (with an expected CapEx of $2 billion) to produce 300,000 tpa"),
            (">$2.0B", 2.0, "lower_bound_strict",
             COUNTRY_COMPACT, "25-26",
             "Mingomba Copper KoBold Metals AI-driven exploration; 300ktpa production potential >$2.0B"),
        ),
        "capacity": (300000, "production potential", COUNTRY_COMPACT, "8",
                     "Mingomba property (with an expected CapEx of $2 billion) to produce 300,000 tpa"),
        "historical": (),
    },
}


def _source_metadata(project: dict, document: str, pages: str) -> dict:
    for item in project.get("sources", []):
        if item.get("document") == document and str(item.get("pages")) == pages:
            return item
    # USGS evidence may be present even when the answer did not cite it.
    if document == USGS_YEARBOOK:
        return {
            "title": "Zambia Minerals Yearbook 2024",
            "published_date": "",
            "source_url": "https://www.usgs.gov/centers/national-minerals-information-center/zambia",
        }
    raise ValueError(f"Missing source metadata: {document} pp. {pages}")


def _verified_excerpt(project: dict, document: str, pages: str, proof: str) -> str:
    for evidence in project.get("evidence", []):
        if (evidence.get("document") == document and
                str(evidence.get("pages")) == pages and
                _norm(proof) in _norm(evidence.get("text", ""))):
            text = " ".join(str(evidence["text"]).split())
            m = re.search(re.escape(proof), text, flags=re.IGNORECASE)
            if m:
                a, b = max(0, m.start() - 35), min(len(text), m.end() + 40)
                return ("..." if a else "") + text[a:b] + ("..." if b < len(text) else "")
            return proof
    raise ValueError(
        f"Claim lacks a matching cited passage for {project.get('project')} "
        f"in {document} ({pages}): {proof[:70]}"
    )


def load_comparison(path: Path | str | None = None) -> dict[str, dict]:
    """Load saved user-retrieved evidence and reject unsupported facts."""
    target = Path(path) if path is not None else Path(__file__).resolve().parents[1] / DATA_PATH
    report = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(report, list) or len(report) != len(FACTS):
        raise ValueError("Expected one source report for each comparison project")

    indexed = {item.get("project"): item for item in report}
    if set(indexed) != set(FACTS):
        raise ValueError("Unexpected project set in comparison source snapshot")

    output = {}
    for name, spec in FACTS.items():
        item = indexed[name]
        claims = []

        def add(kind, label, value, document, pages, proof, **kwargs):
            excerpt = _verified_excerpt(item, document, pages, proof)
            metadata = _source_metadata(item, document, pages)
            claims.append(Claim(
                project=name, kind=kind, label=label, value=value,
                document=document, pages=pages, excerpt=excerpt,
                source_title=str(metadata.get("title") or document),
                source_date=str(metadata.get("published_date") or ""),
                source_url=str(metadata.get("source_url") or ""),
                **kwargs,
            ))

        for label, amount, qualifier, doc, pages, proof in spec["capex"]:
            add("capex", "Reported CapEx", label, doc, pages, proof,
                usd_billions=amount, qualifier=qualifier)
        tpa, capacity_type, doc, pages, proof = spec["capacity"]
        add("capacity", "Production capacity or potential",
            f"{tpa:,} tpa ({capacity_type})", doc, pages, proof,
            capacity_tpa=tpa, qualifier=capacity_type)
        for label, doc, pages, proof in spec["historical"]:
            add("historical", "2024 source-reported output", label, doc, pages, proof)

        output[name] = {
            "project": name,
            "developer": spec["developer"],
            "commodity": spec["commodity"],
            "claims": claims,
            "answer": str(item.get("answer") or ""),
        }
    return output


def comparison_rows(projects: dict[str, dict], selected: list[str] | None = None) -> list[dict]:
    """One row per project; preserve conflicting and lower-bound CapEx reports."""
    names = selected if selected is not None else list(projects)
    rows = []
    for name in names:
        project = projects[name]
        claims = project["claims"]
        capex = [c for c in claims if c.kind == "capex"]
        capacity = next(c for c in claims if c.kind == "capacity")
        rows.append({
            "Project": name,
            "Developer (2026 compact)": project["developer"],
            "Commodity": project["commodity"],
            "2026 declaration CapEx": capex[0].value,
            "2026 annex CapEx": capex[1].value,
            "2026 announced capacity/potential (tpa)": capacity.capacity_tpa,
            "Capacity description": capacity.qualifier,
            "2024 reported output": "; ".join(
                c.value for c in claims if c.kind == "historical"
            ) or "Not established in this evidence",
        })
    return rows


def claim_rows(projects: dict[str, dict], selected: list[str] | None = None) -> list[dict]:
    names = selected if selected is not None else list(projects)
    return [{
        "Project": name,
        "Type": claim.kind,
        "Reported value": claim.value,
        "Qualification": claim.qualifier,
        "Source": claim.source_title,
        "Document": claim.document,
        "Pages": claim.pages,
        "Source date": claim.source_date or "2024 source / undated site record",
        "Source URL": claim.source_url,
        "Excerpt": claim.excerpt,
    } for name in names for claim in projects[name]["claims"]]
