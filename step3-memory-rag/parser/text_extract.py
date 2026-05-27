from __future__ import annotations
from lxml import etree as ET

TEXT_TAGS = {"P", "SPAN", "TITLE"}


def _elem_text(elem: ET._Element) -> str:
    """Extract all text content from an element (including tail of children)."""
    return (ET.tostring(elem, method="text", encoding="unicode") or "").strip()


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
