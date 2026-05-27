from __future__ import annotations
import re
import zipfile
from pathlib import Path

from lxml import etree as ET


def sanitize_xml(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)", "&amp;", text)
    return text.encode("utf-8")


def parse_xml(raw: bytes) -> ET._Element:
    sanitized = sanitize_xml(raw)
    parser = ET.XMLParser(recover=True)
    return ET.fromstring(sanitized, parser)


def classify_xml_file(filename: str) -> str:
    stem = Path(filename).stem
    if "_00760" in stem:
        return "audit_separate"
    if "_00761" in stem:
        return "audit_consolidated"
    return "main"


def load_xmls_from_zip(zip_path: str | Path) -> list[tuple[str, str, ET._Element]]:
    """Returns list of (filename, source_xml_type, root_element)."""
    results = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".xml"):
                continue
            with zf.open(info.filename) as f:
                raw = f.read()
            source_type = classify_xml_file(info.filename)
            root = parse_xml(raw)
            results.append((info.filename, source_type, root))
    return results
