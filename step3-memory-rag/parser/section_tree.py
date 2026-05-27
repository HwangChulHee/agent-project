from __future__ import annotations
from lxml import etree as ET

from .models import SectionNode

SECTION_TAGS = {"SECTION-1", "SECTION-2", "SECTION-3"}
SKIP_TAGS = {"PGBRK", "A", "IMAGE", "IMG", "IMG-CAPTION", "COLGROUP", "COL"}
BODY_TAGS = {"P", "SPAN", "TITLE", "TABLE", "TABLE-GROUP"}


def _section_level(tag: str) -> int:
    return int(tag[-1])


def _collect_body_elements(parent: ET._Element) -> list[ET._Element]:
    """Collect body-level elements (P, TABLE, etc.) from a container,
    traversing through LIBRARY transparently."""
    elements = []
    for child in parent:
        tag = child.tag
        if isinstance(tag, str) and tag in SECTION_TAGS:
            continue
        if isinstance(tag, str) and tag == "LIBRARY":
            elements.extend(_collect_body_elements(child))
        elif isinstance(tag, str) and tag == "TITLE":
            continue
        elif isinstance(tag, str) and tag in SKIP_TAGS:
            continue
        else:
            elements.append(child)
    return elements


def _find_child_sections(parent: ET._Element, target_tag: str) -> list[ET._Element]:
    """Find child section elements, looking through LIBRARY wrappers."""
    results = []
    for child in parent:
        tag = child.tag
        if isinstance(tag, str) and tag == target_tag:
            results.append(child)
        elif isinstance(tag, str) and tag == "LIBRARY":
            results.extend(_find_child_sections(child, target_tag))
    return results


def _build_node(elem: ET._Element, level: int) -> SectionNode:
    title_el = elem.find("TITLE")
    title = (title_el.text or "").strip() if title_el is not None else ""
    atocid = elem.get("ATOCID") or None

    child_tag = f"SECTION-{level + 1}" if level < 3 else None
    children = []
    if child_tag:
        child_elems = _find_child_sections(elem, child_tag)
        children = [_build_node(c, level + 1) for c in child_elems]

    body = _collect_body_elements(elem) if not children else []

    # 자식 섹션이 있어도, 섹션 사이에 직접 놓인 body 요소가 있을 수 있음
    if children:
        for child in elem:
            tag = child.tag
            if isinstance(tag, str) and tag not in SECTION_TAGS and tag != "LIBRARY" and tag != "TITLE" and tag not in SKIP_TAGS:
                body.append(child)

    return SectionNode(
        title=title,
        atocid=atocid,
        level=level,
        children=children,
        body_elements=body,
    )


def parse_section_tree(root: ET._Element) -> list[SectionNode]:
    sections = []
    for s1 in root.iter("SECTION-1"):
        sections.append(_build_node(s1, level=1))
    return sections
