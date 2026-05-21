"""Step 3 평가용 쿼리 셋 + 정답 라벨.
Hit Rate @ k, MRR 계산용. doc_id 매칭으로 정답 판정."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Query:
    text: str
    answer_doc: str       # 정답 문서 (Wikipedia 인물 페이지 stem)
    lang: str             # "en" | "ko"
    difficulty: str       # "easy" | "medium" | "hard"
    note: str = ""

QUERIES = [
    # Albert Einstein
    Query("Einstein Nobel Prize",              "Albert_Einstein", "en", "easy"),
    Query("아인슈타인 상대성 이론",              "Albert_Einstein", "ko", "medium", "ko cross-lingual"),

    # Marie Curie
    Query("Curie radium polonium discovery",   "Marie_Curie",     "en", "easy"),
    Query("퀴리 부인 원소",                     "Marie_Curie",     "ko", "hard", "일반어→고유명사 도약"),

    # Isaac Newton
    Query("Newton laws of motion",             "Isaac_Newton",    "en", "easy"),
    Query("뉴턴 만유인력",                      "Isaac_Newton",    "ko", "medium"),

    # Charles Darwin
    Query("Darwin evolution natural selection","Charles_Darwin",  "en", "easy"),
    Query("다윈 진화론 자연선택",                "Charles_Darwin",  "ko", "medium"),

    # Alan Turing
    Query("Turing machine computation",        "Alan_Turing",     "en", "easy"),
    Query("튜링 기계 계산 가능성",               "Alan_Turing",     "ko", "medium"),

    # Ada Lovelace
    Query("Ada Lovelace Analytical Engine",    "Ada_Lovelace",    "en", "easy"),
    Query("에이다 러브레이스 프로그래머",         "Ada_Lovelace",    "ko", "medium"),

    # Nikola Tesla
    Query("Tesla alternating current",         "Nikola_Tesla",    "en", "easy"),
    Query("테슬라 교류 전기",                   "Nikola_Tesla",    "ko", "medium"),

    # Richard Feynman
    Query("Feynman quantum electrodynamics",   "Richard_Feynman", "en", "easy"),
    Query("파인만 양자역학 강의",                "Richard_Feynman", "ko", "medium"),
]

assert len(QUERIES) == 16
assert sum(q.lang == "en" for q in QUERIES) == 8
assert sum(q.lang == "ko" for q in QUERIES) == 8
