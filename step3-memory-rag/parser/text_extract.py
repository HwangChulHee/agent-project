from __future__ import annotations
import re
from lxml import etree as ET

TEXT_TAGS = {"P", "SPAN", "TITLE"}

# 한국어 종결어미 마침표 + 다음 글자가 한글/영문이면 공백 삽입.
# 숫자 소수점(3.7%)이나 약어(U.S.A.)는 건드리지 않음 — 한국어 종결자음만 한정.
_KO_SENTENCE_END = re.compile(r"([다요까임음됨함]\.)(?=[가-힣A-Za-z])")


def _normalize_sentence_spacing(text: str) -> str:
    if not text:
        return text
    return _KO_SENTENCE_END.sub(r"\1 ", text)


def _elem_text(elem: ET._Element) -> str:
    """Extract all text content from an element (including tail of children)."""
    raw = (ET.tostring(elem, method="text", encoding="unicode") or "").strip()
    return _normalize_sentence_spacing(raw)


def extract_text(elements: list[ET._Element]) -> str:
    paragraphs: list[str] = []
    for elem in elements:
        tag = elem.tag
        if not isinstance(tag, str) or tag not in TEXT_TAGS:
            continue
        text = _elem_text(elem)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)
