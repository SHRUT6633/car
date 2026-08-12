#!/usr/bin/env python3
"""
error_catalog_reader.py - read-only helpers for the error catalog.

It only reads issues/scripts/error_catalog.json; it never writes anything.

Usage:
  python issues/scripts/error_catalog_reader.py            - totals per phase
  python issues/scripts/error_catalog_reader.py <keyword>  - search titles
  python issues/scripts/error_catalog_reader.py <version>  - one version
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "issues" / "scripts" / "error_catalog.json"


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def all_errors(payload: dict) -> list[dict]:
    out = [e for v in payload["versions"] for e in v["errors"]]
    for entries in payload["docs"].values():
        out.extend(entries)
    return out


def show_totals(payload: dict) -> None:
    versions, docs = payload["versions"], payload["docs"]
    total = big = small = 0
    print(f"{'phase':<4} {'versions':<8} {'errors':>6} {'BIG':>4} {'SMALL':>5}")
    for prefix in (f"v{i}" for i in range(1, 10)):
        vs = [v for v in versions if v["version"].startswith(prefix)]
        errs = [e for v in vs for e in v["errors"]] + docs.get(prefix, [])
        b = sum(1 for e in errs if e["size"] == "BIG")
        print(f"{prefix:<4} {vs[0]['version'] if vs else '-':<8} {len(errs):>6} {b:>4} {len(errs) - b:>5}")
        total += len(errs)
        big += b
        small += len(errs) - b
    print(f"TOTAL: {total} errors ({big} BIG, {small} SMALL)")


def search(payload: dict, needle: str) -> None:
    hits = 0
    for e in all_errors(payload):
        hay = f"{e['title']} {e['error']} {e['what_happened']}".lower()
        if needle.lower() in hay:
            hits += 1
            print(f"{e['version']} {e['size']:<5} day {e['found_day']:<3} {e['title'][:90]}")
    print(f"{hits} match(es)")


def show_version(payload: dict, target: str) -> None:
    for v in payload["versions"]:
        if v["version"] == target:
            print(f"{v['version']} - {v['title']}")
            for e in v["errors"]:
                print(f"  [{e['size']}] Day {e['found_day']}: {e['title'][:100]}")
            return
    print(f"no such version: {target}")


def main() -> None:
    payload = load()
    if len(sys.argv) < 2:
        show_totals(payload)
        return
    arg = sys.argv[1]
    if any(version["version"] == arg for version in payload["versions"]):
        show_version(payload, arg)
    else:
        search(payload, arg)


if __name__ == "__main__":
    main()
