from __future__ import annotations
import re

from .models import Chunk, SectionNode
from .text_extract import extract_text, _elem_text
from .table_to_md import extract_table_as_text, table_to_markdown

TABLE_TAGS = {"TABLE", "TABLE-GROUP"}
TEXT_TAGS = {"P", "SPAN", "TITLE"}

# 한국어 종결어미 + 마침표 — 분할 우선순위 2
_SENTENCE_END_RE = re.compile(r"(?<=[다요까임음됨함니]\.)\s*")


def _expand_tables(elem):
    """TABLE-GROUP을 투명 컨테이너로 풀어 실제 TABLE 들을 yield (재귀)."""
    tag = elem.tag
    if not isinstance(tag, str):
        return
    if tag == "TABLE":
        yield elem
    elif tag == "TABLE-GROUP":
        for child in elem:
            yield from _expand_tables(child)


def _last_sentences(text: str, n: int = 2, max_chars: int = 200) -> str:
    """텍스트의 마지막 1~2 문장을 한국어 종결어미 기준으로 추출."""
    text = text.strip()
    if not text:
        return ""
    parts = [s.strip() for s in _SENTENCE_END_RE.split(text) if s.strip()]
    if parts:
        tail = " ".join(parts[-n:])
    else:
        tail = text
    if len(tail) > max_chars:
        tail = tail[-max_chars:]
    return tail


def _split_table_md(md: str, max_chars: int) -> list[str]:
    if len(md) <= max_chars:
        return [md]

    lines = md.split("\n")
    header_lines: list[str] = []
    data_lines: list[str] = []
    past_separator = False
    for line in lines:
        if not past_separator:
            header_lines.append(line)
            if line.startswith("|") and set(line.replace("|", "").replace(" ", "")) <= {"-"}:
                past_separator = True
        else:
            data_lines.append(line)

    if not data_lines:
        return [md]

    header_block = "\n".join(header_lines)
    header_len = len(header_block) + 1

    parts: list[str] = []
    current: list[str] = []
    current_len = header_len

    for row in data_lines:
        row_len = len(row) + 1
        if current and current_len + row_len > max_chars:
            parts.append(header_block + "\n" + "\n".join(current))
            current = [row]
            current_len = header_len + len(row) + 1
        else:
            current.append(row)
            current_len += row_len

    if current:
        parts.append(header_block + "\n" + "\n".join(current))

    return parts


def _split_by_separator(text: str, sep: str, max_chars: int) -> list[str]:
    parts = text.split(sep)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    sep_len = len(sep)

    for part in parts:
        part_len = len(part)
        added_len = part_len + (sep_len if current else 0)
        if current and current_len + added_len > max_chars:
            chunks.append(sep.join(current))
            current = [part]
            current_len = part_len
        else:
            current.append(part)
            current_len += added_len

    if current:
        chunks.append(sep.join(current))
    return chunks


def _split_by_sentence(text: str, max_chars: int) -> list[str]:
    """한국어 종결어미 기준 분할 (다./요./니다.)"""
    if len(text) <= max_chars:
        return [text]
    sentences = _SENTENCE_END_RE.split(text)
    sentences = [s for s in sentences if s]
    if len(sentences) <= 1:
        return [text]

    out: list[str] = []
    current = ""
    for s in sentences:
        if current and len(current) + len(s) > max_chars:
            out.append(current)
            current = s
        else:
            current = current + s if current else s
    if current:
        out.append(current)
    return out


def _hard_split(text: str, max_chars: int) -> list[str]:
    """공백 → 문자 단위 최후 fallback."""
    if len(text) <= max_chars:
        return [text]
    out: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        out.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    if remaining:
        out.append(remaining)
    return out


def _split_text(text: str, max_chars: int) -> list[str]:
    """우선순위: \\n\\n → \\n → 종결어미 → 공백/문자."""
    if len(text) <= max_chars:
        return [text]

    result = _split_by_separator(text, "\n\n", max_chars)

    expanded: list[str] = []
    for chunk in result:
        if len(chunk) <= max_chars:
            expanded.append(chunk)
        else:
            expanded.extend(_split_by_separator(chunk, "\n", max_chars))

    final: list[str] = []
    for chunk in expanded:
        if len(chunk) <= max_chars:
            final.append(chunk)
            continue
        sub = _split_by_sentence(chunk, max_chars)
        for s in sub:
            if len(s) <= max_chars:
                final.append(s)
            else:
                final.extend(_hard_split(s, max_chars))
    return final


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """인접 chunk 사이 overlap 글자 prepend."""
    if overlap <= 0 or len(chunks) < 2:
        return chunks
    out = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1][-overlap:].lstrip()
        out.append(tail + "\n" + chunks[i] if tail else chunks[i])
    return out


def _iter_leaves(node: SectionNode, path_parts: list[str]):
    current_path = path_parts + [node.title] if node.title else path_parts
    if node.children:
        for child in node.children:
            yield from _iter_leaves(child, current_path)
        if node.body_elements:
            yield current_path, node
    else:
        yield current_path, node


def _make_table_prefix(section_path: str, last_context: str) -> str:
    """표 chunk 의 컨텍스트 prefix 구성."""
    lines = [f"[{section_path}]"] if section_path else []
    if last_context:
        lines.append(last_context)
    if lines:
        return "\n".join(lines) + "\n---\n"
    return ""


def build_chunks(
    sections: list[SectionNode],
    base_metadata: dict,
    max_chunk_chars: int = 1500,
    target_chunk_chars: int = 800,
    overlap_chars: int = 100,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    target = min(target_chunk_chars, max_chunk_chars)

    for section in sections:
        for path_parts, leaf in _iter_leaves(section, []):
            section_path = " > ".join(path_parts)
            level = leaf.level

            text_buffer: list[str] = []
            last_context: str = ""
            has_any_text = False
            has_any_table = False

            def flush_text():
                nonlocal text_buffer, last_context, has_any_text
                if not text_buffer:
                    return
                body_text = "\n\n".join(t for t in text_buffer if t)
                if not body_text.strip():
                    text_buffer = []
                    return
                has_any_text = True
                parts = _split_text(body_text, target)
                parts = _add_overlap(parts, overlap_chars)
                for part in parts:
                    if len(part) > max_chunk_chars:
                        for sub in _hard_split(part, max_chunk_chars):
                            chunks.append(Chunk(
                                text=sub,
                                metadata={
                                    **base_metadata,
                                    "section_path": section_path,
                                    "section_level": level,
                                    "has_table": False,
                                    "aclass": None,
                                },
                            ))
                    else:
                        chunks.append(Chunk(
                            text=part,
                            metadata={
                                **base_metadata,
                                "section_path": section_path,
                                "section_level": level,
                                "has_table": False,
                                "aclass": None,
                            },
                        ))
                last_context = _last_sentences(body_text)
                text_buffer = []

            for elem in leaf.body_elements:
                tag = elem.tag
                if not isinstance(tag, str):
                    continue
                if tag in TABLE_TAGS:
                    # 표 직전 텍스트 flush
                    flush_text()
                    # TABLE-GROUP 투명 통과 + 각 TABLE 별 chunk
                    for table in _expand_tables(elem):
                        text_content = extract_table_as_text(table)
                        if text_content:
                            # 1/2열 긴-텍스트 컨테이너 → 텍스트 chunk
                            has_any_text = True
                            tc_parts = _split_text(text_content, target)
                            tc_parts = _add_overlap(tc_parts, overlap_chars)
                            for part in tc_parts:
                                if len(part) > max_chunk_chars:
                                    for sub in _hard_split(part, max_chunk_chars):
                                        chunks.append(Chunk(
                                            text=sub,
                                            metadata={
                                                **base_metadata,
                                                "section_path": section_path,
                                                "section_level": level,
                                                "has_table": False,
                                                "aclass": None,
                                            },
                                        ))
                                else:
                                    chunks.append(Chunk(
                                        text=part,
                                        metadata={
                                            **base_metadata,
                                            "section_path": section_path,
                                            "section_level": level,
                                            "has_table": False,
                                            "aclass": None,
                                        },
                                    ))
                            last_context = _last_sentences(text_content)
                            continue

                        md_raw = table_to_markdown(table)
                        if not md_raw.strip():
                            continue
                        aclass = table.get("ACLASS") or None
                        truncated = False
                        # [2] wide sparse 감지 + truncate
                        first_line = md_raw.split("\n", 1)[0]
                        n_cols = max(first_line.count("|") - 1, 0)
                        if n_cols > 20 or len(md_raw) > 6000:
                            kept = md_raw[:2000]
                            md_raw = (
                                kept
                                + f"\n...(wide sparse 표 일부 생략: 전체 {n_cols}열, "
                                f"{len(md_raw):,}자)"
                            )
                            truncated = True

                        prefix = _make_table_prefix(section_path, last_context)
                        # max_chunk_chars 에서 prefix 길이 제외하고 split
                        budget = max(max_chunk_chars - len(prefix), 200)
                        has_any_table = True
                        for md_part in _split_table_md(md_raw, budget):
                            chunks.append(Chunk(
                                text=prefix + md_part,
                                metadata={
                                    **base_metadata,
                                    "section_path": section_path,
                                    "section_level": level,
                                    "has_table": True,
                                    "aclass": aclass,
                                    "truncated": truncated,
                                },
                            ))
                elif tag in TEXT_TAGS:
                    t = _elem_text(elem)
                    if t:
                        text_buffer.append(t)

            flush_text()

            if not has_any_text and not has_any_table:
                chunks.append(Chunk(
                    text=section_path,
                    metadata={
                        **base_metadata,
                        "section_path": section_path,
                        "section_level": level,
                        "has_table": False,
                        "aclass": None,
                    },
                ))

    return chunks
