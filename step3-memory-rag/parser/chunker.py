from __future__ import annotations

from .models import Chunk, SectionNode
from .text_extract import extract_text
from .table_to_md import extract_table_as_text, table_to_markdown

TABLE_TAGS = {"TABLE", "TABLE-GROUP"}


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
    header_len = len(header_block) + 1  # +1 for newline before data

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


def _split_by_paragraphs(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    result = _split_by_separator(text, "\n\n", max_chars)

    final: list[str] = []
    for chunk in result:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            final.extend(_split_by_separator(chunk, "\n", max_chars))

    return final


def _iter_leaves(node: SectionNode, path_parts: list[str]):
    current_path = path_parts + [node.title] if node.title else path_parts
    if node.children:
        for child in node.children:
            yield from _iter_leaves(child, current_path)
        if node.body_elements:
            yield current_path, node
    else:
        yield current_path, node


def build_chunks(
    sections: list[SectionNode],
    base_metadata: dict,
    max_chunk_chars: int = 1500,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    for section in sections:
        for path_parts, leaf in _iter_leaves(section, []):
            section_path = " > ".join(path_parts)
            level = leaf.level

            text_elems = []
            table_elems = []
            for elem in leaf.body_elements:
                tag = elem.tag
                if isinstance(tag, str) and tag in TABLE_TAGS:
                    table_elems.append(elem)
                else:
                    text_elems.append(elem)

            body_text = extract_text(text_elems)
            has_text = bool(body_text.strip())
            if has_text:
                for part in _split_by_paragraphs(body_text, max_chunk_chars):
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

            has_tables = False
            for tbl in table_elems:
                actual_tables = []
                if tbl.tag == "TABLE-GROUP":
                    actual_tables.extend(tbl.findall("TABLE"))
                elif tbl.tag == "TABLE":
                    actual_tables.append(tbl)

                for table in actual_tables:
                    text_content = extract_table_as_text(table)
                    if text_content:
                        has_tables = True
                        for part in _split_by_paragraphs(text_content, max_chunk_chars):
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
                        continue

                    md = table_to_markdown(table)
                    if md.strip():
                        aclass = table.get("ACLASS") or None
                        has_tables = True
                        for part in _split_table_md(md, max_chunk_chars):
                            chunks.append(Chunk(
                                text=part,
                                metadata={
                                    **base_metadata,
                                    "section_path": section_path,
                                    "section_level": level,
                                    "has_table": True,
                                    "aclass": aclass,
                                },
                            ))

            if not has_text and not has_tables:
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
