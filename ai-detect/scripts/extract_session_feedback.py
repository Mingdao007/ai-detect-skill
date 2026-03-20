#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_PATH = ROOT / "data" / "review_queue.jsonl"
DEFAULT_RULES_PATH = ROOT / "data" / "rules.json"
SOURCE_ROOTS = {
    "codex": Path.home() / ".codex" / "sessions",
    "claude": Path.home() / ".claude" / "projects",
}
CATEGORY_PRIORITY = [
    "placeholder_title",
    "template_label",
    "meta_process",
    "fake_academic",
    "homework_title",
]
NOISE_MARKERS = (
    "# startup instruction payload instructions",
    "Base directory for this skill:",
    "You are Codex, a coding agent",
    "<skill>",
    "</skill>",
    "<proposed_plan>",
    "PLEASE IMPLEMENT THIS PLAN",
    "# Literature Review Deck Plan",
    "## Deck Structure",
    "*** Begin Patch",
    "Chunk ID:",
    "Wall time:",
    "Original token count:",
)
MAINTENANCE_MARKERS = (
    "ai-detect",
    "review_queue.jsonl",
    "rules.json",
    "extract_session_feedback.py",
    "scan_ai_smell.py",
    "Pending review candidates",
    "Needs user confirmation",
    "Confirmed findings",
    "第一批待你判",
    "待你判的",
    "算 AI",
    "不算 AI",
    "先保留待观察",
    "candidate_id",
    "审阅队列",
    "规则库",
    "候选如下",
)
CANDIDATE_PATTERNS = [
    (
        "placeholder_title",
        re.compile(
            r"\b(Final split|Final taxonomy|Candidate directions|Discussion for the next meeting|Mainline recent papers and venues|Why this review|Corpus and review pipeline)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "placeholder_title",
        re.compile(r"Recent Literature Review for(?:\s+[^\n]{0,80})?", re.IGNORECASE),
    ),
    (
        "template_label",
        re.compile(r"\bQuestion\s+\d+(?:\s*\([^)]+\))?:?", re.IGNORECASE),
    ),
    ("template_label", re.compile(r"\bAnswer:\b", re.IGNORECASE)),
    ("template_label", re.compile(r"\bTask\s+\d+(?:\s*\([^)]+\))?\b", re.IGNORECASE)),
    (
        "meta_process",
        re.compile(r"Directly answering(?:\s+[^\n,.]{0,80})?", re.IGNORECASE),
    ),
    (
        "meta_process",
        re.compile(
            r"what this deck is trying to do|main body:?|author synthesis:?|this slide shows",
            re.IGNORECASE,
        ),
    ),
    (
        "fake_academic",
        re.compile(
            r"Methods,\s*Taxonomy,\s*and\s*Candidate Directions|Three-column(?:\s+[^\n.]{0,80})?|the six cases are:",
            re.IGNORECASE,
        ),
    ),
    (
        "homework_title",
        re.compile(r"[A-Za-z0-9/ -]{0,40}Homework\s+\d+\s+Solutions", re.IGNORECASE),
    ),
]
REWRITE_DIRECTIONS = {
    "placeholder_title": "Replace workflow-like titles with the actual content title.",
    "template_label": "Replace template labels with the real subsection title or remove them.",
    "meta_process": "Delete process narration and keep only the final content.",
    "fake_academic": "Rewrite with shorter, discipline-native phrasing.",
    "homework_title": "Use the course title plus an assignment subtitle instead of a solutions-template title.",
}
DELIVERY_MARKERS = (
    ".tex",
    "deck.tex",
    "deck",
    "slide",
    "title",
    "subtitle",
    "section",
    "subsection",
    "caption",
    "figure",
    "table",
    "report",
    "review",
    "homework",
    "draft",
    "deliverable",
    "manuscript",
    "tex",
    "pdf",
    "page",
    "标题",
    "小节",
    "图注",
    "报告",
    "作业",
    "文稿",
    "交付",
    "命名",
    "幻灯片",
    "这一页",
)
PLAN_MARKERS = (
    "PLEASE IMPLEMENT THIS PLAN",
    "# Literature Review Deck Plan",
    "## Deck Structure",
    "## Deliverables",
    "## Visual And Build Rules",
    "## Test Plan",
    "## Assumptions",
    "<proposed_plan>",
)
FEEDBACK_MARKERS = (
    "你写这个干嘛",
    "不需要",
    "不要",
    "去掉",
    "改成",
    "改完",
    "不学术",
    "ai 味",
    "AI 味",
    "像ai",
    "像 AI",
    "典型 AI",
    "这句",
    "标题",
    "caption",
    "图注",
    "这一页",
    "line ",
    "已改成",
    "已按你说的改",
)


@dataclass(frozen=True)
class MessageRecord:
    source: str
    session_path: str
    timestamp: str
    speaker: str
    text: str
    sequence: int


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def looks_like_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if any(marker in stripped for marker in NOISE_MARKERS):
        return True
    if contains_marker(stripped, MAINTENANCE_MARKERS):
        return True
    if len(stripped) > 6000:
        return True
    if stripped.startswith("```") or stripped.count("```") >= 4:
        return True
    return False


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("rules", [])


def compile_rule_patterns(rules: list[dict]) -> list[tuple[dict, list[re.Pattern[str]]]]:
    compiled: list[tuple[dict, list[re.Pattern[str]]]] = []
    for rule in rules:
        patterns = []
        for pattern in rule.get("patterns", []):
            if pattern.get("type") == "regex":
                patterns.append(re.compile(pattern["value"], re.IGNORECASE))
            elif pattern.get("type") == "exact":
                patterns.append(re.compile(re.escape(pattern["value"]), re.IGNORECASE))
        compiled.append((rule, patterns))
    return compiled


def match_rule_status(phrase: str, compiled_rules: list[tuple[dict, list[re.Pattern[str]]]]) -> str:
    for rule, patterns in compiled_rules:
        for pattern in patterns:
            if pattern.search(phrase):
                return "confirmed" if rule.get("status") == "confirmed" else "pending"
    return "pending"


def load_queue(path: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        entries[entry["candidate_id"]] = entry
    return entries


def sort_queue(entries: list[dict]) -> list[dict]:
    return sorted(
        entries,
        key=lambda entry: (
            CATEGORY_PRIORITY.index(entry["category_guess"])
            if entry["category_guess"] in CATEGORY_PRIORITY
            else len(CATEGORY_PRIORITY),
            entry["status"] != "pending",
            entry["phrase"].lower(),
        ),
    )


def write_queue(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(entry, ensure_ascii=False) for entry in sort_queue(entries)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def iter_codex_messages(root: Path) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    for path in sorted(root.rglob("*.jsonl")):
        sequence = 0
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            text = ""
            speaker = ""
            if obj.get("type") == "response_item":
                payload = obj.get("payload", {})
                if payload.get("type") != "message":
                    continue
                speaker = payload.get("role", "")
                if speaker not in {"user", "assistant"}:
                    continue
                parts = []
                for item in payload.get("content", []):
                    if isinstance(item, dict):
                        value = item.get("text")
                        if isinstance(value, str):
                            parts.append(value)
                text = "\n".join(parts)
            elif obj.get("type") == "event_msg":
                payload = obj.get("payload", {})
                if payload.get("type") == "user_message":
                    speaker = "user"
                    text = payload.get("message", "")
                elif payload.get("type") == "agent_message":
                    speaker = "assistant"
                    text = payload.get("message", "")
            if not isinstance(text, str) or looks_like_noise(text):
                continue
            records.append(
                MessageRecord(
                    source="codex",
                    session_path=str(path),
                    timestamp=str(obj.get("timestamp", "")),
                    speaker=speaker,
                    text=text,
                    sequence=sequence,
                )
            )
            sequence += 1
    return dedupe_records(records)


def iter_claude_messages(root: Path) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    for path in sorted(root.rglob("*.jsonl")):
        sequence = 0
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            speaker = obj.get("type")
            if speaker not in {"user", "assistant"}:
                continue
            message = obj.get("message", {})
            parts = []
            if isinstance(message, dict):
                for item in message.get("content", []):
                    if isinstance(item, dict):
                        value = item.get("text")
                        if isinstance(value, str):
                            parts.append(value)
            text = "\n".join(parts)
            if looks_like_noise(text):
                continue
            records.append(
                MessageRecord(
                    source="claude",
                    session_path=str(path),
                    timestamp=str(obj.get("timestamp", "")),
                    speaker=speaker,
                    text=text,
                    sequence=sequence,
                )
            )
            sequence += 1
    return dedupe_records(records)


def dedupe_records(records: list[MessageRecord]) -> list[MessageRecord]:
    seen = set()
    deduped = []
    for record in records:
        key = (
            record.source,
            record.session_path,
            record.timestamp,
            record.speaker,
            normalize_text(record.text),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return sorted(deduped, key=lambda record: (record.source, record.session_path, record.sequence, record.timestamp))


def normalize_phrase(phrase: str) -> str:
    cleaned = phrase.strip().strip("`'\"“”")
    return normalize_text(cleaned.rstrip(".,;，。？！?"))


def candidate_id(category: str, phrase: str) -> str:
    digest = hashlib.sha1(f"{category}|{phrase.lower()}".encode("utf-8")).hexdigest()
    return digest[:12]


def line_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return line_start, line_end


def is_candidate_like(record: MessageRecord, match: re.Match[str], category: str) -> bool:
    line_start, line_end = line_bounds(record.text, match.start(), match.end())
    line = record.text[line_start:line_end].strip()
    phrase = normalize_phrase(match.group(0))
    if not phrase or not line:
        return False

    wrapped_in_ticks = f"`{match.group(0)}`" in record.text[max(0, match.start() - 2) : min(len(record.text), match.end() + 2)]
    starts_line = line.startswith(match.group(0)) or line.startswith(f"`{match.group(0)}`")
    ends_line = line.endswith(match.group(0)) or line.endswith(f"`{match.group(0)}`")
    short_line = len(line) <= max(90, len(phrase) + 40)

    if category in {"placeholder_title", "template_label", "homework_title"}:
        if match.group(0).lower().startswith("question ") and not match.group(0).startswith("Question"):
            return False
        if "/".join([match.group(0), ""]) in line:
            return False
        if short_line and (wrapped_in_ticks or starts_line or ends_line):
            return True
        return False

    return short_line or wrapped_in_ticks


def is_delivery_relevant(
    session_records: list[MessageRecord], record_index: int, match: re.Match[str], category: str
) -> bool:
    current = session_records[record_index]
    line_start, line_end = line_bounds(current.text, match.start(), match.end())
    line = current.text[line_start:line_end]
    neighbor_texts = [current.text]
    if record_index > 0:
        neighbor_texts.append(session_records[record_index - 1].text)
    if record_index + 1 < len(session_records):
        neighbor_texts.append(session_records[record_index + 1].text)
    haystack = normalize_text("\n".join(neighbor_texts))
    haystack_lower = haystack.lower()
    if contains_marker(haystack_lower, MAINTENANCE_MARKERS):
        return False
    has_plan_marker = contains_marker(haystack_lower, PLAN_MARKERS)
    has_feedback_marker = contains_marker(haystack_lower, FEEDBACK_MARKERS)
    has_delivery_marker = contains_marker(haystack_lower, DELIVERY_MARKERS)
    if has_plan_marker and not has_feedback_marker:
        return False
    if has_feedback_marker and has_delivery_marker:
        return True
    if category == "homework_title":
        return True
    if f"`{match.group(0)}`" in line and has_feedback_marker:
        return True
    if current.speaker == "assistant" and has_delivery_marker and has_feedback_marker:
        return True
    return False


def render_message_block(title: str, record: MessageRecord) -> str:
    return f"{title} ({record.speaker}, {record.timestamp}):\n{record.text.strip()}"


def is_context_message(record: MessageRecord) -> bool:
    if looks_like_noise(record.text):
        return False
    text = record.text
    return contains_marker(text, DELIVERY_MARKERS) or contains_marker(text, FEEDBACK_MARKERS)


def find_context_neighbor(
    session_records: list[MessageRecord], start_index: int, step: int, current_text: str
) -> MessageRecord | None:
    index = start_index + step
    while 0 <= index < len(session_records):
        record = session_records[index]
        if normalize_text(record.text) != normalize_text(current_text) and is_context_message(record):
            return record
        index += step
    return None


def build_review_context(
    session_records: list[MessageRecord], record_index: int, match: re.Match[str]
) -> str:
    current = session_records[record_index]
    line_start, line_end = line_bounds(current.text, match.start(), match.end())
    matched_line = current.text[line_start:line_end].strip()
    parts = []
    previous = find_context_neighbor(session_records, record_index, -1, current.text)
    next_record = find_context_neighbor(session_records, record_index, 1, current.text)
    if previous is not None:
        parts.append(render_message_block("Previous relevant message", previous))
    parts.append(f"Matched line:\n{matched_line}")
    parts.append(render_message_block("Current message", current))
    if next_record is not None:
        parts.append(render_message_block("Next relevant message", next_record))
    return "\n\n---\n\n".join(parts)


def extract_candidates(
    records: list[MessageRecord], compiled_rules: list[tuple[dict, list[re.Pattern[str]]]]
) -> list[dict]:
    seen_ids = set()
    candidates = []
    grouped: dict[tuple[str, str], list[MessageRecord]] = {}
    for record in records:
        grouped.setdefault((record.source, record.session_path), []).append(record)
    for session_records in grouped.values():
        for record_index, record in enumerate(session_records):
            for category, pattern in CANDIDATE_PATTERNS:
                for match in pattern.finditer(record.text):
                    if not is_candidate_like(record, match, category):
                        continue
                    if not is_delivery_relevant(session_records, record_index, match, category):
                        continue
                    phrase = normalize_phrase(match.group(0))
                    if not phrase:
                        continue
                    identifier = candidate_id(category, phrase)
                    if identifier in seen_ids:
                        continue
                    seen_ids.add(identifier)
                    candidates.append(
                        {
                            "candidate_id": identifier,
                            "source": record.source,
                            "session_path": record.session_path,
                            "timestamp": record.timestamp,
                            "speaker": record.speaker,
                            "category_guess": category,
                            "phrase": phrase,
                            "context": build_review_context(session_records, record_index, match),
                            "status": match_rule_status(phrase, compiled_rules),
                            "user_note": "",
                        }
                    )
    return candidates


def merge_candidates(existing: dict[str, dict], extracted: list[dict]) -> list[dict]:
    merged = dict(existing)
    for candidate in extracted:
        current = merged.get(candidate["candidate_id"])
        if current is None:
            merged[candidate["candidate_id"]] = candidate
            continue
        if len(candidate.get("context", "")) > len(current.get("context", "")):
            current["context"] = candidate["context"]
        if not current.get("timestamp"):
            current["timestamp"] = candidate["timestamp"]
    return list(merged.values())


def rule_from_candidate(candidate: dict) -> dict:
    phrase = candidate["phrase"]
    category = candidate["category_guess"]
    escaped_phrase = re.escape(phrase).replace(r"\ ", " ")
    if category in {"placeholder_title", "template_label"}:
        pattern_value = rf"^\s*{escaped_phrase}\s*$"
    else:
        pattern_value = escaped_phrase
    slug = re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")[:48] or candidate["candidate_id"]
    return {
        "rule_id": f"{category}__{slug}",
        "category": category,
        "status": "confirmed",
        "patterns": [{"type": "regex", "value": pattern_value}],
        "examples": [phrase],
        "rewrite_direction": REWRITE_DIRECTIONS[category],
        "evidence_count": 1,
    }


def upsert_rule(rules: list[dict], candidate: dict) -> None:
    compiled_rules = compile_rule_patterns(rules)
    for rule, patterns in compiled_rules:
        for pattern in patterns:
            if pattern.search(candidate["phrase"]):
                rule["status"] = "confirmed"
                if candidate["phrase"] not in rule["examples"]:
                    rule["examples"].append(candidate["phrase"])
                rule["evidence_count"] = len(rule["examples"])
                return
    rules.append(rule_from_candidate(candidate))


def write_rules(path: Path, rules: list[dict]) -> None:
    path.write_text(
        json.dumps({"version": 1, "rules": rules}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def print_batch(entries: list[dict], limit: int, category: str) -> None:
    pending = [entry for entry in entries if entry["status"] == "pending"]
    if category != "all":
        pending = [entry for entry in pending if entry["category_guess"] == category]
    pending = sort_queue(pending)[:limit]
    if not pending:
        print("No pending review candidates.")
        return
    print(f"Pending review candidates: {len(pending)}")
    for entry in pending:
        print(f"- [{entry['candidate_id']}] {entry['category_guess']}")
        print(f"  phrase: {entry['phrase']}")
        print(f"  source: {entry['source']} / {entry['speaker']}")
        print(f"  session: {entry['session_path']}")
        print("  context:")
        for line in entry["context"].splitlines():
            print(f"    {line}")


def cmd_extract(args: argparse.Namespace) -> None:
    rules = load_rules(Path(args.rules))
    compiled_rules = compile_rule_patterns(rules)
    queue = load_queue(Path(args.queue))
    records: list[MessageRecord] = []
    source_names = SOURCE_ROOTS.keys() if args.source == "all" else [args.source]
    for source_name in source_names:
        root = SOURCE_ROOTS[source_name]
        if not root.exists():
            continue
        if source_name == "codex":
            records.extend(iter_codex_messages(root))
        elif source_name == "claude":
            records.extend(iter_claude_messages(root))
    extracted = extract_candidates(records, compiled_rules)
    merged = merge_candidates(queue, extracted)
    if not args.dry_run:
        write_queue(Path(args.queue), merged)
    counts = Counter(entry["category_guess"] for entry in extracted)
    print(f"Extracted {len(extracted)} unique candidates from {len(records)} messages.")
    for category in CATEGORY_PRIORITY:
        if counts[category]:
            print(f"- {category}: {counts[category]}")
    print(f"Queue path: {args.queue}")


def cmd_next(args: argparse.Namespace) -> None:
    entries = list(load_queue(Path(args.queue)).values())
    print_batch(entries, args.limit, args.category)


def cmd_judge(args: argparse.Namespace) -> None:
    queue_path = Path(args.queue)
    rules_path = Path(args.rules)
    entries = load_queue(queue_path)
    rules = load_rules(rules_path)
    updated = []
    for identifier in args.candidate_id:
        if identifier not in entries:
            raise SystemExit(f"Unknown candidate_id: {identifier}")
        entry = entries[identifier]
        entry["status"] = args.decision
        entry["user_note"] = args.note
        updated.append(entry)
        if args.decision == "confirmed":
            upsert_rule(rules, entry)
    write_queue(queue_path, list(entries.values()))
    write_rules(rules_path, rules)
    print(f"Updated {len(updated)} candidate(s) to {args.decision}.")
    for entry in updated:
        print(f"- {entry['candidate_id']} {entry['phrase']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract and review AI-smell candidates from Codex and Claude CLI session logs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract candidates into the review queue.")
    extract_parser.add_argument(
        "--source",
        choices=["all", "codex", "claude"],
        default="all",
        help="Which session source to parse.",
    )
    extract_parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    extract_parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    extract_parser.add_argument("--dry-run", action="store_true")
    extract_parser.set_defaults(func=cmd_extract)

    next_parser = subparsers.add_parser("next", help="Show the next pending review batch.")
    next_parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    next_parser.add_argument(
        "--category",
        choices=["all", *CATEGORY_PRIORITY],
        default="all",
    )
    next_parser.add_argument("--limit", type=int, default=3)
    next_parser.set_defaults(func=cmd_next)

    judge_parser = subparsers.add_parser("judge", help="Record a user judgment for one or more candidates.")
    judge_parser.add_argument("candidate_id", nargs="+")
    judge_parser.add_argument(
        "--decision",
        required=True,
        choices=["confirmed", "rejected", "pending"],
    )
    judge_parser.add_argument("--note", default="")
    judge_parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    judge_parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    judge_parser.set_defaults(func=cmd_judge)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
