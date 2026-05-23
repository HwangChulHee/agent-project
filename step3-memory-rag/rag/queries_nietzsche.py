"""차라투스트라 비주얼 노벨 — 해설 모드 쿼리셋 로더.

data/queries/queries.json에서 35개 쿼리 로드.
원본 md: data/queries/ep1_queries.md, ep2_queries.md (발표 자료 + 검수용).

사용:
    from rag.queries_nietzsche import QUERIES
    for q in QUERIES:
        print(q.text, q.category, q.episode, q.ground_truth_en)
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NietzscheQuery:
    text: str              # 한국어 사용자 쿼리
    category: str          # factoid | concept | metaphor | background
    episode: str           # ep1 | ep2
    ground_truth_en: str   # 영어 ground truth (RAGAs용)
    summary_ko: str = ""   # 한국어 요약 (참고용)


def _load_queries() -> list[NietzscheQuery]:
    path = Path(__file__).resolve().parent.parent / "data" / "queries" / "queries.json"
    if not path.exists():
        raise FileNotFoundError(
            f"queries.json 없음: {path}\n"
            f"먼저 실행: uv run python scripts/build_queries_json.py"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [NietzscheQuery(**q) for q in raw]


QUERIES = _load_queries()


# 검증
assert len(QUERIES) >= 30, f"쿼리 수 부족: {len(QUERIES)}"

_by_cat = {}
for q in QUERIES:
    _by_cat.setdefault(q.category, []).append(q)
_by_ep = {}
for q in QUERIES:
    _by_ep.setdefault(q.episode, []).append(q)

if __name__ == "__main__":
    print(f"총 {len(QUERIES)} 쿼리")
    print(f"  카테고리: {[(k, len(v)) for k, v in _by_cat.items()]}")
    print(f"  에피소드: {[(k, len(v)) for k, v in _by_ep.items()]}")
    print(f"\n샘플 3개:")
    for q in QUERIES[:3]:
        print(f"  [{q.episode}/{q.category}] {q.text}")
        print(f"    GT: {q.ground_truth_en[:80]}...")
