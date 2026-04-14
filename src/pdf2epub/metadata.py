from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re


_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')
_MULTISPACE_RE = re.compile(r"\s+")
_SEPARATOR_RE = re.compile(r"[_\.]+")
_NON_WORD_RE = re.compile(r"[^\w\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]+")
_EDGE_BRACKETED_NOISE_RE = re.compile(
    r"^(?:\[[^\]]+\]|\([^)]+\)|【[^】]+】)\s*|\s*(?:\[[^\]]+\]|\([^)]+\)|【[^】]+】)$"
)
_PLACEHOLDER_STEM_RE = re.compile(
    r"^(?:\d{8,18}|scan(?:_\d+)?|document(?:_\d+)?)$",
    re.IGNORECASE,
)
_ISSUE_PATTERNS = (
    re.compile(r"(?P<issue>\d{4}年\s*\d{1,2}月号)"),
    re.compile(r"(?P<issue>\d{4}年\s*\d{1,2}月)"),
    re.compile(r"(?P<issue>\d{1,2}月号)"),
    re.compile(r"(?P<issue>\d{2}\s*/\s*\d{1,2})"),
    re.compile(r"(?P<issue>\d{4}\s*/\s*\d{1,2})"),
    re.compile(r"(?P<issue>\d{4}\s+\d{1,2})"),
    re.compile(r"(?P<issue>第\s*\d+\s*(?:巻|話|号))"),
    re.compile(r"(?P<issue>\d+\s*(?:巻|話|号))"),
    re.compile(r"(?P<issue>Vol\.?\s*\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"(?P<issue>No\.?\s*\d+)", re.IGNORECASE),
    re.compile(r"(?P<issue>#[0-9]+)"),
)
_GENERIC_COVER_WORDS = {
    "特集",
    "第2特集",
    "第1特集",
    "新展開",
    "新連載",
    "graphic",
    "science",
    "magazine",
}


@dataclass(frozen=True)
class ExtractedMetadata:
    title: str
    issue: str | None
    original_stem: str


@dataclass(frozen=True)
class MetadataDecision:
    metadata: ExtractedMetadata
    source: str
    confidence: float
    matched_title: str | None = None


def normalize_stem(name_or_path: str) -> str:
    stem = Path(name_or_path).stem
    stem = _SEPARATOR_RE.sub(" ", stem)
    stem = _MULTISPACE_RE.sub(" ", stem).strip()
    return stem


def normalize_for_match(value: str) -> str:
    return _NON_WORD_RE.sub("", value or "").casefold()


def load_title_candidates(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _strip_edge_noise(title: str) -> str:
    previous = None
    current = title.strip()
    while previous != current:
        previous = current
        current = _EDGE_BRACKETED_NOISE_RE.sub("", current).strip()
    return current


def extract_issue(text: str) -> str | None:
    normalized = _MULTISPACE_RE.sub(" ", text or "").strip()
    for pattern in _ISSUE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return _MULTISPACE_RE.sub(" ", match.group("issue")).strip()
    return None


def extract_text_metadata(text: str, fallback_stem: str = "") -> ExtractedMetadata:
    normalized = _MULTISPACE_RE.sub(" ", text or "").strip()
    issue = extract_issue(normalized)
    title = normalized

    if issue:
        issue_match = re.search(re.escape(issue), title)
        if issue_match:
            title = f"{title[:issue_match.start()]} {title[issue_match.end():]}"

    title = _strip_edge_noise(title)
    title = _MULTISPACE_RE.sub(" ", title).strip(" -_")
    if not title:
        title = fallback_stem

    return ExtractedMetadata(title=title or fallback_stem, issue=issue, original_stem=fallback_stem)


def is_placeholder_title(title: str) -> bool:
    compact = normalize_for_match(title)
    return not compact or bool(_PLACEHOLDER_STEM_RE.fullmatch(compact))


def extract_cover_metadata(cover_text: str, fallback_stem: str = "") -> ExtractedMetadata:
    normalized_lines = [
        _MULTISPACE_RE.sub(" ", line).strip()
        for line in cover_text.splitlines()
        if line.strip()
    ]
    issue = extract_issue("\n".join(normalized_lines))

    scored_candidates: list[tuple[int, str]] = []
    for index, line in enumerate(normalized_lines[:15]):
        cleaned = line.strip(" -_./|")
        lowered = cleaned.lower()
        compact = normalize_for_match(cleaned)
        if not compact or lowered in _GENERIC_COVER_WORDS:
            continue
        if issue and cleaned == issue:
            continue
        if len(cleaned) > 24 or len(compact) < 2:
            continue

        score = 100 - index * 5
        if " " not in cleaned:
            score += 10
        if len(cleaned) <= 10:
            score += 10
        if re.search(r"[A-Za-z]{4,}", cleaned):
            score += 8
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", cleaned):
            score += 8
        scored_candidates.append((score, cleaned))

    title = max(scored_candidates, key=lambda item: item[0])[1] if scored_candidates else fallback_stem
    return ExtractedMetadata(title=title or fallback_stem, issue=issue, original_stem=fallback_stem)


def _match_candidate_against_text(candidate: str, text: str) -> float:
    normalized_candidate = normalize_for_match(candidate)
    normalized_text = normalize_for_match(text)
    if not normalized_candidate or not normalized_text:
        return 0.0
    if normalized_candidate in normalized_text:
        return 1.0
    if normalized_text in normalized_candidate:
        return 0.9
    return SequenceMatcher(None, normalized_candidate, normalized_text).ratio()


def match_title_candidate(
    sources: list[str],
    candidates: list[str],
    minimum_score: float = 0.62,
) -> tuple[str | None, float]:
    best_title = None
    best_score = 0.0

    lines: list[str] = []
    for source in sources:
        if not source:
            continue
        lines.append(source)
        lines.extend(line.strip() for line in source.splitlines() if line.strip())

    for candidate in candidates:
        for line in lines:
            score = _match_candidate_against_text(candidate, line)
            if score > best_score:
                best_title = candidate
                best_score = score

    if best_score < minimum_score:
        return None, best_score
    return best_title, best_score


def infer_metadata(
    name_or_path: str,
    pdf_title: str = "",
    cover_text: str = "",
    title_candidates: list[str] | None = None,
) -> MetadataDecision:
    original_stem = normalize_stem(name_or_path)
    pdf_metadata = (
        extract_text_metadata(pdf_title.strip(), fallback_stem=original_stem)
        if pdf_title.strip()
        else None
    )
    cover_metadata = (
        extract_cover_metadata(cover_text, fallback_stem=original_stem)
        if cover_text.strip()
        else None
    )

    matched_title, score = match_title_candidate(
        [
            pdf_title,
            cover_text,
            pdf_metadata.title if pdf_metadata else "",
            cover_metadata.title if cover_metadata else "",
        ],
        title_candidates or [],
    )

    issue = (
        (pdf_metadata.issue if pdf_metadata else None)
        or (cover_metadata.issue if cover_metadata else None)
    )

    if matched_title:
        return MetadataDecision(
            metadata=ExtractedMetadata(
                title=matched_title,
                issue=issue,
                original_stem=original_stem,
            ),
            source="title-candidates",
            confidence=score,
            matched_title=matched_title,
        )

    if pdf_metadata and not is_placeholder_title(pdf_metadata.title):
        return MetadataDecision(pdf_metadata, "pdf-metadata", 0.85)

    if cover_metadata and not is_placeholder_title(cover_metadata.title):
        return MetadataDecision(cover_metadata, "cover-ocr", 0.75)

    return MetadataDecision(
        metadata=ExtractedMetadata(
            title=original_stem,
            issue=issue,
            original_stem=original_stem,
        ),
        source="input-stem-fallback",
        confidence=0.2,
    )


def sanitize_filename(value: str) -> str:
    sanitized = _ILLEGAL_FILENAME_CHARS.sub(" ", value)
    sanitized = _MULTISPACE_RE.sub(" ", sanitized).strip().strip(".")
    return sanitized or "output"


def build_output_stem(title: str, issue: str | None = None) -> str:
    joined = f"{title}_{issue}".strip() if issue else title.strip()
    return sanitize_filename(joined)
