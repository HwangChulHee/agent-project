"""vLLM 서버 연결 확인용 스모크 테스트.

학습 코드 짜기 전에 OpenAI SDK ↔ vLLM 통신이 되는지만 확인.
한국어 인사 한 번 받으면 끝.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# .env 파일 읽기
load_dotenv()

# OpenAI SDK 초기화 (vLLM의 OpenAI 호환 API 사용)
client = OpenAI(
    base_url=os.getenv("VLLM_BASE_URL"),
    api_key=os.getenv("VLLM_API_KEY"),
)

# 간단한 호출
response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=[
        {"role": "user", "content": "Say 'hello' in Korean in one word."}
    ],
    max_tokens=20,
    temperature=0.7,
)

# 결과 출력
print(f"응답: {response.choices[0].message.content}")
print(f"토큰 사용: prompt={response.usage.prompt_tokens}, "
      f"completion={response.usage.completion_tokens}")
