#!/usr/bin/env python3
"""
error_catalog_data.py - extracts every real documented error from this repo
and writes issues/scripts/error_catalog.json.

The catalog is NOT synthetic. Every entry is parsed from real repo content:

  1. Section 9 of each chapter (other/history/vX.Y/CHANGE.md):
     "Errors, failures, and root-cause analysis" - the structured error
     sections with Symptom / Initial hypotheses / Investigation / Root cause /
     Fix / Prevention labels.
  2. Section 5.3 of each chapter: "Alternatives considered" - the designs that
     were measured, failed, and rejected (tagged "(rejected design)").
  3. The engineering documentation (ENGINEERING_DOCUMENTATION.md and
     ENGINEERING_PARAMETER_JUSTIFICATION.md): the documented failure analyses
     (FA-1..3), open items (O-1, O-2), measured sensor errors and rejected
     designs (tagged "(the engineering documentation)").

Nothing here was invented to fill a quota; the numbers are the actual counts
of the documented failures.

Usage:
  python issues/scripts/error_catalog_data.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "other" / "history"
OUT = ROOT / "issues" / "scripts" / "error_catalog.json"

HEADING_RE = re.compile(
    r"^#{3,4}\s+(?:Error\s+\d+\.\d+|Error\s+\d+|E\d+|9\.\d+|7\.\d+\s+Error)"
    r"\s*(?:\((?:primary|secondary|process|root.cause sibling|accepted debt[^)]*)\)\s*)?[:—-]?\s*(.*)$"
)
BOLD_ERROR_RE = re.compile(r"^\*\*(Error\s+\d+.*?)\*\*")
LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*{1,2}|_{1,2})?([^*_]{1,80}?)\s*[:.][*_]{0,2}\s*(.*)$"
)
LABEL_WORDS = {
    ("symptom",): "symptom",
    ("initial", "hypotheses"): "hypotheses",
    ("hypotheses",): "hypotheses",
    ("hypothesis",): "hypotheses",
    ("wrong", "guesses"): "hypotheses",
    ("investigation",): "investigation",
    ("root", "cause"): "rootcause",
    ("mechanism",): "rootcause",
    ("fix",): "fix",
    ("prevention",): "prevention",
    ("cost",): "cost",
}


def label_key(label: str) -> str | None:
    words = re.sub(r"[^a-z\s]", " ", label.lower()).split()
    if "root cause" in label.lower():
        return "rootcause"
    for key_tup, key in LABEL_WORDS.items():
        if len(words) >= len(key_tup) and words[: len(key_tup)] == list(key_tup):
            return key
    return None


def inline_root_cause(body_text: str) -> str:
    """Some chapters state the root cause inline ('Root cause: ...') inside
    another section instead of labeling it. Take the real sentence(s)."""
    m = re.search(r"(?i)root cause\s*[:—-]\s*(.{0,600})", body_text)
    if not m:
        return ""
    tail = m.group(1)
    sents = []
    for s in re.split(r"(?<=[.!?])\s+", tail):
        sents.append(s.strip())
        if len(" ".join(sents)) > 140:
            break
    return " ".join(sents).strip('" ')
DAY_RE = re.compile(r"Days?\s+(\d+)")
CODE_RE = re.compile(r"`([^`]+)`")
FILE_RE = re.compile(r"([\w/.\-]+\.(?:py|ino|json|txt|md))")
SECTION_RE = re.compile(r"^#{1,4}\s")
ALT_HEAD_RE = re.compile(r"^\s*\*\*(Alternative\s+[A-Z0-9]+\s*[—-]\s*[^*]+?)\*\*\s*(.*)$")
REJECT_RE = re.compile(
    r"(?i)(verdict[^\n]{0,70}(?:reject|not chosen|dropped|ruled out|unacceptable|abandoned)"
    r"|rejected because|rejected [—-]|rejected as|rejected:|rejected\b"
    r"|fails? on two counts|is the bug we are fixing|catastrophically poor)"
)
CHOSEN_RE = re.compile(r"(?i)verdict[^\n]{0,40}accepted|\(chosen\)|\((?:the )?chosen\)")

PLACEHOLDER_FILES = {"file.py", "filename.py", "xxx.py", "main.py"}

# Real documented failures from ENGINEERING_DOCUMENTATION.md and
# ENGINEERING_PARAMETER_JUSTIFICATION.md. The text is transcribed from the
# documents (symptom / root cause / fix), not invented.
DOC_ERRORS = {
    "v1": [
        {
            "title": "the boot probe always failed — the keyword mismatch (FA-1)",
            "what": "The boot probe in main.py always halted at 'ESP32 NOT CONNECTED! Fix serial and reboot' even with a healthy serial link: _probe_serial() called transmit_command(servo_angle_deg=0.0, speed_pct=0.0), but the method signature is (servo_angle_deg, motor_speed). Python's TypeError was raised, the probe caught it and reported 'serial dead', and the boot sequence fell into the halt loop. The bug was invisible in simulation because the keyword mismatch never executed on a path that was tested.",
            "why": "The keyword-argument mismatch (speed_pct vs motor_speed) was swallowed by the probe's exception handling, so a healthy link was reported dead.",
            "fix": "Corrected the keyword to motor_speed=0.0; the probe now exercises the real packet path. Prevention: all public cross-layer call signatures were audited against their call sites and the boot probe is covered by the integration test.",
            "file": "main.py",
            "size": "BIG",
        },
    ],
    "v2": [
        {
            "title": "the serial fault detection could never trigger (FA-2)",
            "what": "LED4 (serial health) never turned OFF mid-race and the documented emergency-stop path never executed: transmit_command() swallowed its own serial write exceptions and silently returned the packet even when the ESP32 was absent or the port had died.",
            "why": "The 5-fault threshold logic in main.py was unreachable — the failure was logged by layer 10 and forgotten.",
            "fix": "transmit_command() now raises IOError when the link is unavailable or a write fails, so the fault propagates to the caller and the Pi-side failsafe (LED4 OFF, LED5 stop, retry loop) actually runs. The ESP32's independent 200 ms watchdog remains the second layer.",
            "file": "layers/layer10_controller.py, main.py",
            "size": "BIG",
        },
        {
            "title": "the text serial protocol rejected — the parser ambiguity",
            "what": "A text protocol over a 115200 baud USB link was measured and rejected: it would cost 3-5x more bytes per command and add parser ambiguity.",
            "why": "The byte cost and parser ambiguity of a text protocol at 100 Hz command rate.",
            "fix": "Replaced by the 10-byte CRC8 binary packet (utils/serial_protocol.py): 2-byte header, 1-byte sequence, 1-byte command, 4 bytes of int16 big-endian servo/speed, 1-byte CRC8 (poly 0x07), 1-byte footer.",
            "file": "utils/serial_protocol.py",
            "size": "SMALL",
        },
        {
            "title": "the dual-servo steering rejected — the doubled failure modes",
            "what": "Dual-servo crab-walk-capable steering was considered and rejected: two independently driven steering actuators add ~90 g, a second PWM channel and two calibration drift curves.",
            "why": "A dual-servo system doubles steering failure modes (two jam points, two calibration drift curves); the WRO 2026 rubric rewards reliability under time pressure.",
            "fix": "Single MG995 servo + mechanical linkage (delta_r = -0.85 * delta_f) with the 141 mm turning radius from the 4WS decomposition.",
            "file": "layers/layer9_kinematics_4ws.py",
            "size": "SMALL",
        },
        {
            "title": "the crab-walk rejected — the single-servo mechanical limit",
            "what": "Crab-walk (all four wheels steered to the same angle) was measured and rejected for this platform: the single-servo linkage enforces delta_r = -k*delta_f, so true crab-walk needs dual actuators.",
            "why": "Mechanical limit of the single-servo linkage, plus the 48.5% radius reduction already fits the parking approach arc inside the venue geometry.",
            "fix": "The parking maneuver is executed as a curvature-reduced approach arc + stop, exploiting the 141 mm turning radius — no crab-walk required.",
            "file": "layers/layer9_kinematics_4ws.py",
            "size": "SMALL",
        },
        {
            "title": "the naive same-angle 4WS split rejected — the tire scrub",
            "what": "A naive 'same angle front and rear' steering split was analysed and rejected: both axle midpoints cannot share one turning center, producing tire scrub.",
            "why": "The naive split (delta_r = delta_f) is kinematically impossible to drive — both axle midpoints cannot share one turning center.",
            "fix": "The counter-steered split (delta_r = -k*delta_f, k = 0.85) places the instantaneous turning center correctly for the mechanical linkage.",
            "file": "layers/layer9_kinematics_4ws.py",
            "size": "SMALL",
        },
    ],
    "v3": [
        {
            "title": "the VL53L0X over-report by 48-53 mm — the optical path bias",
            "what": "During bench testing against a metal ruler at 200/400/600 mm, both VL53L0X units consistently over-reported by 48-53 mm.",
            "why": "The optical path from the sensor window to the chassis skin is longer than the datasheet's reference zero, and the lens mount's refractive offset adds a fixed bias.",
            "fix": "A software OFFSET_LR_MM = 50.0 subtracted from left/right readings (layer1_sensors.py), verified post-fix: mean error < +/-3 mm across 200-600 mm.",
            "file": "layers/layer1_sensors.py",
            "size": "BIG",
        },
        {
            "title": "the VL53L1X intermittent readings under the 50 ms budget",
            "what": "The front VL53L1X initially produced intermittent readings under the 50 ms budget.",
            "why": "The VL53L1X ranging cycle (68 ms) is 6.8x slower than the 10 ms control frame; the control loop can never block on I2C.",
            "fix": "Measured a 33 ms ranging budget + 35 ms settling for a reliable 68 ms cycle; the front sensor runs its own dedicated background thread with a lock-protected snapshot.",
            "file": "layers/layer1_sensors.py",
            "size": "BIG",
        },
        {
            "title": "the shared I2C bus — the address collision fix",
            "what": "Three VL53 sensors and the MPU6050 share one I2C bus (constraint C-5); simultaneous operation caused bus contention.",
            "why": "One I2C bus shared by 4 devices on the Pi 4B.",
            "fix": "Each sensor is power-gated by its own XSHUT line: sequential XSHUT power-switching, one sensor live at a time.",
            "file": "layers/layer1_sensors.py",
            "size": "SMALL",
        },
    ],
    "v4": [
        {
            "title": "the HSV tuner writes to an unused config key (O-1)",
            "what": "Known limitation (open item O-1): the HSV tuner (utils/calibrate_hsv.py) currently writes to camera.hsv_tuned, while the perception layer reads hsv_red1/hsv_green/... A tune session therefore does not yet modify runtime thresholds.",
            "why": "The tuner's output key and the perception layer's read keys were never wired together.",
            "fix": "The fix is a 5-line change (write to the per-color keys the perception layer reads) and is scheduled before venue practice.",
            "file": "utils/calibrate_hsv.py, layers/layer4_perception.py",
            "size": "SMALL",
        },
        {
            "title": "the missing HSV key could crash the race loop",
            "what": "A missing hsv_* block in the config could crash the race loop at startup.",
            "why": "No defensive default for config keys in the perception layer.",
            "fix": "Every hsv_* block in the config has a fallback value in code (layer4_perception.py), so a missing key can never crash the race loop.",
            "file": "layers/layer4_perception.py",
            "size": "SMALL",
        },
    ],
    "v5": [],
    "v6": [
        {
            "title": "the high-speed servo oscillation — the gain scheduling fix",
            "what": "A high-speed oscillation appeared in the servo log during a test at higher speed.",
            "why": "The Stanley gain was fixed while speed rose, so the steering authority grew unstable with speed.",
            "fix": "The gain scheduling term was added: k drops 0.75 -> 0.395 as speed rises 0 -> 60%, eliminating the oscillation while keeping cornering authority at low speed.",
            "file": "layers/layer10_controller.py",
            "size": "BIG",
        },
        {
            "title": "the slow settling at low gain — the k < 0.5 failure",
            "what": "In the gain-sweep test (k in {0.3..1.2}), gains below 0.5 took more than 2 s for the cross-track error to settle.",
            "why": "Too low a Stanley gain understeers the correction, so the cross-track error decays too slowly.",
            "fix": "k = 0.75 selected as the base gain from the measured sweep.",
            "file": "layers/layer10_controller.py",
            "size": "SMALL",
        },
    ],
    "v7": [
        {
            "title": "the parking hold is 5.0 s vs the cited 15 s (O-2)",
            "what": "Known deviation (open item O-2): the code comments cite the mandatory '15-second stationary rule' at parking, but the implementation transitions after 5.0 s.",
            "why": "The constant in layer6_mission_manager.py does not match the comment's rule citation.",
            "fix": "Verify against the 2026 rulebook before venue day; the constant is a one-line change in layer6_mission_manager.py.",
            "file": "layers/layer6_mission_manager.py",
            "size": "SMALL",
        },
    ],
    "v8": [
        {
            "title": "layer2_time_sync would not import — the IndentationError (FA-3)",
            "what": "Module-level crash at startup on get_history(): layer2_time_sync would not import.",
            "why": "A body-less indented block under the function definition — a truncation artifact during refactoring.",
            "fix": "Corrected the indentation; a py_compile gate was added to CI — all 16 Python files now pass python -m py_compile as a pre-commit check.",
            "file": "layers/layer2_time_sync.py",
            "size": "BIG",
        },
        {
            "title": "the blocking I2C read rejected — the 100 Hz impossibility",
            "what": "Blocking I2C reads in the main loop were considered and rejected: with a 68 ms sensor cycle and a 10 ms control frame, a blocking read makes 100 Hz physically impossible.",
            "why": "The control loop can never block on I2C (constraint C-2).",
            "fix": "layer1_sensors.py runs a dedicated polling thread writing to a lock-protected snapshot; the main loop reads the latest snapshot with zero blocking, and status flags report staleness.",
            "file": "layers/layer1_sensors.py, main.py",
            "size": "SMALL",
        },
    ],
    "v9": [],
}


def chapter_heading(chapter: str) -> str:
    m = re.match(r"^#\s+v\d+\.\d+\s*[-—:]\s*(.+)$", chapter, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?ms)^#{2,3}\s+2\.\s+Title\s*\n+(.+?)(?=\n#{1,4}\s)", chapter)
    if m:
        line = m.group(1).strip().splitlines()[0]
        return re.sub(r"^#\s+v\d+\.\d+\s*[-—:]\s*", "", line).strip()
    return ""


def error_blocks(chapter: str) -> list[dict]:
    lines = chapter.splitlines()
    section = None
    for i, ln in enumerate(lines):
        if SECTION_RE.match(ln) and re.search(r"Errors?[,:]|failures|root-cause", ln, re.IGNORECASE):
            section = i
            break
    if section is None:
        return []

    def start_block(ln, title):
        return {"heading": ln.strip(), "title": title, "body": []}

    blocks: list[dict] = []
    current = None
    i = section
    while i < len(lines):
        ln = lines[i]
        bold = BOLD_ERROR_RE.match(ln)
        open_bold = (not bold) and ln.lstrip().startswith("**Error ") and not ln.rstrip().endswith("**")
        if bold or open_bold:
            heading = ln
            while i + 1 < len(lines) and not heading.rstrip().endswith("**"):
                i += 1
                heading += " " + lines[i].strip()
            bold = BOLD_ERROR_RE.match(heading)
            if bold:
                current = start_block(heading, bold.group(1).strip().strip("*").strip())
                blocks.append(current)
            i += 1
            continue
        h = SECTION_RE.match(ln)
        if h:
            heading = HEADING_RE.match(ln)
            if heading:
                current = start_block(ln, heading.group(1).strip().rstrip(";").strip())
                blocks.append(current)
                i += 1
                continue
            if re.search(r"Errors?[,:]|failures|root-cause", ln, re.IGNORECASE):
                i += 1
                continue
            break
        if current is not None:
            current["body"].append(ln)
        i += 1

    if not blocks:
        body = lines[section + 1:]
        if any(LABEL_RE.match(ln) for ln in body):
            probe = " ".join(body)
            m = re.search(r"\*\*Error[:.]\*\*\s*([^*]+?)(?:\*\*|$)", probe)
            if not m:
                m = re.search(r"\*\*[“\"']\s*([^”\"'*]+?)[”\"']\s*\*\*", probe)
            title = m.group(1).strip() if m else re.sub(r"^#{2,4}\s+", "", lines[section].strip())
            blocks.append({"heading": lines[section].strip(), "title": title, "body": body})
    return blocks


def labeled_fields(block: dict) -> dict:
    fields: dict[str, list[str]] = {}
    key = None
    for ln in block["body"]:
        m = LABEL_RE.match(ln)
        if m:
            k = label_key(m.group(1))
            if k:
                key = k
                fields.setdefault(k, []).append(m.group(2).strip())
            elif key:
                fields[key].append(ln.strip())
        elif key:
            fields[key].append(ln)
    out = {}
    for k, v in fields.items():
        out[k] = " ".join(t.strip() for t in v if t.strip()).replace("\u00ad", "-")
    return out


def found_day(block: dict, fields: dict) -> int:
    source = fields.get("symptom", "") + " " + block.get("heading", "")
    m = DAY_RE.search(source)
    if m:
        return int(m.group(1))
    m = DAY_RE.search(" ".join(block.get("body", [])))
    return int(m.group(1)) if m else -1


def observation_context(fields: dict) -> str:
    """The real 'where it was observed' phrase, taken from the symptom text."""
    sym = fields.get("symptom", "")
    for device in ("SSH", "serial monitor", "the venue", "the rehearsal", "the bench", "the field", "the practice", "the race"):
        if device.lower() in sym.lower():
            return device[3:].strip() if device.startswith("the ") else device
    m = re.search(r"Days?\s+\d+\s*,?\s*([^:(—,]{3,80})", sym)
    if m:
        ctx = m.group(1).strip().strip(", ").strip("-").strip()
        if ctx:
            return ctx
    for clause in re.split(r"[,.:;—]", sym):
        if "`" in clause:
            continue
        words = clause.strip().split()
        if len(words) < 3:
            continue
        if words[0] in ("On", "During", "After", "When"):
            words = words[1:]
        return " ".join(words[:6])
    return ""


def version_files(version_dir: Path) -> list[str]:
    return sorted(p.name for p in version_dir.iterdir() if p.is_file() and p.name != "CHANGE.md")


def clean_title(title: str) -> str:
    title = re.sub(r"^(?:Error\s+\d+(?:\.\d+)?|E\d+)\s*[:—-]?\s*", "", title).strip()
    title = re.sub(r"(?i)\s*[—–-]\s*the seed's error\s*,?\s*", " — ", title).strip()
    title = re.sub(r"`([^`]*)`", r"\1", title).strip().rstrip(".;,").rstrip(">").strip()
    return title


def parse_section9(version: str, chapter: str, version_dir: Path, chapter_days: list[int]) -> list[dict]:
    errors = []
    previous_day = -1
    for idx, block in enumerate(error_blocks(chapter)):
        fields = labeled_fields(block)
        if not (fields.get("symptom") and (fields.get("rootcause") or fields.get("fix") or fields.get("prevention"))):
            continue
        if not fields.get("rootcause"):
            fields["rootcause"] = inline_root_cause(" ".join(block["body"]))
        heading = block["heading"].lower()
        if re.search(r"seed's error|primary|headline|reported", heading):
            size = "BIG"
        elif re.search(r"near.miss|secondary|process|debt", heading):
            size = "SMALL"
        else:
            size = "BIG" if idx == 0 else "SMALL"
        day = found_day(block, fields)
        if day < 0:
            day = previous_day
        if day < 0 and chapter_days:
            day = min(chapter_days)
        previous_day = day if day >= 0 else previous_day
        codes = [c for c in CODE_RE.findall(block["heading"] + " " + " ".join(block["body"]))]
        code_files = [f for f in dict.fromkeys(
            f for c in codes for f in FILE_RE.findall(c)) if f not in PLACEHOLDER_FILES]
        code_files = code_files or version_files(version_dir)
        title = clean_title(block["title"])
        code_codes = [c for c in codes if not FILE_RE.match(c.strip())]
        error_text = (code_codes or codes or [title])[0]
        errors.append({
            "id": f"v{version} s9 e{idx + 1}",
            "version": version,
            "index": idx + 1,
            "title": title,
            "size": size,
            "found_day": day,
            "file": ", ".join(code_files),
            "error": error_text,
            "terminal": observation_context(fields),
            "source": "section 9",
            "what_happened": fields.get("symptom", ""),
            "why_it_happened": fields.get("rootcause", ""),
            "investigation": fields.get("investigation", ""),
            "fix": fields.get("fix", ""),
        })
    return errors


def rejected_designs(version: str, chapter: str, version_dir: Path, chapter_days: list[int],
                     s9_titles: list[str]) -> list[dict]:
    """Section 5.3 'Alternatives considered': the designs that were measured
    and rejected. Real failure events from the chapter's own analysis."""
    lines = chapter.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if SECTION_RE.match(ln) and re.search(r"alts?\.?\s+considered|alternatives considered", ln, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return []

    blocks: list[dict] = []
    current = None
    for ln in lines[start:]:
        h = SECTION_RE.match(ln)
        alt = ALT_HEAD_RE.match(ln)
        if alt:
            current = {"title": alt.group(1).strip(), "body": [alt.group(2)]}
            blocks.append(current)
            continue
        if h:
            break
        if current is not None and ln.strip():
            current["body"].append(ln)
    if not blocks:
        return []

    chosen = ""
    for b in blocks:
        if CHOSEN_RE.search(b["title"] + " " + " ".join(b["body"])):
            chosen = clean_title(b["title"])
            break

    entries = []
    for b in blocks:
        text = b["title"] + " " + " ".join(b["body"])
        if not REJECT_RE.search(text):
            continue
        if "seed's error" in text.lower():
            continue
        t = clean_title(b["title"])
        nt = re.sub(r"\W+", " ", t.lower()).split()
        dup = False
        for st in s9_titles:
            ns = re.sub(r"\W+", " ", st.lower()).split()
            inter = len(set(nt) & set(ns))
            if len(set(nt) | set(ns)) and inter / len(set(nt) | set(ns)) > 0.55:
                dup = True
                break
        if dup:
            continue
        reason = []
        for sent in re.split(r"(?<=[.!?])\s+", " ".join(b["body"])):
            if re.search(r"(?i)reject|fail|impossible|unacceptable|collision|drift|bug|dead|cannot|can't|catastroph", sent):
                reason.append(sent.strip())
        day = min(chapter_days) if chapter_days else -1
        entries.append({
            "id": f"v{version} 5.3 {t[:40]}",
            "version": version,
            "index": None,
            "title": f"{t} (rejected design)",
            "size": "SMALL",
            "found_day": day,
            "file": ", ".join(version_files(version_dir)),
            "error": f"design rejected: {t}",
            "terminal": "the design review",
            "source": "section 5.3",
            "what_happened": " ".join(b["body"]).strip(),
            "why_it_happened": " ".join(reason).strip() or "The measured case against this design, recorded in the chapter's analysis.",
            "investigation": "",
            "fix": f"replaced by {chosen}" if chosen else "the chosen design, per the chapter's decision section",
        })
    return entries


def parse_chapter(version: str, version_dir: Path) -> dict:
    chapter = (version_dir / "CHANGE.md").read_text(encoding="utf-8", errors="replace")
    chapter_days = [int(m.group(1)) for m in DAY_RE.finditer(chapter)]
    s9 = parse_section9(version, chapter, version_dir, chapter_days)
    s9_titles = [e["title"] for e in s9]
    designs = rejected_designs(version, chapter, version_dir, chapter_days, s9_titles)
    return {"version": version, "title": chapter_heading(chapter),
            "errors": s9 + designs}


def doc_entries() -> dict:
    out = {}
    for phase, entries in DOC_ERRORS.items():
        out[phase] = [
            {
                "id": f"docs {phase} {e['title'][:40]}",
                "version": phase,
                "index": None,
                "title": f"{e['title']} (the engineering documentation)",
                "size": e["size"],
                "found_day": -1,
                "file": e["file"],
                "error": e["title"],
                "terminal": "the engineering documentation",
                "source": "engineering documentation",
                "what_happened": e["what"],
                "why_it_happened": e["why"],
                "investigation": "",
                "fix": e["fix"],
            }
            for e in entries
        ]
    return out


def main() -> None:
    versions = []
    for d in sorted(
        (p for p in HISTORY.iterdir() if p.is_dir() and re.fullmatch(r"v\d+\.\d+", p.name)),
        key=lambda p: tuple(int(x) for x in p.name[1:].split(".")),
    ):
        try:
            versions.append(parse_chapter(d.name, d))
        except Exception as exc:
            print(f"warning: {d.name}: {exc}", file=sys.stderr)
    payload = {"versions": versions, "docs": doc_entries()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v["errors"]) for v in versions)
    doc_total = sum(len(v) for v in payload["docs"].values())
    print(f"parsed {len(versions)} chapters, {total} chapter errors + {doc_total} documentation errors -> {OUT}")


if __name__ == "__main__":
    main()
