from __future__ import annotations
from pathlib import Path

from .models import Chunk
from .xml_loader import load_xmls_from_zip
from .section_tree import parse_section_tree
from .chunker import build_chunks

COMPANY_MAP = {
    "00126380": "삼성전자",
    "00164779": "SK하이닉스",
    "00161383": "한미반도체",
}


class Parser:
    def __init__(self, max_chunk_chars: int = 1500):
        self.max_chunk_chars = max_chunk_chars

    def parse(self, zip_path: str | Path) -> list[Chunk]:
        zip_path = Path(zip_path)
        stem = zip_path.stem
        corp_code = stem.split("_")[0]
        rcept_no = stem.split("_")[1] if "_" in stem else stem
        company = COMPANY_MAP.get(corp_code, corp_code)

        xmls = load_xmls_from_zip(zip_path)
        all_chunks: list[Chunk] = []

        for filename, source_type, root in xmls:
            base_meta = {
                "company": company,
                "corp_code": corp_code,
                "rcept_no": rcept_no,
                "source_xml": source_type,
            }
            sections = parse_section_tree(root)
            chunks = build_chunks(sections, base_meta, self.max_chunk_chars)
            all_chunks.extend(chunks)

        return all_chunks
