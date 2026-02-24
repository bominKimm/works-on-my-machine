#!/usr/bin/env python3
"""
RAG를 통한 보안 검토 데모.

사용법 (프로젝트 루트 agenthon에서):
  python example/demo_rag_review.py

동작:
  1. example/sample_design.bicep 로드 (의도적 위반 포함)
  2. CAT-006 등에서 RAG로 관련 정책 청크 검색 후 출력
  3. Policy Agent handle_design_review 호출 → 위반/권장 + policy_ref 출력
"""

import asyncio
import json
import sys
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import data.env  # noqa: F401
except ImportError:
    pass

SAMPLE_BICEP_PATH = Path(__file__).parent / "sample_design.bicep"
DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "vector_index.json"


def main() -> None:
    print("=" * 60)
    print("1. 샘플 Bicep 로드 (이미지 → 변환된 설계로 가정)")
    print("=" * 60)
    if not SAMPLE_BICEP_PATH.exists():
        print(f"파일 없음: {SAMPLE_BICEP_PATH}")
        return
    bicep_text = SAMPLE_BICEP_PATH.read_text(encoding="utf-8")
    print(bicep_text[:800])
    print("... (생략)\n")

    print("=" * 60)
    print("2. 설계(Bicep) 기반 참고 카테고리 선별 + RAG 검색")
    print("=" * 60)
    if not INDEX_PATH.exists():
        print(f"벡터 인덱스 없음: {INDEX_PATH}")
        print("먼저 실행: python -m data.rag index status=active")
        return

    from data.rag import load_index, search
    from agents.policy_agent import _get_relevant_categories_for_bicep

    # 이 Bicep에선 NSG, Storage, Web 이 있으므로 CAT-006 + CAT-002, CAT-003, CAT-005 등이 선별됨
    relevant_cats = _get_relevant_categories_for_bicep(bicep_text)
    print(f"  선별된 카테고리: {relevant_cats} (CAT-006 항상 포함, 나머지는 리소스 유형 기준)")

    index = load_index(INDEX_PATH)
    policy_query = (
        "개발 설계 보안성 검토, NSG sourceAddressPrefix 금지, "
        "스토리지 HTTPS 전용 TLS, 웹앱 httpsOnly, 방화벽 규칙"
    )

    # CAT-006 검색 (설계 검토 전용)
    results_006 = search(policy_query, k=5, index=index, metadata_filter={"collection": "CAT-006"})
    print(f"\n[CAT-006 개발 설계 보안성 검토] 상위 {len(results_006)}개 청크:")
    for i, r in enumerate(results_006, 1):
        print(f"\n--- 청크 {i} (유사도: {r['score']}, 출처: {r.get('path', r.get('id'))}) ---")
        print((r.get("content") or "")[:400] + ("..." if len(r.get("content") or "") > 400 else ""))

    # 다른 카테고리에서도 검색 (선택)
    results_003 = search(policy_query, k=2, index=index, metadata_filter={"collection": "CAT-003"})
    if results_003:
        print(f"\n[CAT-003 네트워크] 상위 {len(results_003)}개 청크 (참고용):")
        for i, r in enumerate(results_003, 1):
            print(f"  {i}. [{r['score']}] {r.get('path', '')} ...")

    print("\n" + "=" * 60)
    print("3. Policy Agent 보안 검토 (Bicep + RAG 청크 → LLM → 위반/권장)")
    print("=" * 60)
    async def run_review():
        from agents.policy_agent import handle_design_review
        return await handle_design_review(bicep_text, "")

    result = asyncio.run(run_review())
    print("\n[검토 결과]")
    print("  status:", result.get("status"))
    print("  summary:", result.get("summary", ""))
    print("\n  violations:", json.dumps(result.get("violations", []), ensure_ascii=False, indent=4))
    print("  recommendations:", json.dumps(result.get("recommendations", []), ensure_ascii=False, indent=4))
    if result.get("policy_citations"):
        print("  policy_citations (일부):", result["policy_citations"][:3])

    print("\n[데모 끝] 위와 같이 RAG가 CAT-006 등에서 정책 청크를 가져오고, LLM이 Bicep과 비교해 위반/권장을 policy_ref와 함께 출력합니다.")


if __name__ == "__main__":
    main()
