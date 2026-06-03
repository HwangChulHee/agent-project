"""
개념 추출 — 자료 텍스트 → GPT mini → 개념·관계 (JSON).
기법/개념으로 타입 분명한 것만. 속성·수치·결과·모델명·벤치마크는 제외.
"""
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

PROMPT = """너는 LLM/에이전트 연구 분야의 개념 추출기다.
주어진 텍스트에서 '분야 개념'만 뽑아 JSON으로 출력한다.

개념의 type은 둘 중 하나로 분명해야 한다:
- 기법(method): 방법·접근법. 예: 리랭킹, RAG, 임베딩검색, 지식증류
- 개념(concept): 기법이 아닌 추상 대상. 예: agent memory, 멀티홉 QA

다음은 절대 뽑지 마라 (개념이 아니다):
- 속성·성능: low inference latency, well-distributed scores
- 중간 산출물·수치: calibrated soft labels, soft labels
- 특정 모델 이름: BGE-Reranker, Qwen3-Reranker, GPT-4o
- 평가·벤치마크 이름: memory retrieval benchmark
판단 기준: "이게 위키백과 표제어가 될 만한 분야 개념인가?" 아니면 제외.

관계(relations): from, rel, to. rel은 반드시 다음 셋 중 하나:
- is_a: 상하위 분류
- part_of: 부분-전체
- depends_on: 선수지식
셋에 안 맞으면 출력하지 마라.

개념명(id)은 자연어 표기 그대로 쓴다: 공백 유지, 언더스코어(_) 금지, 불필요한 복수형/수식어 제거 (예: "agent memory" O, "agent_memory" X).
숙련도·난이도는 절대 추측하지 마라.
설명 없이 JSON만:
{"concepts": [{"id":"...","type":"기법|개념"}], "relations": [{"from":"...","rel":"...","to":"..."}]}

텍스트:
"""


def extract(text):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT + text}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


if __name__ == "__main__":
    sample = (
        "Cross-encoder reranking improves retrieval quality in RAG systems "
        "by re-scoring the top candidates from an initial embedding-based "
        "retrieval. Unlike bi-encoders used for embedding search, "
        "cross-encoders jointly encode the query and document."
    )
    result = extract(sample)
    print("개념:", [(c["id"], c["type"]) for c in result.get("concepts", [])])
    print("관계:", [(r["from"], r["rel"], r["to"]) for r in result.get("relations", [])])
