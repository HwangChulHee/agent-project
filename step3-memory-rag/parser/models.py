from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SectionNode:
    title: str
    atocid: str | None
    level: int
    children: list[SectionNode] = field(default_factory=list)
    body_elements: list = field(default_factory=list)


@dataclass
class Chunk:
    text: str
    metadata: dict
