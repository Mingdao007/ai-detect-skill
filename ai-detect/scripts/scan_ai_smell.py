#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = ROOT / "data" / "rules.json"
DEFAULT_QUEUE_PATH = ROOT / "data" / "review_queue.jsonl"


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("rules", [])


def load_queue(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def compile_patterns(rule: dict) -> list[re.Pattern[str]]:
    compiled = []
    for pattern in rule.get("patterns", []):
        pattern_type = pattern.get("type", "regex")
        value = pattern["value"]
        if pattern_type == "regex":
            compiled.append(re.compile(value, re.IGNORECASE))
        elif pattern_type == "exact":
            compiled.append(re.compile(re.escape(value), re.IGNORECASE))
    return compiled


def scan_confirmed(text: str, rules: list[dict]) -> list[tuple[int, dict, str]]:
    findings: list[tuple[int, dict, str]] = []
    seen = set()
    for idx, line in enumerate(text.splitlines(), start=1):
        for rule in rules:
            if rule.get("status") != "confirmed":
                continue
            for pattern in compile_patterns(rule):
                if pattern.search(line):
                    key = (idx, rule["rule_id"])
                    if key not in seen:
                        seen.add(key)
                        findings.append((idx, rule, line.strip()))
                    break
    return findings


def scan_pending(text: str, queue_entries: list[dict], rules: list[dict]) -> list[tuple[int, dict, str]]:
    findings: list[tuple[int, dict, str]] = []
    confirmed_patterns = []
    for rule in rules:
        if rule.get("status") == "confirmed":
            confirmed_patterns.extend(compile_patterns(rule))
    seen = set()
    for entry in queue_entries:
        if entry.get("status") != "pending":
            continue
        phrase_pattern = re.compile(re.escape(entry["phrase"]), re.IGNORECASE)
        if any(pattern.search(entry["phrase"]) for pattern in confirmed_patterns):
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if phrase_pattern.search(line):
                key = (idx, entry["candidate_id"])
                if key not in seen:
                    seen.add(key)
                    findings.append((idx, entry, line.strip()))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="First-pass scanner for user-specific AI-smelling phrasing."
    )
    parser.add_argument("file", help="Text-like file to scan")
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve()
    text = path.read_text(encoding="utf-8", errors="ignore")
    rules = load_rules(Path(args.rules))
    queue_entries = load_queue(Path(args.queue))
    confirmed_findings = scan_confirmed(text, rules)
    pending_findings = scan_pending(text, queue_entries, rules)

    if not confirmed_findings and not pending_findings:
        print("No confirmed or pending AI-smell signals matched.")
        return

    print(f"AI-smell scan for {path}")
    print()

    if confirmed_findings:
        print(f"Confirmed findings: {len(confirmed_findings)}")
        for line_no, rule, text_line in confirmed_findings:
            print(f"- line {line_no} [{rule['rule_id']} / {rule['category']}]")
            print(f"  text: {text_line}")
            print(f"  fix:  {rule['rewrite_direction']}")
    else:
        print("Confirmed findings: 0")

    print()

    if pending_findings:
        print(f"Needs user confirmation: {len(pending_findings)}")
        for line_no, entry, text_line in pending_findings:
            print(f"- line {line_no} [{entry['candidate_id']} / {entry['category_guess']}]")
            print(f"  text: {text_line}")
            print(f"  phrase: {entry['phrase']}")
            print(f"  source: {entry['source']}")
    else:
        print("Needs user confirmation: 0")


if __name__ == "__main__":
    main()
