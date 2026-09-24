#!/usr/bin/env python3
"""Audit the scholarly bibliography and its calibration/verification inventory.

The script uses only the Python standard library.  In standalone-repository mode it
checks reference_inventory.csv against external_resources.csv.  In full-project mode,
pass --bib and --tex to additionally require an exact one-to-one bibliography match,
valid citation keys, and use of every bibliography entry in the manuscript.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)
URL_RE = re.compile(r"^https://[^\s]+$", re.I)


def strip_outer_braces(value: str) -> str:
    value = value.strip()
    while len(value) >= 2 and value[0] == "{" and value[-1] == "}":
        depth = 0
        balanced = True
        for i, ch in enumerate(value):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and i != len(value) - 1:
                    balanced = False
                    break
                if depth < 0:
                    balanced = False
                    break
        if balanced and depth == 0:
            value = value[1:-1].strip()
        else:
            break
    return value


def normalize_text(value: str) -> str:
    value = strip_outer_braces(value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\\['\"`^~=.]\{?([A-Za-z])\}?", r"\1", value)
    value = value.replace("---", "-").replace("--", "-")
    return " ".join(value.split()).strip()


def split_top_level(text: str, separator: str = ",") -> List[str]:
    parts: List[str] = []
    start = 0
    brace = 0
    quote = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and brace == 0:
            quote = not quote
        elif not quote:
            if ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
                if brace < 0:
                    raise ValueError("unbalanced closing brace")
            elif ch == separator and brace == 0:
                parts.append(text[start:i])
                start = i + 1
    if brace != 0 or quote:
        raise ValueError("unbalanced BibTeX field text")
    parts.append(text[start:])
    return parts


def parse_bibtex(path: Path) -> Dict[str, Dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    entries: Dict[str, Dict[str, str]] = {}
    i = 0
    while True:
        match = re.search(r"@(\w+)\s*\{", text[i:])
        if not match:
            break
        entry_type = match.group(1).lower()
        start = i + match.end()
        depth = 1
        j = start
        while j < len(text) and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        if depth:
            raise ValueError(f"unterminated BibTeX entry after byte {i + match.start()}")
        body = text[start : j - 1]
        pieces = split_top_level(body)
        if not pieces:
            raise ValueError("empty BibTeX entry")
        key = pieces[0].strip()
        if not key:
            raise ValueError("BibTeX entry without key")
        if key in entries:
            raise ValueError(f"duplicate BibTeX key: {key}")
        fields: Dict[str, str] = {"entry_type": entry_type}
        for piece in pieces[1:]:
            if not piece.strip():
                continue
            if "=" not in piece:
                raise ValueError(f"malformed field in {key}: {piece!r}")
            name, value = piece.split("=", 1)
            fields[name.strip().lower()] = strip_outer_braces(value.strip().rstrip(","))
        entries[key] = fields
        i = j
    return entries


def collect_citations(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    keys: List[str] = []
    for match in re.finditer(r"\\cite\w*\s*\{([^}]+)\}", text):
        keys.extend(k.strip() for k in match.group(1).split(",") if k.strip())
    return keys


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def indexed(rows: Iterable[Dict[str, str]], key: str) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    result: Dict[str, Dict[str, str]] = {}
    duplicates: List[str] = []
    for row in rows:
        value = row.get(key, "").strip()
        if not value:
            duplicates.append("<blank>")
        elif value in result:
            duplicates.append(value)
        else:
            result[value] = row
    return result, duplicates


def main() -> None:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent
    parser.add_argument("--inventory", type=Path, default=root / "reference_inventory.csv")
    parser.add_argument("--external", type=Path, default=root / "external_resources.csv")
    default_bib = root.parent / "paper" / "references.bib"
    default_tex = root.parent / "paper" / "paper.tex"
    parser.add_argument("--bib", type=Path, default=default_bib if default_bib.exists() else None)
    parser.add_argument("--tex", type=Path, default=default_tex if default_tex.exists() else None)
    parser.add_argument("--out", type=Path, default=root / "results" / "references-summary.json")
    args = parser.parse_args()

    errors: List[str] = []
    inventory_rows = load_csv(args.inventory)
    external_rows = [
        r for r in load_csv(args.external)
        if r.get("citation_key", "").strip()
        and r.get("resource_type", "").strip().lower().startswith("scholarly")
    ]
    inventory, inventory_dups = indexed(inventory_rows, "citation_key")
    external, external_dups = indexed(external_rows, "citation_key")
    if inventory_dups:
        errors.append(f"duplicate/blank inventory keys: {sorted(set(inventory_dups))}")
    if external_dups:
        errors.append(f"duplicate/blank external-resource keys: {sorted(set(external_dups))}")
    if set(inventory) != set(external):
        errors.append(
            "inventory/external key mismatch: "
            f"inventory-only={sorted(set(inventory)-set(external))}, "
            f"external-only={sorted(set(external)-set(inventory))}"
        )

    required = [
        "title", "year", "venue", "identifier", "verification_level",
        "verification_source", "access_date", "relevance_bucket",
        "calibration_cohort", "manuscript_use", "metadata_status", "verification_note",
    ]
    for key, row in inventory.items():
        missing = [field for field in required if not row.get(field, "").strip()]
        if missing:
            errors.append(f"{key}: blank required fields {missing}")
        identifier = row.get("identifier", "").strip()
        if not (DOI_RE.match(identifier) or URL_RE.match(identifier)):
            errors.append(f"{key}: identifier is neither DOI nor https URL: {identifier!r}")
        if row.get("metadata_status") != "verified":
            errors.append(f"{key}: metadata_status must be verified")
        if row.get("access_date") != "2026-09-21":
            errors.append(f"{key}: unexpected access_date {row.get('access_date')!r}")
        ext = external.get(key)
        if ext:
            ext_url = ext.get("scholarly_or_official_url", "").strip()
            inv_source = row.get("verification_source", "").strip()
            if ext_url != inv_source:
                errors.append(f"{key}: verification source differs from external_resources.csv")

    # Detect silent bibliography padding, aliases, and undocumented audit labels.
    normalized_identifiers: Dict[str, str] = {}
    normalized_titles: Dict[str, str] = {}
    allowed_levels = {
        "full-paper-structural-calibration",
        "substantive-text-checked",
        "metadata-and-relevance-checked",
    }
    allowed_cohorts = {
        "TACO-full-paper", "influential-full-paper", "adjacent-full-paper",
        "latest-close", "contextual-reference",
    }
    for key, row in inventory.items():
        identifier = row.get("identifier", "").strip().lower().rstrip("/")
        title = normalize_text(row.get("title", "")).casefold()
        if identifier in normalized_identifiers:
            errors.append(f"duplicate identifier: {key} and {normalized_identifiers[identifier]}")
        else:
            normalized_identifiers[identifier] = key
        if title in normalized_titles:
            errors.append(f"duplicate normalized title: {key} and {normalized_titles[title]}")
        else:
            normalized_titles[title] = key
        year = row.get("year", "").strip()
        if not re.fullmatch(r"(?:19|20)\d{2}", year):
            errors.append(f"{key}: invalid four-digit year {year!r}")
        level = row.get("verification_level", "").strip()
        if level not in allowed_levels:
            errors.append(f"{key}: unknown verification_level {level!r}")
        cohorts = {x.strip() for x in row.get("calibration_cohort", "").split(";") if x.strip()}
        unknown = sorted(cohorts - allowed_cohorts)
        if unknown:
            errors.append(f"{key}: unknown calibration cohorts {unknown}")
        source = row.get("verification_source", "").strip().lower().rstrip("/")
        if DOI_RE.match(row.get("identifier", "").strip()) and identifier not in source:
            errors.append(f"{key}: DOI identifier absent from verification_source")

    cohort_counts = Counter()
    for row in inventory_rows:
        for cohort in (x.strip() for x in row.get("calibration_cohort", "").split(";") if x.strip()):
            cohort_counts[cohort] += 1
    minima = {"TACO-full-paper": 12, "influential-full-paper": 5, "adjacent-full-paper": 5, "latest-close": 2}
    for cohort, minimum in minima.items():
        if cohort_counts[cohort] < minimum:
            errors.append(f"cohort {cohort}: {cohort_counts[cohort]} < required {minimum}")

    citation_counts: Counter[str] = Counter()
    bib_entries: Dict[str, Dict[str, str]] = {}
    if args.bib:
        bib_entries = parse_bibtex(args.bib)
        if set(bib_entries) != set(inventory):
            errors.append(
                "bibliography/inventory key mismatch: "
                f"bib-only={sorted(set(bib_entries)-set(inventory))}, "
                f"inventory-only={sorted(set(inventory)-set(bib_entries))}"
            )
        for key, fields in bib_entries.items():
            row = inventory.get(key)
            if not row:
                continue
            bib_title = normalize_text(fields.get("title", ""))
            inv_title = normalize_text(row.get("title", ""))
            if bib_title != inv_title:
                errors.append(f"{key}: title mismatch: {bib_title!r} != {inv_title!r}")
            if fields.get("year", "").strip() != row.get("year", "").strip():
                errors.append(f"{key}: year mismatch")
            venue = fields.get("journal", fields.get("booktitle", fields.get("archiveprefix", "")))
            if normalize_text(venue) != normalize_text(row.get("venue", "")):
                errors.append(f"{key}: venue mismatch")
            identifier = fields.get("doi", fields.get("url", "")).strip()
            if identifier != row.get("identifier", "").strip():
                errors.append(f"{key}: identifier mismatch")

    if args.tex:
        if not args.bib:
            errors.append("--tex requires --bib")
        citations = collect_citations(args.tex)
        citation_counts.update(citations)
        missing = sorted(set(citations) - set(bib_entries))
        uncited = sorted(set(bib_entries) - set(citations))
        if missing:
            errors.append(f"manuscript cites missing keys: {missing}")
        if uncited:
            errors.append(f"uncited bibliography entries: {uncited}")

    levels = Counter(row.get("verification_level", "") for row in inventory_rows)
    buckets = Counter(row.get("relevance_bucket", "") for row in inventory_rows)
    summary = {
        "status": "PASS" if not errors else "FAIL",
        "scholarly_references": len(inventory),
        "unique_bibliography_keys": len(bib_entries) if args.bib else None,
        "unique_cited_keys": len(citation_counts) if args.tex else None,
        "total_citation_occurrences": sum(citation_counts.values()) if args.tex else None,
        "verification_levels": dict(sorted(levels.items())),
        "relevance_buckets": dict(sorted(buckets.items())),
        "calibration_cohorts": dict(sorted(cohort_counts.items())),
        "requirements": minima,
        "errors": errors,
        "interpretation": (
            "Metadata/identifier checks and documented reading levels are audited. "
            "This is not an automated proof that every cited scientific claim is correct; "
            "claim wording remains limited to the recorded access scope."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
