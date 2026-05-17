"""ReAct 에이전트 (Function calling 버전) 테스트.

1단계와 같은 4개 케이스로 비교 가능하게 구성.
show_reasoning=True/False 둘 다 테스트 가능.
"""
import sys
from agent import Agent


TEST_CASES = [
    {
        "name": "T1: No tool needed",
        "question": "Hi, how are you today?",
    },
    {
        "name": "T2: Calculator only",
        "question": "What is 17 * 23 + 100?",
    },
    {
        "name": "T3: Wikipedia only",
        "question": "Who is Marie Curie? Give me one sentence.",
    },
    {
        "name": "T4: Multi-step (both tools)",
        "question": "What year was Albert Einstein born? Add 100 to that year.",
    },
]


def main(show_reasoning: bool = False):
    agent = Agent(verbose=True, show_reasoning=show_reasoning)
    
    summary = []
    
    for case in TEST_CASES:
        print(f"\n\n{'#'*70}")
        print(f"# {case['name']}")
        print(f"{'#'*70}")
        
        try:
            answer = agent.run(case["question"])
            iterations = len(agent.logs)
            tool_calls = sum(len(log.tool_calls) for log in agent.logs)
            
            summary.append({
                "name": case["name"],
                "iterations": iterations,
                "tool_calls": tool_calls,
                "answer": answer[:100] + ("..." if len(answer) > 100 else ""),
            })
            
        except Exception as e:
            print(f"\n>>> ERROR: {type(e).__name__}: {e}")
            summary.append({
                "name": case["name"],
                "iterations": "ERROR",
                "tool_calls": "ERROR",
                "answer": str(e),
            })
    
    # 종합 요약
    print(f"\n\n{'='*70}")
    print(f"# SUMMARY (show_reasoning={show_reasoning})")
    print(f"{'='*70}")
    print(f"{'Case':<35} {'Iter':>6} {'Tools':>6}  Answer")
    print(f"{'-'*70}")
    for s in summary:
        print(f"{s['name']:<35} {str(s['iterations']):>6} {str(s['tool_calls']):>6}  {s['answer']}")


if __name__ == "__main__":
    # 명령행 인자로 thinking 모드 전환
    # 사용: python run.py [thinking]
    show_reasoning = (len(sys.argv) > 1 and sys.argv[1] == "thinking")
    main(show_reasoning=show_reasoning)
