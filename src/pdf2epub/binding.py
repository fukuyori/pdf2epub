from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


_JP_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")


class BindingDirection(str, Enum):
    RTL = "rtl"
    LTR = "ltr"


@dataclass(frozen=True)
class BindingDecision:
    direction: BindingDirection
    reason: str


RTL_KEYWORDS = (
    "右開き",
    "右綴じ",
    "右閉じ",
    "manga",
    "comic",
    "comics",
    "コミック",
    "漫画",
    "マンガ",
    "小説",
    "文庫",
    "novel",
    "週刊",
    "月刊",
)

LTR_KEYWORDS = (
    "左開き",
    "左綴じ",
    "左閉じ",
    "left-to-right",
    "ltr",
    "english",
    "magazine us",
    "western",
)


def contains_japanese(text: str) -> bool:
    return bool(_JP_CHAR_RE.search(text))


def japanese_ratio(text: str) -> float:
    if not text:
        return 0.0
    matched = len(_JP_CHAR_RE.findall(text))
    return matched / max(len(text), 1)


def resolve_binding(
    mode: str,
    source_name: str = "",
    text_samples: list[str] | None = None,
    language_hint: str = "ja",
    pdf_creator: str = "",
    image_only: bool = False,
) -> BindingDecision:
    normalized_mode = (mode or "auto").lower()
    if normalized_mode == "rtl":
        return BindingDecision(BindingDirection.RTL, "binding was forced to rtl")
    if normalized_mode == "ltr":
        return BindingDecision(BindingDirection.LTR, "binding was forced to ltr")

    haystack = " ".join([source_name, *(text_samples or [])]).lower()

    for keyword in RTL_KEYWORDS:
        if keyword.lower() in haystack:
            return BindingDecision(
                BindingDirection.RTL,
                "filename/text heuristics suggest Japanese right-bound content",
            )

    for keyword in LTR_KEYWORDS:
        if keyword.lower() in haystack:
            return BindingDecision(
                BindingDirection.LTR,
                "filename/text heuristics suggest left-bound content",
            )

    if contains_japanese(source_name):
        return BindingDecision(
            BindingDirection.RTL,
            "Japanese characters were found in the filename",
        )

    joined_samples = "\n".join(text_samples or [])
    if japanese_ratio(joined_samples) >= 0.05:
        return BindingDecision(
            BindingDirection.RTL,
            "early pages contain enough Japanese text to prefer rtl",
        )

    if image_only and language_hint.lower().startswith("ja"):
        return BindingDecision(
            BindingDirection.RTL,
            "image-only scanned PDF with Japanese language hint defaults to rtl",
        )

    if "scansnap" in (pdf_creator or "").lower() and language_hint.lower().startswith("ja"):
        return BindingDecision(
            BindingDirection.RTL,
            "ScanSnap-style scanned PDF with Japanese language hint defaults to rtl",
        )

    return BindingDecision(
        BindingDirection.LTR,
        "no strong Japanese/right-bound signals were found",
    )
