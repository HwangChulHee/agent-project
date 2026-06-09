"""경로 / 모델 상수. MAP=graphrag 환경변수로 GraphRAG 전용 맵 분리."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"          # PDF는 공용 (논문 겹쳐도 중복 다운 안 함)

# MAP 환경변수로 출력 폴더 분리: 기본 outputs / graphrag면 outputs_graphrag
_MAP = os.getenv("MAP", "")
OUT_DIR = DATA_DIR / ("outputs_graphrag" if _MAP == "graphrag" else "outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "gpt-5.4-mini"

# GraphRAG 전용 6편
GRAPHRAG_IDS = [
    "2404.16130",  # GraphRAG (원조)
    "2410.05779",  # LightRAG
    "2405.14831",  # HippoRAG
    "2502.14802",  # HippoRAG2 / RAG to Memory
    "2408.08921",  # Graph RAG survey
    "2503.21322",  # HyperGraphRAG
    # --- 의료 도메인 적용 (B: 관찰용) ---
    "2408.04187",  # Medical Graph RAG (MedGraphRAG)
    "2502.04413",  # MedRAG
    "2403.10131",  # RAFT (도메인 특화 RAG 적응)
    "2502.13010",  # AMG-RAG (Agentic Medical Graph-RAG)
    # --- 벤치마크/평가 유형 (가: 관찰용) ---
    "2309.01431",  # RGB (RAG Benchmark)
    "2407.11005",  # RAGBench
    # --- 분석/실증 유형 (다: 관찰용) ---
    "2401.14887",  # The Power of Noise (RAG 노이즈 분석)
    "2408.02854",  # RAG Taxonomy / Failure Points
]

# 기존 범용+RAG+에이전트 58편
FULL_IDS = [
    "2203.02155", "2305.18290", "2212.08073",
    "2201.11903", "2203.11171", "2305.10601", "2210.03629",
    "2205.10625", "2303.17651",
    "1706.03762", "1810.04805", "2005.14165", "1910.10683", "2312.00752",
    "2001.08361", "2203.15556", "2206.07682", "2204.02311",
    "2302.13971", "2307.09288",
    "2302.04761", "2303.11366", "2305.16291", "2304.03442",
    "2005.11401", "2002.08909",
    "2106.09685", "2305.14314", "2205.14135",
    "2109.01652", "2212.10560",
    "2101.03961",
    "2004.04906", "2004.12832", "2212.10496", "2310.11511",
    "2305.06983", "2301.12652", "2401.15884", "2304.09542", "2312.10997",
    "2401.18059", "2409.04701", "2312.06648", "2406.17526", "2410.12788",
    "2004.05150", "2310.19923", "2305.14283",
    "2308.08155", "2308.00352", "2303.17580", "2310.04406", "2305.04091",
]

# MAP에 따라 PAPER_IDS 선택
PAPER_IDS = GRAPHRAG_IDS if _MAP == "graphrag" else FULL_IDS
