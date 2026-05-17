"""ReAct 에이전트 테스트 실행 진입점.

여러 케이스로 에이전트를 돌려보고 동작을 관찰한다.
- T1: 도구 불필요 (간단한 인사)
- T2: 계산기만 필요
- T3: Wikipedia만 필요
- T4: 두 도구 모두 필요 (멀티스텝)
"""
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


def main():
    agent = Agent(verbose=True)
    
    for case in TEST_CASES:
        print(f"\n\n{'#'*70}")
        print(f"# {case['name']}")
        print(f"{'#'*70}")
        
        try:
            answer = agent.run(case["question"])
            print(f"\n>>> ANSWER: {answer}")
        except Exception as e:
            print(f"\n>>> ERROR: {type(e).__name__}: {e}")
        
        print(f"\n[steps taken: {len(agent.logs)}]")


if __name__ == "__main__":
    main()
