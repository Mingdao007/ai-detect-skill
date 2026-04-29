#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = ROOT / "data" / "rules.json"
DEFAULT_QUEUE_PATH = ROOT / "data" / "review_queue.jsonl"
REDUNDANCY_SCANNER = ROOT / "redundancy" / "scripts" / "scan_redundancy.py"
DISPLAY_OPEN_RE = re.compile(r"^\s*\\\[\s*$")
DISPLAY_CLOSE_RE = re.compile(r"^\s*\\\]\s*$")
OVERFULL_HBOX_RE = re.compile(
    r"Overfull \\hbox \((?P<amount>[^)]+)\) detected at line(?:s)? "
    r"(?P<start>\d+)(?:--(?P<end>\d+))?"
)
INLINE_DOLLAR_MATH_RE = re.compile(r"\$[^$]*\$")
INLINE_PAREN_MATH_RE = re.compile(r"\\\([^)]*\\\)")
INLINE_MATH_SINGLE_DASH_WORD_RE = re.compile(
    r"(\\\([^)]*\\\)|\$[^$]*\$)-[A-Za-z]"
)
VISIBLE_SINGLE_HYPHEN_COMPOUND_RE = re.compile(
    r"(?<!-)\b[A-Za-z0-9]+(?:'[A-Za-z]+)?-[A-Za-z0-9]+(?:'[A-Za-z]+)?\b(?!-)"
)
REDUNDANCY_CATEGORIES = {"redundant_filler", "empty_contrast", "sequencer_label"}
OPTION_BLOCK_RE = re.compile(r"\[[^\]]*\]")
COMMAND_NAME_RE = re.compile(r"\\[A-Za-z@]+(?:\*)?")
COMMAND_SYMBOL_RE = re.compile(r"\\.")
PAREN_LABEL_RE = re.compile(r"\([A-Za-z0-9_.:-]+\)")
VISIBLE_TEXT_CLEAN_RE = re.compile(r"[^A-Za-z0-9\s,.;:!?'\-]")
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
FRAME_BEGIN_RE = re.compile(r"^\s*\\begin\{frame\}(?:\[.*\])?")
FRAME_END_RE = re.compile(r"^\s*\\end\{frame\}")
SIMPLE_NEWCOMMAND_RE = re.compile(r"\\newcommand\{\\([A-Za-z@]+)\}\{(.+)\}")
BODY_CITATION_RE = re.compile(r"(?<!\\textbf\{)\[(\d+)\]")
FOOTER_ENTRY_RE = re.compile(r"\\textbf\{\[(\d+)\]\}\s*(.+)")
REDUNDANCY_CONNECTOR_RE = re.compile(
    r"(?P<lhs>.+?)(?:,\s*not\s+(?P<rhs_not>.+)|\brather than\b\s+(?P<rhs_rather>.+)|\binstead of\b\s+(?P<rhs_instead>.+))$",
    re.IGNORECASE,
)
PROSE_SKIP_PREFIXES = (
    r"\begin{",
    r"\end{",
    r"\toprule",
    r"\midrule",
    r"\bottomrule",
    r"\hline",
    r"\vspace",
    r"\smallskip",
    r"\medskip",
    r"\bigskip",
    r"\centering",
    r"\raggedright",
    r"\raggedleft",
    r"\scriptsize",
    r"\tiny",
    r"\small",
    r"\footnotesize",
    r"\normalsize",
    r"\large",
    r"\Large",
    r"\renewcommand",
    r"\setlength",
    r"\includegraphics",
    r"\draw",
    r"\path",
    r"\fill",
    r"\clip",
    r"\paperfooter",
    r"\softfooter",
    r"\label",
    r"\ref",
    r"\cite",
    r"\url",
)
GENERIC_REDUNDANCY_HEADS = {
    "list",
    "paper",
    "way",
    "thing",
    "part",
    "choice",
    "process",
    "workflow",
    "step",
    "point",
    "section",
    "story",
    "structure",
    "sequence",
}
GENERIC_REDUNDANCY_MODIFIERS = {
    "unrelated",
    "different",
    "various",
    "general",
    "overall",
    "simple",
    "separate",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "more",
    "not",
    "of",
    "on",
    "or",
    "our",
    "part",
    "should",
    "so",
    "still",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "we",
    "what",
    "when",
    "where",
    "which",
    "why",
    "will",
    "with",
}


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


def scan_redundancy_subskill(path: Path) -> dict:
    proc = subprocess.run(
        [
            "python3",
            str(REDUNDANCY_SCANNER),
            str(path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "redundancy subskill scan failed")
    return json.loads(proc.stdout)


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


def tex_body_lines(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    in_document = False
    body: list[tuple[int, str]] = []
    for line_no, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if stripped.startswith(r"\begin{document}"):
            in_document = True
            continue
        if stripped.startswith(r"\end{document}"):
            break
        if in_document:
            body.append((line_no, raw_line))
    return body


def strip_tex_comment(raw_line: str) -> str:
    pieces: list[str] = []
    escaped = False
    for char in raw_line:
        if char == "%" and not escaped:
            break
        pieces.append(char)
        escaped = (char == "\\") and not escaped
        if char != "\\":
            escaped = False
    return "".join(pieces)


def extract_visible_text(raw_line: str) -> str:
    text = strip_tex_comment(raw_line)
    text = INLINE_DOLLAR_MATH_RE.sub(" ", text)
    text = INLINE_PAREN_MATH_RE.sub(" ", text)
    text = OPTION_BLOCK_RE.sub(" ", text)
    text = COMMAND_NAME_RE.sub(" ", text)
    text = COMMAND_SYMBOL_RE.sub(" ", text)
    text = PAREN_LABEL_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("&", " ")
    text = text.replace("^", " ")
    text = text.replace("_", " ")
    text = text.replace("~", " ")
    text = text.replace("\\\\", " ")
    text = VISIBLE_TEXT_CLEAN_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def looks_like_english_prose(raw_line: str, visible_text: str) -> bool:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("%"):
        return False
    if any(stripped.startswith(prefix) for prefix in PROSE_SKIP_PREFIXES):
        return False
    if r"\paperfooter{" in raw_line or r"\includegraphics" in raw_line:
        return False
    if "&" in raw_line:
        return False
    if len(visible_text) < 18:
        return False
    tokens = WORD_RE.findall(visible_text)
    if len(tokens) < 5:
        return False
    if sum(1 for token in tokens if len(token) >= 3) < 3:
        return False
    alpha_chars = sum(1 for char in visible_text if char.isalpha())
    ascii_alpha_chars = sum(
        1 for char in visible_text if char.isascii() and char.isalpha()
    )
    if alpha_chars == 0 or ascii_alpha_chars / alpha_chars < 0.9:
        return False
    return True


def normalize_token(token: str) -> str:
    token = token.lower()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def content_tokens(text: str) -> list[str]:
    tokens = [normalize_token(token) for token in WORD_RE.findall(text)]
    return [token for token in tokens if token not in STOPWORDS and len(token) >= 3]


def prose_units(text: str) -> list[dict]:
    units: list[dict] = []
    for line_no, raw_line in tex_body_lines(text):
        visible = extract_visible_text(raw_line)
        if not looks_like_english_prose(raw_line, visible):
            continue
        segments = [seg.strip() for seg in SENTENCE_SPLIT_RE.split(visible) if seg.strip()]
        if not segments:
            segments = [visible]
        for segment in segments:
            tokens = content_tokens(segment)
            if len(tokens) < 4:
                continue
            units.append(
                {
                    "line_no": line_no,
                    "raw_line": raw_line.strip(),
                    "text": segment,
                    "tokens": tokens,
                }
            )
    return units


def scan_redundancy(text: str, excluded_lines: set[int]) -> list[dict]:
    findings: list[dict] = []
    units = prose_units(text)

    for unit in units:
        if unit["line_no"] in excluded_lines:
            continue
        lowered = unit["text"].lower()
        if "not only" in lowered and "but also" in lowered:
            continue
        contrast_match = REDUNDANCY_CONNECTOR_RE.search(unit["text"])
        if not contrast_match:
            continue
        lhs = (contrast_match.group("lhs") or "").strip(" ,.;:")
        rhs = (
            contrast_match.group("rhs_not")
            or contrast_match.group("rhs_rather")
            or contrast_match.group("rhs_instead")
            or ""
        ).strip(" ,.;:")
        lhs_tokens = set(content_tokens(lhs))
        rhs_tokens = content_tokens(rhs)
        rhs_new = {token for token in rhs_tokens if token not in lhs_tokens}
        if not rhs_tokens or len(rhs_tokens) > 6:
            continue
        if not any(token in GENERIC_REDUNDANCY_HEADS for token in rhs_tokens):
            continue
        if rhs_new and not all(
            token in GENERIC_REDUNDANCY_HEADS or token in GENERIC_REDUNDANCY_MODIFIERS
            for token in rhs_new
        ):
            continue
        findings.append(
            {
                "kind": "heuristic_empty_contrast",
                "line_no": unit["line_no"],
                "text": unit["text"],
                "fix": (
                    "the contrast clause adds mostly generic wording with little new "
                    "information; delete it or replace it with the real distinction."
                ),
            }
        )

    for previous, current in zip(units, units[1:]):
        if previous["line_no"] in excluded_lines or current["line_no"] in excluded_lines:
            continue
        previous_tokens = set(previous["tokens"])
        current_tokens = set(current["tokens"])
        if len(previous_tokens) < 5 or len(current_tokens) < 5:
            continue
        overlap = len(previous_tokens & current_tokens) / min(
            len(previous_tokens), len(current_tokens)
        )
        new_tokens = current_tokens - previous_tokens
        if overlap < 0.82 or len(new_tokens) > 1:
            continue
        findings.append(
            {
                "kind": "heuristic_adjacent_restatement",
                "line_no": previous["line_no"],
                "end_line_no": current["line_no"],
                "text": previous["text"],
                "next_text": current["text"],
                "fix": (
                    "the later sentence mostly restates the earlier one with little new "
                    "information; merge them or delete the weaker sentence."
                ),
            }
        )

    deduped: list[dict] = []
    seen = set()
    for finding in findings:
        key = (
            finding["kind"],
            finding["line_no"],
            finding.get("end_line_no", finding["line_no"]),
            finding["text"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


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


def iter_display_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if "\\begin{equation}" in line:
            start = idx + 1
            end = idx + 1
            while end < len(lines) and "\\end{equation}" not in lines[end]:
                end += 1
            blocks.append((start, end + 1, "equation"))
            idx = end
        elif DISPLAY_OPEN_RE.match(line):
            start = idx + 1
            end = idx + 1
            while end < len(lines) and not DISPLAY_CLOSE_RE.match(lines[end]):
                end += 1
            blocks.append((start, end + 1, "display"))
            idx = end
        idx += 1
    return blocks


def last_content_line(lines: list[str], start: int, end: int) -> tuple[int, str]:
    for line_no in range(end - 1, start - 1, -1):
        stripped = lines[line_no - 1].strip()
        if not stripped or stripped.startswith("%"):
            continue
        if stripped in {"\\]", "\\end{equation}"} or "\\tag{" in stripped:
            continue
        return line_no, stripped
    return 0, ""


def next_nonempty_line(lines: list[str], line_no: int) -> tuple[int, str]:
    for next_line_no in range(line_no + 1, len(lines) + 1):
        stripped = lines[next_line_no - 1].strip()
        if stripped and not stripped.startswith("%"):
            return next_line_no, stripped
    return 0, ""


def starts_with_lowercase_prose(text_line: str) -> bool:
    if not text_line or text_line.startswith("\\"):
        return False
    first = text_line[0]
    return first.isalpha() and first.islower()


def scan_punctuation(text: str) -> list[dict]:
    lines = text.splitlines()
    findings: list[dict] = []
    for start, end, kind in iter_display_blocks(lines):
        last_line_no, last_text = last_content_line(lines, start, end)
        next_line_no, next_text = next_nonempty_line(lines, end)
        if not last_text or not next_text:
            continue
        punct = last_text[-1] if last_text[-1] in ".,;:" else ""
        if starts_with_lowercase_prose(next_text) and punct not in {",", ";", ":"}:
            findings.append(
                {
                    "kind": kind,
                    "line_no": last_line_no,
                    "text": last_text,
                    "punct": punct or "(none)",
                    "next_line_no": next_line_no,
                    "next_text": next_text,
                }
            )
    return findings


def strip_inline_math(line: str) -> str:
    line = INLINE_DOLLAR_MATH_RE.sub("", line)
    line = INLINE_PAREN_MATH_RE.sub("", line)
    return line


def scan_tex_dash_punctuation(text: str) -> list[dict]:
    lines = text.splitlines()
    display_lines: set[int] = set()
    for start, end, _kind in iter_display_blocks(lines):
        display_lines.update(range(start, end + 1))

    findings: list[dict] = []
    for line_no, raw_line in enumerate(lines, start=1):
        if line_no in display_lines:
            continue
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        raw_has_prose_dash = " - " in strip_inline_math(raw_line)
        raw_has_inline_math_dash = bool(INLINE_MATH_SINGLE_DASH_WORD_RE.search(raw_line))
        visible_text = extract_visible_text(raw_line)
        visible_has_single_hyphen = False
        if (
            visible_text
            and r"\includegraphics" not in raw_line
            and r"\url{" not in raw_line
            and r"\href{" not in raw_line
            and "http://" not in raw_line
            and "https://" not in raw_line
        ):
            visible_has_single_hyphen = bool(
                VISIBLE_SINGLE_HYPHEN_COMPOUND_RE.search(visible_text)
            )
        if (
            not raw_has_prose_dash
            and not raw_has_inline_math_dash
            and not visible_has_single_hyphen
        ):
            continue
        if raw_has_inline_math_dash:
            findings.append(
                {
                    "line_no": line_no,
                    "text": stripped,
                    "kind": "inline_math_dash_word",
                }
            )
        if raw_has_prose_dash:
            findings.append(
                {
                    "line_no": line_no,
                    "text": stripped,
                    "kind": "prose_dash",
                }
            )
        if visible_has_single_hyphen:
            findings.append(
                {
                    "line_no": line_no,
                    "text": visible_text,
                    "kind": "single_hyphen_compound",
                }
            )
    return findings


def overfull_excerpt(lines: list[str], start: int, end: int) -> str:
    pieces: list[str] = []
    for idx in range(start, min(end, len(lines)) + 1):
        stripped = lines[idx - 1].strip()
        if stripped and not stripped.startswith("%"):
            pieces.append(stripped)
        if len(" ".join(pieces)) > 160:
            break
    if not pieces and 1 <= start <= len(lines):
        pieces.append(lines[start - 1].strip())
    return " ".join(pieces)[:180]


def scan_overflow(path: Path, text: str) -> list[dict]:
    if path.suffix != ".tex":
        return []
    log_path = path.with_suffix(".log")
    if not log_path.exists():
        return []
    lines = text.splitlines()
    findings: list[dict] = []
    seen = set()
    log_text = log_path.read_text(encoding="utf-8", errors="ignore")
    for log_line in log_text.splitlines():
        match = OVERFULL_HBOX_RE.search(log_line)
        if not match:
            continue
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        amount = match.group("amount")
        key = (start, end, amount)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "line_no": start,
                "end_line_no": end,
                "amount": amount,
                "text": overfull_excerpt(lines, start, end),
            }
        )
    return findings


def parse_simple_macros(text: str) -> dict[str, str]:
    macros: dict[str, str] = {}
    for raw_line in text.splitlines():
        match = SIMPLE_NEWCOMMAND_RE.search(raw_line.strip())
        if not match:
            continue
        macros[f"\\{match.group(1)}"] = match.group(2)
    return macros


def iter_frames(lines: list[str]) -> list[tuple[int, int]]:
    frames: list[tuple[int, int]] = []
    start_line = None
    for idx, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if FRAME_BEGIN_RE.match(stripped):
            start_line = idx
            continue
        if FRAME_END_RE.match(stripped) and start_line is not None:
            frames.append((start_line, idx))
            start_line = None
    return frames


def split_frame_body_and_footer(
    frame_lines: list[tuple[int, str]]
) -> tuple[list[tuple[int, str]], str]:
    body_lines: list[tuple[int, str]] = []
    footer_lines: list[str] = []
    in_footer = False
    brace_balance = 0

    for _line_no, raw_line in frame_lines:
        if not in_footer and r"\paperfooter{" in raw_line:
            in_footer = True
            footer_lines.append(raw_line)
            brace_balance += raw_line.count("{") - raw_line.count("}")
            if brace_balance <= 0:
                in_footer = False
                brace_balance = 0
            continue
        if in_footer:
            footer_lines.append(raw_line)
            brace_balance += raw_line.count("{") - raw_line.count("}")
            if brace_balance <= 0:
                in_footer = False
                brace_balance = 0
            continue
        body_lines.append((_line_no, raw_line))

    return body_lines, "\n".join(footer_lines)


def expand_known_macros(text: str, macros: dict[str, str]) -> str:
    expanded = text
    for name, body in macros.items():
        expanded = expanded.replace(name, body)
    return expanded


def extract_footer_refs(footer_text: str, macros: dict[str, str]) -> list[dict]:
    if not footer_text:
        return []
    footer_text = expand_known_macros(footer_text, macros)
    footer_text = footer_text.replace(r"\paperfooter{", "", 1).strip()
    if footer_text.endswith("}"):
        footer_text = footer_text[:-1].strip()
    entries = [entry.strip() for entry in footer_text.split(r"\\") if entry.strip()]
    refs: list[dict] = []
    for entry in entries:
        match = FOOTER_ENTRY_RE.search(entry)
        if not match:
            continue
        ref_num = int(match.group(1))
        ref_text = match.group(2).strip()
        refs.append(
            {
                "num": ref_num,
                "text": ref_text,
                "style": "full" if "``" in ref_text or "''" in ref_text else "short",
            }
        )
    return refs


def extract_body_citations(body_lines: list[tuple[int, str]]) -> set[int]:
    citations: set[int] = set()
    for _line_no, raw_line in body_lines:
        line = strip_tex_comment(raw_line)
        for match in BODY_CITATION_RE.finditer(line):
            citations.add(int(match.group(1)))
    return citations


def scan_reference_consistency(path: Path, text: str) -> list[dict]:
    if path.suffix != ".tex":
        return []
    lines = text.splitlines()
    macros = parse_simple_macros(text)
    findings: list[dict] = []
    footer_styles: list[tuple[int, str, str]] = []

    for frame_start, frame_end in iter_frames(lines):
        frame_lines = [
            (line_no, lines[line_no - 1])
            for line_no in range(frame_start, frame_end + 1)
        ]
        body_lines, footer_text = split_frame_body_and_footer(frame_lines)
        body_citations = extract_body_citations(body_lines)
        footer_refs = extract_footer_refs(footer_text, macros)
        footer_nums = {ref["num"] for ref in footer_refs}

        for ref in footer_refs:
            footer_styles.append((frame_start, ref["style"], ref["text"]))

        missing = sorted(body_citations - footer_nums)
        if missing:
            findings.append(
                {
                    "kind": "missing_footer_reference",
                    "line_no": frame_start,
                    "text": f"frame citations {sorted(body_citations)}",
                    "fix": (
                        "each citation number used in the frame body must appear exactly "
                        "once in the frame footer reference list."
                    ),
                }
            )

        unused = sorted(footer_nums - body_citations)
        if unused:
            findings.append(
                {
                    "kind": "unused_footer_reference",
                    "line_no": frame_start,
                    "text": f"frame footer references {sorted(footer_nums)}",
                    "fix": (
                        "do not keep footer references that are not cited in the frame "
                        "body."
                    ),
                }
            )

    style_kinds = {style for _line_no, style, _text in footer_styles}
    if len(style_kinds) > 1:
        sample_full = next(
            (text for _line_no, style, text in footer_styles if style == "full"),
            "",
        )
        sample_short = next(
            (text for _line_no, style, text in footer_styles if style == "short"),
            "",
        )
        findings.append(
            {
                "kind": "mixed_footer_reference_style",
                "line_no": 1,
                "text": f"full={sample_full} | short={sample_short}",
                "fix": (
                    "keep one footer reference style across the whole deck; do not mix "
                    "short venue-only references with full title references."
                ),
            }
        )

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="First-pass scanner for Mingdao-specific AI-smelling phrasing."
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
    punctuation_findings = scan_punctuation(text) if path.suffix == ".tex" else []
    dash_findings = scan_tex_dash_punctuation(text) if path.suffix == ".tex" else []
    overflow_findings = scan_overflow(path, text)
    reference_findings = scan_reference_consistency(path, text)
    redundancy_result = scan_redundancy_subskill(path)
    redundancy_findings = redundancy_result.get("confirmed_findings", [])
    for finding in redundancy_result.get("needs_user_confirmation", []):
        entry = {
            "candidate_id": finding["candidate_id"],
            "category_guess": finding["category_guess"],
            "phrase": finding["phrase"],
            "source": finding.get("source", "redundancy"),
        }
        pending_findings.append((finding["line_no"], entry, finding["text"]))

    if (
        not confirmed_findings
        and not pending_findings
        and not punctuation_findings
        and not dash_findings
        and not overflow_findings
        and not reference_findings
        and not redundancy_findings
    ):
        print("No confirmed or pending AI-smell signals matched.")
        print("Punctuation diagnostics: 0")
        print("Dash diagnostics: 0")
        print("Overflow diagnostics: 0")
        print("Reference diagnostics: 0")
        print("Redundancy diagnostics: 0")
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

    print()

    if punctuation_findings:
        print(f"Punctuation diagnostics: {len(punctuation_findings)}")
        for finding in punctuation_findings:
            print(
                "- line "
                f"{finding['line_no']} [display_continuation_punctuation / {finding['kind']}]"
            )
            print(f"  text: {finding['text']}")
            print(
                f"  next: line {finding['next_line_no']} -> {finding['next_text']}"
            )
            print(
                "  fix:  displayed math continues into lowercase prose; end the display "
                "with ',' or another continuation mark instead of a period."
            )
    else:
        print("Punctuation diagnostics: 0")

    print()

    if dash_findings:
        print(f"Dash diagnostics: {len(dash_findings)}")
        for finding in dash_findings:
            print(f"- line {finding['line_no']} [tex_{finding['kind']}]")
            print(f"  text: {finding['text']}")
            if finding["kind"] == "inline_math_dash_word":
                print(
                    "  fix:  when inline math is followed by an English noun phrase "
                    "in LaTeX prose, use '--' rather than a single '-' between them."
                )
            elif finding["kind"] == "single_hyphen_compound":
                print(
                    "  fix:  in LaTeX visible prose, use '--' rather than a single "
                    "'-' between English tokens."
                )
            else:
                print(
                    "  fix:  in LaTeX prose, use '--' for dash punctuation; keep single "
                    "'-' only for mathematical minus signs or non-prose literal syntax."
                )
    else:
        print("Dash diagnostics: 0")

    print()

    if overflow_findings:
        print(f"Overflow diagnostics: {len(overflow_findings)}")
        for finding in overflow_findings:
            line_span = (
                f"{finding['line_no']}"
                if finding["line_no"] == finding["end_line_no"]
                else f"{finding['line_no']}-{finding['end_line_no']}"
            )
            print(
                f"- line {line_span} [overfull_hbox / {finding['amount']}]"
            )
            print(f"  text: {finding['text']}")
            print(
                "  fix:  compiled LaTeX reports a horizontal overflow; split the "
                "display into shorter aligned lines or separate displays."
            )
    else:
        print("Overflow diagnostics: 0")

    print()

    if reference_findings:
        print(f"Reference diagnostics: {len(reference_findings)}")
        for finding in reference_findings:
            print(f"- line {finding['line_no']} [{finding['kind']}]")
            print(f"  text: {finding['text']}")
            print(f"  fix:  {finding['fix']}")
    else:
        print("Reference diagnostics: 0")

    print()

    if redundancy_findings:
        print(f"Redundancy diagnostics: {len(redundancy_findings)}")
        for finding in redundancy_findings:
            if finding["kind"] == "rule":
                print(
                    f"- line {finding['line_no']} [{finding['rule_id']} / "
                    f"{finding['category']}]"
                )
                print(f"  text: {finding['text']}")
                print(f"  fix:  {finding['fix']}")
                continue
            if finding["kind"] == "heuristic_adjacent_restatement":
                print(
                    f"- line {finding['line_no']}-{finding['end_line_no']} "
                    "[heuristic_adjacent_restatement]"
                )
                print(f"  text: {finding['text']}")
                print(f"  next: {finding['next_text']}")
                print(f"  fix:  {finding['fix']}")
                continue
            print(f"- line {finding['line_no']} [{finding['kind']}]")
            print(f"  text: {finding['text']}")
            print(f"  fix:  {finding['fix']}")
    else:
        print("Redundancy diagnostics: 0")


if __name__ == "__main__":
    main()
