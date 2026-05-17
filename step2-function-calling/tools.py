"""에이전트가 사용할 도구 — Function calling 버전.

Style A (1단계)와의 차이:
- description은 여전히 자연어이지만, 별도 'parameters'에 JSON Schema 정의
- argument가 단일 문자열 → JSON 객체 (필드명 명시)
- LLM이 직접 JSON arguments를 생성, 우리는 파싱 안 함 (vLLM이 해줌)
"""
from dataclasses import dataclass
from typing import Callable

import ast
import operator


# ============================================================
# Tool 클래스
# ============================================================
@dataclass
class Tool:
    """Function calling용 도구 정의.
    
    Attributes:
        name: 도구 식별자 (영문 소문자 + 언더스코어)
        description: LLM이 보게 될 자연어 설명
        parameters: JSON Schema 형식의 인자 정의
        call: 실제 실행 함수. **kwargs로 호출됨 (인자 이름이 schema와 일치)
    """
    name: str
    description: str
    parameters: dict  # JSON Schema
    call: Callable
    
    def to_openai_schema(self) -> dict:
        """OpenAI tools API 형식으로 변환."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
    
    def run(self, **kwargs) -> str:
        """도구 실행 + 에러 핸들링.
        
        Style A와 달리 **kwargs를 받는다.
        LLM이 생성한 JSON에서 파싱된 인자가 그대로 전달됨.
        """
        try:
            return str(self.call(**kwargs))
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"


# ============================================================
# Tool 1: Calculator
# ============================================================
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Disallowed constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression node: {type(node).__name__}")


def calculate(expression: str) -> str:
    """수학 표현식을 안전하게 평가."""
    tree = ast.parse(expression, mode="eval")
    return str(_safe_eval(tree.body))


calculator_tool = Tool(
    name="calculator",
    description="Evaluate a mathematical expression. Supports +, -, *, /, %, ** and parentheses. Does not support variables or function calls.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression to evaluate, e.g. '2 + 3 * 4'.",
            },
        },
        "required": ["expression"],
    },
    call=calculate,
)


# ============================================================
# Tool 2: Wikipedia Search
# ============================================================
import requests

_WIKI_API_BASE = "https://en.wikipedia.org/api/rest_v1"
_WIKI_SEARCH_API = "https://en.wikipedia.org/w/api.php"
_WIKI_TIMEOUT = 10
_WIKI_MAX_CHARS = 1000
_WIKI_HEADERS = {"User-Agent": "step2-function-calling-agent/0.1 (learning project)"}


def _fetch_wiki_summary(title: str) -> dict | None:
    url = f"{_WIKI_API_BASE}/page/summary/{title}"
    response = requests.get(url, headers=_WIKI_HEADERS, timeout=_WIKI_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _search_wiki_titles(query: str, limit: int = 5) -> list[str]:
    params = {
        "action": "opensearch",
        "search": query,
        "limit": limit,
        "namespace": 0,
        "format": "json",
    }
    response = requests.get(
        _WIKI_SEARCH_API,
        params=params,
        headers=_WIKI_HEADERS,
        timeout=_WIKI_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data[1] if len(data) > 1 else []


def wikipedia_search(query: str) -> str:
    """Wikipedia 페이지 요약을 반환."""
    query = query.strip()
    if not query:
        return "Error: query is empty."
    
    data = _fetch_wiki_summary(query.replace(" ", "_"))
    
    if data is None:
        titles = _search_wiki_titles(query, limit=5)
        if not titles:
            return f"No Wikipedia page found for '{query}'."
        data = _fetch_wiki_summary(titles[0].replace(" ", "_"))
        if data is None:
            return f"Found candidates but could not fetch summary: {', '.join(titles)}"
    
    if data.get("type") == "disambiguation":
        candidates = _search_wiki_titles(query, limit=5)
        return (
            f"'{query}' is ambiguous. Possible pages: {', '.join(candidates)}. "
            f"Please retry with a more specific query."
        )
    
    extract = data.get("extract", "")
    title = data.get("title", query)
    
    if not extract:
        return f"Wikipedia page '{title}' has no summary."
    
    if len(extract) > _WIKI_MAX_CHARS:
        extract = extract[:_WIKI_MAX_CHARS] + "... [truncated]"
    
    return f"[{title}] {extract}"


wikipedia_tool = Tool(
    name="wikipedia_search",
    description="Search Wikipedia and return a summary of the most relevant page. Use specific search terms — ambiguous queries return a list of options. Use this for factual questions about people, places, events, or concepts.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'Marie Curie' or 'Einstein'.",
            },
        },
        "required": ["query"],
    },
    call=wikipedia_search,
)


# ============================================================
# Tool Registry
# ============================================================
ALL_TOOLS: dict[str, Tool] = {
    "calculator": calculator_tool,
    "wikipedia_search": wikipedia_tool,
}


def get_openai_tools_schema(tools: dict[str, Tool] = ALL_TOOLS) -> list[dict]:
    """OpenAI tools 인자에 넣을 schema 리스트 생성."""
    return [tool.to_openai_schema() for tool in tools.values()]
