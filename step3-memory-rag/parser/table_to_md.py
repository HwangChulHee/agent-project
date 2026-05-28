from __future__ import annotations
from lxml import etree as ET

CELL_TAGS = {"TH", "TD", "TE", "TU"}

TEXT_CONTAINER_CELL_THRESHOLD = 500
TEXT_CONTAINER_MAX_COLS = 2


def _cell_text(cell: ET._Element) -> str:
    raw = (ET.tostring(cell, method="text", encoding="unicode") or "").strip()
    return " ".join(raw.split()) or " "


def extract_table_as_text(table_elem: ET._Element) -> str | None:
    """1~2열짜리 긴 텍스트 컨테이너 TABLE → 텍스트 추출. 일반 표면 None.

    [7] 강화: 한 셀이 500자 초과 + 전체 표가 최대 2열 이내일 때만 컨테이너로 인정.
    다열 표(숫자가 많고 한 셀만 긴 경우)는 표로 유지.
    """
    all_tr = table_elem.findall(".//TR")
    if not all_tr:
        return None

    max_cols = 0
    long_cell_text: str | None = None
    for tr in all_tr:
        cells = [c for c in tr if isinstance(c.tag, str) and c.tag in CELL_TAGS]
        col_count = sum(int(c.get("COLSPAN", "1") or "1") for c in cells)
        if col_count > max_cols:
            max_cols = col_count
        for cell in cells:
            raw = (ET.tostring(cell, method="text", encoding="unicode") or "").strip()
            if len(raw) > TEXT_CONTAINER_CELL_THRESHOLD and long_cell_text is None:
                long_cell_text = raw

    if long_cell_text is not None and max_cols <= TEXT_CONTAINER_MAX_COLS:
        return long_cell_text
    return None


def _drop_empty_columns(grid: list[list[str]]) -> list[list[str]]:
    """모든 행에서 빈 열은 통째로 제거. 적어도 1열은 유지."""
    if not grid:
        return grid
    n_cols = max(len(r) for r in grid)
    keep = [
        i for i in range(n_cols)
        if any(i < len(r) and r[i].strip() not in ("", " ") for r in grid)
    ]
    if not keep:
        return grid
    return [[r[i] if i < len(r) else " " for i in keep] for r in grid]


def table_to_markdown(table_elem: ET._Element) -> str:
    rows_data: list[list[str]] = []
    header_row_count = 0

    all_tr = table_elem.findall(".//TR")
    if not all_tr:
        return ""

    thead = table_elem.find(".//THEAD")
    thead_trs = set()
    if thead is not None:
        for tr in thead.findall("TR"):
            thead_trs.add(id(tr))

    max_cols = 0
    raw_rows: list[list[tuple[str, int, int]]] = []
    for tr in all_tr:
        cells = []
        for cell in tr:
            if not isinstance(cell.tag, str) or cell.tag not in CELL_TAGS:
                continue
            colspan = int(cell.get("COLSPAN", "1") or "1")
            rowspan = int(cell.get("ROWSPAN", "1") or "1")
            text = _cell_text(cell)
            cells.append((text, colspan, rowspan))
        raw_rows.append(cells)
        logical_cols = sum(cs for _, cs, _ in cells)
        if logical_cols > max_cols:
            max_cols = logical_cols

    if max_cols == 0:
        return ""

    if len(raw_rows) <= 1:
        return ""

    n_rows = len(raw_rows)
    grid: list[list[str]] = [[" "] * max_cols for _ in range(n_rows)]
    occupied: list[list[bool]] = [[False] * max_cols for _ in range(n_rows)]

    for r, cells in enumerate(raw_rows):
        col = 0
        for text, colspan, rowspan in cells:
            while col < max_cols and occupied[r][col]:
                col += 1
            if col >= max_cols:
                break
            for dr in range(rowspan):
                for dc in range(colspan):
                    rr = r + dr
                    cc = col + dc
                    if rr < n_rows and cc < max_cols:
                        occupied[rr][cc] = True
                        grid[rr][cc] = text if (dr == 0 and dc == 0) else " "
            col += colspan

    if thead_trs:
        header_row_count = sum(1 for tr in all_tr if id(tr) in thead_trs)
    else:
        first_cells = all_tr[0] if all_tr else []
        if any(c.tag == "TH" for c in first_cells if isinstance(c.tag, str)):
            header_row_count = 1

    if header_row_count == 0:
        header_row_count = 1

    # [1] 모든 행에서 빈 열 통째 제거 — header row 보존 위해 header 도 함께
    grid = _drop_empty_columns(grid)

    lines: list[str] = []
    for i, row in enumerate(grid):
        line = "| " + " | ".join(row) + " |"
        lines.append(line)
        if i == header_row_count - 1:
            sep = "| " + " | ".join("---" for _ in row) + " |"
            lines.append(sep)

    return "\n".join(lines)
