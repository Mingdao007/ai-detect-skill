#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = ROOT / "data" / "rules.json"
DEFAULT_QUEUE_PATH = ROOT / "data" / "review_queue.jsonl"
NODE_EXTRACTOR = ROOT / "scripts" / "extract_visible_strings.mjs"
ALLOWED_SURFACES = {"tex", "md", "js", "ts"}
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
URL_RE = re.compile(r"https?://\S+")
INLINE_DOLLAR_MATH_RE = re.compile(r"\$[^$]*\$")
INLINE_PAREN_MATH_RE = re.compile(r"\\\([^)]*\\\)")
OPTION_BLOCK_RE = re.compile(r"\[[^\]]*\]")
COMMAND_NAME_RE = re.compile(r"\\[A-Za-z@]+(?:\*)?")
COMMAND_SYMBOL_RE = re.compile(r"\\.")
PAREN_LABEL_RE = re.compile(r"\([A-Za-z0-9_.:-]+\)")
VISIBLE_TEXT_CLEAN_RE = re.compile(r"[^A-Za-z0-9\u4e00-\u9fff\s,.;:!?'\-，。？！；：、（）]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。？！；;])\s+")
ENGLISH_CONNECTOR_RE = re.compile(
    r"(?P<lhs>.+?)(?:,\s*not\s+(?P<rhs_not>.+)|\brather than\b\s+(?P<rhs_rather>.+)|\binstead of\b\s+(?P<rhs_instead>.+))$",
    re.IGNORECASE,
)
CHINESE_CONNECTOR_RE = re.compile(
    r"(?P<lhs>.+?)(?:而不是|不是)(?P<rhs>.+)$"
)
ENGLISH_SEQUENCER_RE = re.compile(r"^(?:First|Then|Finally)\s*(?:--|:|-)\s+", re.IGNORECASE)
CHINESE_SEQUENCER_RE = re.compile(r"^(?:首先|然后|最后)\s*(?:：|:|-|——)\s*")
CHINESE_AXIS_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9]{1,18}(?:方面|层面)?(?:不同|区别在于)")
ENGLISH_AXIS_RE = re.compile(r"^[A-Za-z][A-Za-z /&-]{0,32}\b(?:respectively|in contrast)\b", re.IGNORECASE)
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
GENERIC_REDUNDANCY_HEADS_EN = {
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
GENERIC_REDUNDANCY_MODIFIERS_EN = {
    "unrelated",
    "different",
    "various",
    "general",
    "overall",
    "simple",
    "separate",
}
GENERIC_REDUNDANCY_HEADS_ZH = {
    "列表",
    "论文",
    "过程",
    "流程",
    "步骤",
    "部分",
    "内容",
    "结构",
    "方式",
    "选择",
    "东西",
    "方向",
}
GENERIC_REDUNDANCY_MODIFIERS_ZH = {
    "不同",
    "一般",
    "整体",
    "简单",
    "单独",
    "无关",
    "若干",
    "一些",
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


def infer_surface(path: Path | None, requested: str) -> str:
    if requested != "auto":
        return requested
    if path is None:
        return "md"
    suffix = path.suffix.lower()
    if suffix == ".tex":
        return "tex"
    if suffix == ".md":
        return "md"
    if suffix == ".ts":
        return "ts"
    return "js"


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


def extract_visible_tex(raw_line: str) -> str:
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
    return re.sub(r"\s+", " ", text).strip()


def tex_body_lines(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    in_document = False
    body = []
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


def visible_tex_lines(text: str) -> list[dict]:
    lines: list[dict] = []
    for line_no, raw_line in tex_body_lines(text):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(PROSE_SKIP_PREFIXES):
            continue
        visible = extract_visible_tex(raw_line)
        if visible:
            lines.append({"line_no": line_no, "text": visible, "surface": "tex"})
    return lines


def visible_md_lines(text: str) -> list[dict]:
    lines: list[dict] = []
    in_code = False
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            continue
        if stripped.startswith("    "):
            continue
        visible = URL_RE.sub(" ", raw_line)
        visible = re.sub(r"`[^`]*`", " ", visible)
        visible = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", visible)
        visible = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", visible)
        visible = visible.lstrip("#>*-+ \t")
        visible = VISIBLE_TEXT_CLEAN_RE.sub(" ", visible)
        visible = re.sub(r"\s+", " ", visible).strip()
        if visible:
            lines.append({"line_no": line_no, "text": visible, "surface": "md"})
    return lines


def visible_js_ts_lines(path: Path, surface: str) -> list[dict]:
    proc = subprocess.run(
        ["node", str(NODE_EXTRACTOR), str(path), surface],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "Node AST extraction failed.")
    payload = json.loads(proc.stdout)
    lines = []
    for unit in payload.get("units", []):
        text = re.sub(r"\s+", " ", str(unit.get("text", ""))).strip()
        if not text:
            continue
        lines.append(
            {
                "line_no": int(unit.get("line_no", 1)),
                "text": text,
                "surface": surface,
                "context": unit.get("context", ""),
            }
        )
    return lines


def load_text(path: Path | None, inline_text: str | None) -> tuple[str, Path | None]:
    if inline_text is not None:
        return inline_text, path
    if path is not None:
        return path.read_text(encoding="utf-8", errors="ignore"), path
    return sys.stdin.read(), None


def split_sentences(text: str) -> list[str]:
    segments = [segment.strip() for segment in SENTENCE_SPLIT_RE.split(text) if segment.strip()]
    return segments or [text.strip()]


def normalize_token(token: str) -> str:
    return token.lower().strip("'")


def content_tokens_en(text: str) -> list[str]:
    tokens = [normalize_token(token) for token in WORD_RE.findall(text)]
    return [token for token in tokens if token not in STOPWORDS and len(token) >= 3]


def content_tokens_zh(text: str) -> list[str]:
    chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    grams: list[str] = []
    for chunk in chunks:
        if len(chunk) == 2:
            grams.append(chunk)
            continue
        grams.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return grams


def detect_language(text: str) -> str:
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if cjk_count >= 4 and cjk_count >= latin_count:
        return "zh"
    if latin_count >= 6:
        return "en"
    if cjk_count:
        return "zh"
    return "en"


def prose_units(lines: list[dict]) -> list[dict]:
    units: list[dict] = []
    for line in lines:
        for segment in split_sentences(line["text"]):
            language = detect_language(segment)
            tokens = content_tokens_zh(segment) if language == "zh" else content_tokens_en(segment)
            if len(tokens) < 3:
                continue
            units.append(
                {
                    "line_no": line["line_no"],
                    "surface": line["surface"],
                    "text": segment,
                    "language": language,
                    "tokens": tokens,
                }
            )
    return units


def scan_confirmed(lines: list[dict], rules: list[dict]) -> list[dict]:
    findings: list[dict] = []
    seen = set()
    for line in lines:
        for rule in rules:
            if rule.get("status") != "confirmed":
                continue
            for pattern in compile_patterns(rule):
                if pattern.search(line["text"]):
                    key = (line["line_no"], rule["rule_id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        {
                            "kind": "rule",
                            "line_no": line["line_no"],
                            "surface": line["surface"],
                            "language": detect_language(line["text"]),
                            "text": line["text"],
                            "confidence": "high",
                            "fix": rule["rewrite_direction"],
                            "rule_id": rule["rule_id"],
                            "category": rule["category"],
                        }
                    )
                    break
    return findings


def scan_pending(lines: list[dict], queue_entries: list[dict], rules: list[dict]) -> list[dict]:
    findings: list[dict] = []
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
        for line in lines:
            if phrase_pattern.search(line["text"]):
                key = (line["line_no"], entry["candidate_id"])
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "line_no": line["line_no"],
                        "surface": line["surface"],
                        "text": line["text"],
                        "candidate_id": entry["candidate_id"],
                        "category_guess": entry["category_guess"],
                        "phrase": entry["phrase"],
                        "source": "redundancy",
                    }
                )
    return findings


def scan_empty_contrast(units: list[dict], excluded_lines: set[int]) -> list[dict]:
    findings: list[dict] = []
    for unit in units:
        if unit["line_no"] in excluded_lines:
            continue
        if unit["language"] == "en":
            lowered = unit["text"].lower()
            if "not only" in lowered and "but also" in lowered:
                continue
            match = ENGLISH_CONNECTOR_RE.search(unit["text"])
            if not match:
                continue
            lhs = (match.group("lhs") or "").strip(" ,.;:")
            rhs = (
                match.group("rhs_not")
                or match.group("rhs_rather")
                or match.group("rhs_instead")
                or ""
            ).strip(" ,.;:")
            lhs_tokens = set(content_tokens_en(lhs))
            rhs_tokens = content_tokens_en(rhs)
            rhs_new = {token for token in rhs_tokens if token not in lhs_tokens}
            if not rhs_tokens or len(rhs_tokens) > 6:
                continue
            if not any(token in GENERIC_REDUNDANCY_HEADS_EN for token in rhs_tokens):
                continue
            if rhs_new and not all(
                token in GENERIC_REDUNDANCY_HEADS_EN or token in GENERIC_REDUNDANCY_MODIFIERS_EN
                for token in rhs_new
            ):
                continue
            findings.append(
                {
                    "kind": "heuristic_empty_contrast",
                    "line_no": unit["line_no"],
                    "surface": unit["surface"],
                    "language": unit["language"],
                    "text": unit["text"],
                    "confidence": "high",
                    "fix": "the contrast clause adds mostly generic wording with little new information; delete it or replace it with the real distinction.",
                }
            )
            continue
        match = CHINESE_CONNECTOR_RE.search(unit["text"])
        if not match:
            continue
        rhs = (match.group("rhs") or "").strip(" ，。；;:：")
        rhs_tokens = content_tokens_zh(rhs)
        if not rhs_tokens or len(rhs_tokens) > 5:
            continue
        if not all(
            token in GENERIC_REDUNDANCY_HEADS_ZH or token in GENERIC_REDUNDANCY_MODIFIERS_ZH
            for token in rhs_tokens
        ):
            continue
        findings.append(
            {
                "kind": "heuristic_empty_contrast",
                "line_no": unit["line_no"],
                "surface": unit["surface"],
                "language": unit["language"],
                "text": unit["text"],
                "confidence": "medium",
                "fix": "对比后半句新增的多是泛化名词或泛化修饰，应删掉空转对比，直接写真正的区分点。",
            }
        )
    return findings


def overlap_ratio(previous_tokens: set[str], current_tokens: set[str]) -> float:
    return len(previous_tokens & current_tokens) / min(len(previous_tokens), len(current_tokens))


def scan_adjacent_restatement(units: list[dict], excluded_lines: set[int]) -> list[dict]:
    findings: list[dict] = []
    for previous, current in zip(units, units[1:]):
        if previous["line_no"] in excluded_lines or current["line_no"] in excluded_lines:
            continue
        if previous["surface"] != current["surface"] or previous["language"] != current["language"]:
            continue
        previous_tokens = set(previous["tokens"])
        current_tokens = set(current["tokens"])
        if len(previous_tokens) < 4 or len(current_tokens) < 4:
            continue
        overlap = overlap_ratio(previous_tokens, current_tokens)
        new_tokens = current_tokens - previous_tokens
        if previous["language"] == "en":
            if overlap < 0.82 or len(new_tokens) > 1:
                continue
        else:
            if overlap < 0.72 or len(new_tokens) > 2:
                continue
        findings.append(
            {
                "kind": "heuristic_adjacent_restatement",
                "line_no": previous["line_no"],
                "end_line_no": current["line_no"],
                "surface": previous["surface"],
                "language": previous["language"],
                "text": previous["text"],
                "next_text": current["text"],
                "confidence": "high" if previous["language"] == "en" else "medium",
                "fix": "the later sentence mostly restates the earlier one with little new information; merge them or delete the weaker sentence.",
            }
        )
    return findings


def scan_sequencer_labels(units: list[dict], excluded_lines: set[int]) -> list[dict]:
    findings: list[dict] = []
    for unit in units:
        if unit["line_no"] in excluded_lines:
            continue
        if ENGLISH_SEQUENCER_RE.search(unit["text"]) or CHINESE_SEQUENCER_RE.search(unit["text"]):
            findings.append(
                {
                    "kind": "heuristic_sequencer_label",
                    "line_no": unit["line_no"],
                    "surface": unit["surface"],
                    "language": unit["language"],
                    "text": unit["text"],
                    "confidence": "high" if unit["language"] == "en" else "medium",
                    "fix": "replace the sequence scaffold with the actual content label or question.",
                }
            )
    return findings


def scan_axis_repetition(units: list[dict], excluded_lines: set[int]) -> list[dict]:
    findings: list[dict] = []
    run: list[dict] = []
    for unit in units + [{"line_no": -1, "text": "", "surface": None, "language": None}]:
        is_axis = (
            unit["line_no"] not in excluded_lines
            and (
                CHINESE_AXIS_RE.search(unit["text"])
                or ENGLISH_AXIS_RE.search(unit["text"])
            )
        )
        if is_axis:
            run.append(unit)
            continue
        if len(run) >= 3:
            for item in run:
                findings.append(
                    {
                        "kind": "heuristic_axis_repetition",
                        "line_no": item["line_no"],
                        "surface": item["surface"],
                        "language": item["language"],
                        "text": item["text"],
                        "confidence": "medium",
                        "fix": "front-load the comparison axis once and name the actual difference directly instead of repeating the same low-information axis label on each item.",
                    }
                )
        run = []
    return findings


def dedupe(findings: list[dict]) -> list[dict]:
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


def build_visible_lines(path: Path | None, text: str, surface: str) -> list[dict]:
    if surface == "tex":
        return visible_tex_lines(text)
    if surface == "md":
        return visible_md_lines(text)
    if path is not None:
        return visible_js_ts_lines(path, surface)
    with tempfile.NamedTemporaryFile("w", suffix=f".{surface}", encoding="utf-8", delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        return visible_js_ts_lines(temp_path, surface)
    finally:
        temp_path.unlink(missing_ok=True)


def build_result(path: Path | None, text: str, surface: str, rules_path: Path, queue_path: Path) -> dict:
    rules = load_rules(rules_path)
    queue_entries = load_queue(queue_path)
    visible_lines = build_visible_lines(path, text, surface)
    confirmed = scan_confirmed(visible_lines, rules)
    pending = scan_pending(visible_lines, queue_entries, rules)
    excluded_lines = {finding["line_no"] for finding in confirmed}
    units = prose_units(visible_lines)
    heuristics = dedupe(
        scan_empty_contrast(units, excluded_lines)
        + scan_adjacent_restatement(units, excluded_lines)
        + scan_sequencer_labels(units, excluded_lines)
        + scan_axis_repetition(units, excluded_lines)
    )
    confirmed.extend(heuristics)
    return {
        "path": str(path) if path is not None else "<stdin>",
        "surface": surface,
        "confirmed_findings": confirmed,
        "needs_user_confirmation": pending,
    }


def print_result(result: dict) -> None:
    print(f"Redundancy scan for {result['path']}")
    print()
    confirmed = result["confirmed_findings"]
    pending = result["needs_user_confirmation"]
    if confirmed:
        print(f"Confirmed findings: {len(confirmed)}")
        for finding in confirmed:
            span = (
                f"{finding['line_no']}"
                if finding.get("end_line_no") in {None, finding["line_no"]}
                else f"{finding['line_no']}-{finding['end_line_no']}"
            )
            label = finding.get("rule_id") or finding["kind"]
            print(f"- line {span} [{label}]")
            print(f"  text: {finding['text']}")
            if finding.get("next_text"):
                print(f"  next: {finding['next_text']}")
            print(f"  fix:  {finding['fix']}")
    else:
        print("Confirmed findings: 0")
    print()
    if pending:
        print(f"Needs user confirmation: {len(pending)}")
        for finding in pending:
            print(f"- line {finding['line_no']} [{finding['candidate_id']} / {finding['category_guess']}]")
            print(f"  text: {finding['text']}")
            print(f"  phrase: {finding['phrase']}")
            print(f"  source: {finding['source']}")
    else:
        print("Needs user confirmation: 0")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan bilingual formal deliverables for low-information repetition."
    )
    parser.add_argument("file", nargs="?")
    parser.add_argument("--text")
    parser.add_argument("--surface", choices=["auto", *sorted(ALLOWED_SURFACES)], default="auto")
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    path = Path(args.file).expanduser().resolve() if args.file else None
    text, path = load_text(path, args.text)
    surface = infer_surface(path, args.surface)
    result = build_result(path, text, surface, Path(args.rules), Path(args.queue))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print_result(result)


if __name__ == "__main__":
    main()
