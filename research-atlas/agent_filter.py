"""필터 에이전트 1/3 — tool 스키마 + 스모크 테스트.

테스트 문장 5개를 LLM에 보내 의도한 tool call이 나오는지 검증한다.
이 스키마가 확정되면 api/(2/3)와 프론트(3/3)가 이걸 기준으로 만들어진다.
실행: uv run python agent_filter.py
"""
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = "gpt-5.4-mini"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "filter",
            "description": "그래프에서 조건에 맞는 노드만 강조하고 나머지는 흐리게 한다. 여러 조건은 AND로 결합된다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ptype": {
                        "type": "string",
                        "enum": ["technique", "benchmark", "analysis", "survey", "other"],
                        "description": "논문/노드 유형",
                    },
                    "domain": {
                        "type": "string",
                        "description": "적용 분야 (예: medical, general). 범용은 general",
                    },
                    "date_after": {
                        "type": "string",
                        "description": "YYYY-MM. 이 시점 이후 등장한 노드만 (예: '2024년 이후' -> '2024-01')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_lineage",
            "description": "특정 노드의 계보(builds_on 조상/자손)만 보여준다. node는 반드시 시스템 프롬프트의 노드 목록에 있는 canonical 이름이어야 한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "노드 목록에 있는 canonical 이름 그대로"},
                    "direction": {
                        "type": "string",
                        "enum": ["ancestors", "descendants", "both"],
                        "description": "조상만/자손만/양쪽. 기본 both",
                    },
                },
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset",
            "description": "모든 필터를 해제하고 전체 그래프를 보여준다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def load_node_names():
    d = json.loads(Path("data/outputs/normalized.json").read_text())
    return sorted(v["canonical"] for v in d["nodes"].values())


def build_system_prompt(names):
    return (
        "너는 논문 지식그래프 화면을 조작하는 에이전트다. "
        "사용자의 한국어/영어 명령을 tool call로 번역한다. 말로 답하지 말고 반드시 tool을 호출한다.\n"
        "사용자가 노드를 지칭하면 아래 목록에서 가장 가까운 canonical 이름을 골라 그대로 쓴다. 단, 목록에 명백히 대응하는 이름이 없으면(오타·무관한 단어) 절대 임의의 노드로 대체하지 말고 tool을 호출하지 말고 '해당 노드를 찾지 못했다'고 한 문장으로 답한다.\n"
        f"노드 목록: {', '.join(names)}"
    )


SMOKE_QUERIES = [
    "벤치마크만 보여줘",                  # 기대: filter(ptype=benchmark)
    "RAG 계보만 보여줘",                  # 기대: focus_lineage(node=RAG계열 canonical)
    "2024년 이후 나온 것만",              # 기대: filter(date_after=2024-01)
    "medical 도메인 기법만",              # 기대: filter(ptype=technique, domain=medical)
    "다 보여줘",                          # 기대: reset()
]


def main():
    names = load_node_names()
    system = build_system_prompt(names)
    print(f"노드 {len(names)}개 로드, 시스템 프롬프트 {len(system)}자\n")

    for q in SMOKE_QUERIES:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": q}],
            tools=TOOLS,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            for tc in msg.tool_calls:
                print(f'"{q}"\n  -> {tc.function.name}({tc.function.arguments})\n')
        else:
            print(f'"{q}"\n  -> [tool call 없음] {msg.content[:80]}\n')


if __name__ == "__main__":
    main()
