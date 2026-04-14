from __future__ import annotations

from dataclasses import dataclass
import re


TOC_KEYWORDS = ("目次", "もくじ", "contents")
_MULTISPACE_RE = re.compile(r"\s+")
_FULLWIDTH_DIGIT_TABLE = str.maketrans("０１２３４５６７８９", "0123456789")
_LEADER_RE = re.compile(r"[\.・･·…‥ー\-]{2,}")


@dataclass(frozen=True)
class TocEntry:
    title: str
    printed_page: int | None = None


def normalize_toc_text(text: str) -> str:
    normalized = (text or "").translate(_FULLWIDTH_DIGIT_TABLE)
    return "\n".join(_MULTISPACE_RE.sub(" ", line).strip() for line in normalized.splitlines())


def parse_toc_entries(text: str, max_entries: int = 40) -> list[TocEntry]:
    entries: list[TocEntry] = []
    seen_titles: set[str] = set()
    normalized = normalize_toc_text(text)

    for raw_line in normalized.splitlines():
        line = _LEADER_RE.sub(" ", raw_line).strip(" |")
        if not line:
            continue
        lowered = line.lower()
        if lowered in TOC_KEYWORDS:
            continue

        match = re.match(r"^(?P<title>.+?)\s+(?P<page>\d{1,4})$", line)
        if not match:
            match = re.match(r"^(?P<page>\d{1,4})\s+(?P<title>.+)$", line)
        if not match:
            continue

        title = match.group("title").strip(" -_:：")
        if len(title) < 2:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)
        entries.append(TocEntry(title=title, printed_page=int(match.group("page"))))
        if len(entries) >= max_entries:
            break

    return entries


def detect_toc_page(page_texts: list[str]) -> tuple[int | None, str]:
    best_index = None
    best_text = ""
    best_score = -1

    for index, text in enumerate(page_texts):
        normalized = normalize_toc_text(text)
        if not normalized:
            continue

        lowered = normalized.lower()
        entry_count = len(parse_toc_entries(normalized))
        score = 0
        if any(keyword in lowered for keyword in TOC_KEYWORDS):
            score += 4
        score += min(entry_count, 6)
        if score <= 0 or (score < 4 and entry_count < 3):
            continue

        if score > best_score:
            best_index = index
            best_text = normalized
            best_score = score

    if best_score <= 0:
        return None, ""
    return best_index, best_text
