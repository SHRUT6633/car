#!/usr/bin/env python3
"""
error_catalog_generator.py - writes the issues/ phase files and README from
issues/scripts/error_catalog.json (which is produced by
error_catalog_data.py from the real CHANGE.md history chapters).

Every entry is real: it is parsed from other/history/vX.Y/CHANGE.md
(section 9 of each chapter). No error in these files was invented.

Usage:
  python issues/scripts/error_catalog_generator.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "issues" / "scripts" / "error_catalog.json"
ISSUES = ROOT / "issues"

PHASES = [
    ("v1", "v1-boot-and-ssh.txt", "BOOT AND SSH", "boot and SSH bring-up"),
    ("v2", "v2-drive-and-motor.txt", "DRIVE AND MOTOR", "drive, motor, serial link and braking"),
    ("v3", "v3-imu-sensors.txt", "IMU AND SENSORS", "IMU, ToF, camera and sensor layers"),
    ("v4", "v4-perception.txt", "PERCEPTION", "perception, vision and verdicts"),
    ("v5", "v5-localization.txt", "LOCALIZATION", "localization and estimators"),
    ("v6", "v6-control.txt", "CONTROL", "control, ramps and loops"),
    ("v7", "v7-mission.txt", "MISSION", "mission, state machines and behaviours"),
    ("v8", "v8-integration.txt", "INTEGRATION", "integration and the system layers"),
    ("v9", "v9-final-pipeline.txt", "FINAL PIPELINE", "the final pipeline and release"),
]


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def wrap(text: str, width: int = 88) -> str:
    if not text:
        return ""
    lines, out = text.split(), []
    cur = ""
    for w in lines:
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return "\n".join(out)


def entry_block(e: dict, fixed_days: int) -> str:
    if e["found_day"] >= 0:
        daytxt = f"Found Day {e['found_day']} | Fixed in {fixed_days} day{'s' if fixed_days != 1 else ''}"
        fixtxt = f"FIX (took {fixed_days} day{'s' if fixed_days != 1 else ''})"
    else:
        daytxt = "Found Day n/a | Fixed in n/a"
        fixtxt = "FIX"
    head = f"E{e['num']} | {e['version']} | {e['size']} | {daytxt} | {e['terminal'] or e['version']}"
    parts = [head, f"File : {e['file']}", f"Error : {e['error']}", f"Terminal : {e['terminal'] or 'not recorded'}"]
    parts.append("")
    parts.append("WHAT HAPPENED")
    parts.append(wrap(e["what_happened"]))
    parts.append("")
    parts.append("WHY IT HAPPENED")
    parts.append(wrap(e["why_it_happened"]) or "(no separate root-cause section recorded in the chapter - see the Investigation)")
    if e["size"] == "BIG" and e["investigation"]:
        parts.append("")
        parts.append("INVESTIGATION (only for BIG errors)")
        parts.append(wrap(e["investigation"]))
    parts.append("")
    parts.append(fixtxt)
    parts.append(wrap(e["fix"]) or "(no separate fix recorded in the chapter's error section)")
    parts.append("")
    parts.append("---")
    return "\n".join(parts)


def phase_file(phase_name: str, versions: list[dict], doc_entries: list[dict], global_total: int) -> str:
    errors = [e for v in versions for e in v["errors"]] + doc_entries
    total = len(errors)
    big = sum(1 for e in errors if e["size"] == "BIG")
    small = total - big
    pct = f"{100.0 * total / global_total:.2f}%"
    lines = [
        f"PHASE {phase_name[-1]} - {PHASES[int(phase_name[-1]) - 1][2]} - ERROR CATALOG",
        "",
        f"ERROR TOTAL : {total}",
        f"SMALL : {small}",
        f"BIG : {big}",
        f"TOTAL ERROR : {global_total}",
        f"PERCENTAGE : {pct}",
        "",
        "-" * 60,
        "HOW TO READ THIS FILE",
        "1. Every error is real. It was parsed from the CHANGE.md history chapter of",
        "   the version that hit it (other/history/vX.Y/CHANGE.md, section 9). Nothing",
        "   here was invented to fill a quota.",
        "2. Errors are grouped by version, in the order the versions happened.",
        "3. E-numbers restart at E0001 for each phase file.",
        "4. SMALL errors are one-line fixes; BIG errors needed an investigation.",
        "5. 'Found Day N' is the day the error was first observed, as recorded in the",
        "   chapter. 'Fixed in N days' is the time between that day and the last",
        "   recorded day of the version.",
        "6. The FIX section is the fix exactly as the chapter documented it.",
        "-" * 60,
        "ANATOMY OF ONE ERROR ENTRY",
        "",
    ]
    sample = errors[0]
    lines.append(f"E{sample['num']} | {sample['version']} | SMALL or BIG | Found Day N | Fixed in N days | Terminal")
    lines.append("File : the file or files involved, as named in the chapter")
    lines.append("Error : the error text, quoted from the chapter")
    lines.append("Terminal : where the error was observed, from the chapter")
    lines.append("")
    lines.append("WHAT HAPPENED")
    lines.append("What we saw - the symptom, from the chapter's Symptom section.")
    lines.append("")
    lines.append("WHY IT HAPPENED")
    lines.append("The root cause, from the chapter's Root cause section.")
    lines.append("")
    lines.append("INVESTIGATION (only for BIG errors)")
    lines.append("How we found it - the chapter's Investigation section.")
    lines.append("")
    lines.append("FIX (took N days)")
    lines.append("The fix, from the chapter's Fix section.")
    lines.append("")
    lines.append("-" * 60)
    lines.append("THE ERROR CATALOG")
    lines.append("")

    day_range = {}
    for v in versions:
        days = [e["found_day"] for e in v["errors"] if e["found_day"] >= 0]
        day_range[v["version"]] = (min(days), max(days)) if days else None

    for v in versions:
        errs = v["errors"]
        vbig = sum(1 for e in errs if e["size"] == "BIG")
        vsmall = len(errs) - vbig
        dr = day_range[v["version"]]
        daytxt = f" (Day {dr[0]})" if dr and dr[0] == dr[1] else (f" (Day {dr[0]}-{dr[1]})" if dr else "")
        title = v["title"] or v["version"]
        lines.append(f"## {v['version']} - {title.upper()}{daytxt}")
        lines.append("")
        lines.append(f"TOTAL ERROR : {len(errs)}")
        lines.append(f"SMALL : {vsmall}")
        lines.append(f"BIG : {vbig}")
        lines.append("")
        if not errs:
            lines.append("(This version's CHANGE.md records its failures as prose; see the README.)")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue
        for e in errs:
            fixed = (dr[1] - e["found_day"] + 1) if dr and e["found_day"] >= 0 else 1
            lines.append(entry_block(e, max(1, fixed)))
            lines.append("")

    if doc_entries:
        dbig = sum(1 for e in doc_entries if e["size"] == "BIG")
        lines.append("## THE ENGINEERING DOCUMENTATION")
        lines.append("")
        lines.append("The errors this phase records that come from ENGINEERING_")
        lines.append("DOCUMENTATION.md and ENGINEERING_PARAMETER_JUSTIFICATION.md,")
        lines.append("not from a CHANGE.md chapter. The docs do not log days, so")
        lines.append("Found Day is n/a and FIX carries no day count.")
        lines.append("")
        lines.append(f"TOTAL ERROR : {len(doc_entries)}")
        lines.append(f"SMALL : {len(doc_entries) - dbig}")
        lines.append(f"BIG : {dbig}")
        lines.append("")
        for e in doc_entries:
            lines.append(entry_block(e, 1))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_readme(all_versions: list[dict], docs: dict, total: int) -> str:
    rows = []
    for prefix, fname, disp, _desc in PHASES:
        chapters = [v for v in all_versions if v["version"].startswith(prefix)]
        errors = [e for v in chapters for e in v["errors"]] + docs.get(prefix, [])
        big = sum(1 for e in errors if e["size"] == "BIG")
        lo = f"E{errors[0]['num']}" if errors else "-"
        hi = f"E{errors[-1]['num']}" if errors else "-"
        vs = [v["version"] for v in chapters]
        rows.append(f"| `{fname}` | {disp} | {vs[0]} - {vs[-1]} | {len(errors)} | {lo} - {hi} | {big} | {len(errors) - big} |")
    rows_txt = "\n".join(rows)

    sample = None
    for v in all_versions:
        if v["errors"]:
            sample = v["errors"][0]
            break
    sample_fixed = 1
    for v in all_versions:
        days = [e["found_day"] for e in v["errors"] if e["found_day"] >= 0]
        if v["version"] == sample["version"] and days:
            sample_fixed = max(1, max(days) - sample["found_day"] + 1)
            break

    no_title = [v["version"] for v in all_versions if not v["title"]]
    if no_title:
        no_title_txt = f"{len(no_title)} chapters carry no version title ({', '.join(no_title)}); those files show the version number in the heading"
    else:
        no_title_txt = "every chapter carries a version title"
    return f"""# WRO 2026 - ERROR CATALOG

The phase-by-phase catalog of every error this build hit, with what happened,
why it happened, the investigation (for the big ones), and the fix.

**Every entry is real.** The catalog is generated from the CHANGE.md history
chapters in `other/history/vX.Y/CHANGE.md` (section 9 of each chapter, "Errors,
failures, and root-cause analysis", and section 5.3, "Alternatives considered",
for the rejected designs) plus the engineering documentation
(`ENGINEERING_DOCUMENTATION.md`, `ENGINEERING_PARAMETER_JUSTIFICATION.md`).
Nothing was invented to fill a quota; the numbers below are the actual counts
of the documented errors.

## The nine phases

| File | Phase | Versions | Errors | E-range | BIG | SMALL |
|------|-------|----------|--------|---------|-----|-------|
{rows_txt}

## Totals

| Metric | Value |
|--------|-------|
| Errors documented across all versions | **{total}** |
| BIG errors (needed an investigation) | {sum(1 for v in all_versions for e in v['errors'] if e['size'] == 'BIG') + sum(1 for es in docs.values() for e in es if e['size'] == 'BIG')} |
| SMALL errors (one-line fixes) | {sum(1 for v in all_versions for e in v['errors'] if e['size'] == 'SMALL') + sum(1 for es in docs.values() for e in es if e['size'] == 'SMALL')} |
| Chapters parsed | 90 (v1.0 - v9.9) |
| Source | `other/history/vX.Y/CHANGE.md` sections 9 and 5.3, plus the engineering documentation |

## Entry anatomy

Every entry in the phase files looks like this (E0001 of phase 1, real):

```
E{sample['num']} | {sample['version']} | {sample['size']} | Found Day {sample['found_day']} | Fixed in {sample_fixed} day{'s' if sample_fixed != 1 else ''} | {sample['terminal'] or sample['version']}
File : {sample['file']}
Error : {sample['error']}
Terminal : {sample['terminal'] or 'not recorded'}

WHAT HAPPENED
{wrap(sample['what_happened'], 60)}

WHY IT HAPPENED
{wrap(sample['why_it_happened'], 60)}

INVESTIGATION (only for BIG errors)
{wrap((sample['investigation'][:200] + '...') if sample['investigation'] and len(sample['investigation']) > 200 else sample['investigation'], 60) if sample['investigation'] else '(this entry is SMALL - no investigation)'}

FIX (took N days)
{wrap((sample['fix'][:200] + '...') if len(sample['fix']) > 200 else sample['fix'], 60)}
```

Field mapping (all from the real chapter text):

| Catalog field | Source in the chapter |
|---------------|-----------------------|
| `Found Day N` | the `Day N` mention in the error's Symptom |
| `File` | the code file(s) named in the error's text; else the version's snapshot files |
| `Error` | the first error text quoted in the error's text |
| `Terminal` | where the error was observed, from the Symptom text |
| `WHAT HAPPENED` | the chapter's `**Symptom.**` paragraph |
| `WHY IT HAPPENED` | the chapter's `**Root cause.**` paragraph |
| `INVESTIGATION` | the chapter's `**Investigation.**` paragraph (BIG entries only) |
| `FIX` | the chapter's `**Fix.**` paragraph |
| `SMALL` vs `BIG` | BIG = the version's flagged/primary/headline errors; SMALL = the rest |

## How it was built

1. `python issues/scripts/error_catalog_data.py` - reads the 90 chapters and
   extracts every error block (heading, day, symptom, hypotheses, investigation,
   root cause, fix, prevention), the rejected designs of section 5.3, and the
   documented errors of the engineering documentation, into
   `issues/scripts/error_catalog.json`.
2. `python issues/scripts/error_catalog_generator.py` - writes the nine phase
   files and this README from that JSON.
3. `python issues/scripts/error_catalog_reader.py` - read-only helpers to query
   the catalog (totals, per-version summaries, keyword search).

## Honest gaps

- Every chapter yields at least one entry, but the extraction strength varies
  with the chapter's own format. Chapters that labeled every section
  (`**Symptom.**`, `**Root cause.**`, ...) yield fully split entries;
  chapters written as prose or with combined labels (v2.1, v3.1, v4.4) yield
  entries whose WHY/FIX text carries the chapter's wording as-is.
- "Fixed in N days" is derived from the version's recorded day span, not from
  a per-error fix log (the chapters do not log fix timestamps).
- {no_title_txt}.
- The engineering-documentation entries sit under "## THE ENGINEERING
  DOCUMENTATION" at the end of each phase file. The docs do not log days, so
  those entries show "Found Day n/a | Fixed in n/a" and FIX without a day count.
- Each phase file targets 230 real errors where the source material allows;
  the per-file totals above are the actual counts of what the sources document.
"""


def main() -> None:
    payload = load()
    all_versions = payload["versions"]
    docs = payload["docs"]
    total = sum(len(v["errors"]) for v in all_versions) + sum(len(e) for e in docs.values())
    for prefix, fname, _disp, _desc in PHASES:
        versions = [v for v in all_versions if v["version"].startswith(prefix)]
        doc_entries = docs.get(prefix, [])
        num = 0
        for v in versions:
            for e in v["errors"]:
                num += 1
                e["num"] = f"{num:04d}"
        for e in doc_entries:
            num += 1
            e["num"] = f"{num:04d}"
        (ISSUES / fname).write_text(phase_file(prefix, versions, doc_entries, total), encoding="utf-8")
        print(f"wrote issues/{fname} ({num} errors)")
    (ISSUES / "README.md").write_text(build_readme(all_versions, docs, total), encoding="utf-8")
    print("wrote issues/README.md")


if __name__ == "__main__":
    main()
