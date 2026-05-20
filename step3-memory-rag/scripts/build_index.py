"""인덱싱 엔트리 포인트. data/wikipedia/ 전체 재인덱싱."""

import sys
from pathlib import Path

# 프로젝트 루트를 import path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from rag.indexer import Indexer


def main() -> int:
    load_dotenv()

    data_dir = ROOT / "data" / "wikipedia"
    indexer = Indexer()
    result = indexer.index_directory(data_dir)

    print()
    print("=" * 50)
    print(f"Files indexed:   {result['files']}")
    print(f"Total chunks:    {result['chunks']}")
    print(f"Collection:      {result['collection']}")
    print(f"DB path:         {result['db_path']}")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
