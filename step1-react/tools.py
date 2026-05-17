"""에이전트가 사용할 도구 정의.

각 도구는 Tool 클래스의 인스턴스로 표현된다.
- name: LLM이 호출할 때 쓸 식별자
- description: LLM이 "언제 이 도구를 쓸지" 이해할 자연어 설명
- call: 실제 실행 함수 (단일 문자열 인자를 받아 문자열 반환)

스타일 A (텍스트 파싱 ReAct)에서는 도구가 단일 문자열 인자만 받는 게 가장 안전하다.
LLM이 복잡한 JSON 구조를 100% 정확히 만들어내기 어려운데,
단일 문자열은 어떤 모델이든 잘 만든다.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    """LLM이 호출할 수 있는 도구를 표현한다.
    
    Attributes:
        name: 도구 식별자 (영문 소문자, 언더스코어 권장)
        description: LLM이 보게 될 설명. 어떤 입력을 받고 무엇을 반환하는지 명시.
        call: 실제 실행될 함수. str 인자를 받고 str 결과를 반환.
    """
    name: str
    description: str
    call: Callable[[str], str]
    
    def run(self, argument: str) -> str:
        """도구 실행 + 에러 핸들링.
        
        도구 함수가 예외를 던지면 에이전트가 죽지 않도록 잡아서
        에러 메시지를 문자열로 반환한다. 그러면 LLM이 결과를 보고
        "아, 이 인자로는 안 되네, 다른 걸 시도하자" 같은 판단이 가능.
        """
        try:
            return str(self.call(argument))
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"


# ============================================================
# Tool 1: Calculator
# ============================================================
import ast
import operator

# 허용된 연산자 → 실제 Python 함수 매핑
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,  # 단항 마이너스: -5
}


def _safe_eval(node: ast.AST) -> float:
    """AST 노드를 재귀적으로 평가. 허용된 노드만 통과시킨다."""
    if isinstance(node, ast.Constant):  # 숫자 리터럴
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Disallowed constant: {node.value!r}")
    
    if isinstance(node, ast.BinOp):  # 이항 연산: a + b, a * b
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.left), _safe_eval(node.right))
    
    if isinstance(node, ast.UnaryOp):  # 단항 연산: -x
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.operand))
    
    # 그 외 모든 노드는 거부 (변수, 함수 호출, 속성 접근 등)
    raise ValueError(f"Disallowed expression node: {type(node).__name__}")


def calculate(expression: str) -> str:
    """수학 표현식을 안전하게 평가한다.
    
    예: "2 + 3 * 4" → "14"
    예: "(1 + 2) ** 10" → "59049"
    """
    tree = ast.parse(expression, mode="eval")
    result = _safe_eval(tree.body)
    return str(result)


calculator_tool = Tool(
    name="calculator",
    description=(
        "Evaluates a mathematical expression and returns the result. "
        "Supports +, -, *, /, %, ** (power), and parentheses. "
        "Input must be a single math expression as a string, e.g. '2 + 3 * 4'. "
        "Does NOT support variables or function calls."
    ),
    call=calculate,
)



# ============================================================
# Tool 2: Wikipedia Search (REST API 직접 호출)
# ============================================================
import requests

# 모든 외부 API 호출에 공통으로 쓸 설정
_WIKI_API_BASE = "https://en.wikipedia.org/api/rest_v1"
_WIKI_SEARCH_API = "https://en.wikipedia.org/w/api.php"
_WIKI_TIMEOUT = 10  # 초
_WIKI_MAX_CHARS = 1000
_WIKI_USER_AGENT = "step1-react-agent/0.1 (learning project)"

# 모든 요청에 공통으로 붙일 헤더
_WIKI_HEADERS = {"User-Agent": _WIKI_USER_AGENT}


def _fetch_wiki_summary(title: str) -> dict | None:
    """Wikipedia REST API의 page summary 엔드포인트 호출.
    
    Returns:
        성공 시 응답 JSON (dict), 404면 None.
    Raises:
        requests.HTTPError: 404 외의 HTTP 에러.
        requests.RequestException: 네트워크 에러.
    """
    url = f"{_WIKI_API_BASE}/page/summary/{title}"
    response = requests.get(url, headers=_WIKI_HEADERS, timeout=_WIKI_TIMEOUT)
    
    if response.status_code == 404:
        return None
    response.raise_for_status()  # 그 외 4xx/5xx는 예외 던지기
    return response.json()


def _search_wiki_titles(query: str, limit: int = 5) -> list[str]:
    """OpenSearch API로 검색어와 매치되는 페이지 제목 목록을 가져온다.
    
    Returns: 페이지 제목 리스트 (관련도 순).
    """
    params = {
        "action": "opensearch",
        "search": query,
        "limit": limit,
        "namespace": 0,  # 본문 페이지만 (Talk, User 등 제외)
        "format": "json",
    }
    response = requests.get(
        _WIKI_SEARCH_API,
        params=params,
        headers=_WIKI_HEADERS,
        timeout=_WIKI_TIMEOUT,
    )
    response.raise_for_status()
    
    # OpenSearch 응답 형식: [query, [titles], [descs], [urls]]
    data = response.json()
    return data[1] if len(data) > 1 else []


def wikipedia_search(query: str) -> str:
    """Wikipedia 페이지 요약을 반환한다.
    
    동작 전략:
    1) 쿼리를 페이지 제목으로 직접 시도 (summary API)
    2) 404면 검색 API로 후보를 받아 첫 번째 페이지로 재시도
    3) 검색 결과도 없으면 "not found" 반환
    4) 동음이의어 페이지면 후보 목록 반환 (LLM이 더 구체적으로 재시도)
    """
    query = query.strip()
    if not query:
        return "Error: query is empty."
    
    # 1) Direct lookup
    data = _fetch_wiki_summary(query.replace(" ", "_"))
    
    # 2) 못 찾으면 검색 fallback
    if data is None:
        titles = _search_wiki_titles(query, limit=5)
        if not titles:
            return f"No Wikipedia page found for '{query}'."
        # 검색 결과 첫 번째로 재시도
        data = _fetch_wiki_summary(titles[0].replace(" ", "_"))
        if data is None:
            # 검색은 됐는데 summary가 또 없는 경우 (희귀)
            return f"Found candidates but could not fetch summary: {', '.join(titles)}"
    
    # 3) 동음이의어 페이지 처리
    if data.get("type") == "disambiguation":
        # 동음이의어 페이지에는 후보 본문이 있긴 한데, 후보 목록은 별도 검색으로 보충
        candidates = _search_wiki_titles(query, limit=5)
        return (
            f"'{query}' is ambiguous. Possible pages: {', '.join(candidates)}. "
            f"Please retry with a more specific query."
        )
    
    # 4) 정상 응답 — 요약 추출
    extract = data.get("extract", "")
    title = data.get("title", query)
    
    if not extract:
        return f"Wikipedia page '{title}' has no summary."
    
    # 길이 제한
    if len(extract) > _WIKI_MAX_CHARS:
        extract = extract[:_WIKI_MAX_CHARS] + "... [truncated]"
    
    return f"[{title}] {extract}"


wikipedia_tool = Tool(
    name="wikipedia_search",
    description=(
        "Searches Wikipedia and returns a summary of the most relevant page. "
        "Input must be a single search query as a string, e.g. 'Marie Curie' or 'Einstein'. "
        "Use specific search terms — if the query is ambiguous, a list of options will be returned. "
        "Use this for factual questions about people, places, events, or concepts."
    ),
    call=wikipedia_search,
)


# ============================================================
# Tool Registry — 에이전트가 도구 호출 시 여기서 조회
# ============================================================
ALL_TOOLS: dict[str, Tool] = {
    "calculator": calculator_tool,
    "wikipedia_search": wikipedia_tool,
}


def format_tools_for_prompt(tools: dict[str, Tool] = ALL_TOOLS) -> str:
    """도구들의 이름과 설명을 LLM에 알릴 텍스트로 포맷한다.
    
    이 함수가 만든 텍스트가 시스템 프롬프트의 일부가 된다.
    LLM은 이걸 보고 "어떤 도구가 있고 언제 쓰는지" 학습한다.
    
    출력 형식:
        - calculator: Evaluates a mathematical expression...
        - wikipedia_search: Searches Wikipedia and returns...
    """
    lines = []
    for name, tool in tools.items():
        lines.append(f"- {name}: {tool.description}")
    return "\n".join(lines)
