"""
병렬 처리 LangGraph Workflow 테스트 스크립트

Idris2 명세: Specs/System/LangGraphWorkflow.idr
"""

import sys
import time
from pathlib import Path

from app.agents.parallel_workflow import (
    create_parallel_extraction_workflow,
    create_initial_state,
    initialize_ocr_registry,
)


def main():
    # PDF 경로
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # 기본 샘플 사용
        pdf_path = "samples/고3_과학탐구_생명과학Ⅰ_문항지.pdf"

    if not Path(pdf_path).exists():
        print(f"❌ PDF not found: {pdf_path}")
        return

    print("=" * 80)
    print("병렬 처리 LangGraph Workflow 테스트")
    print("=" * 80)
    print(f"PDF: {pdf_path}")
    print()

    # 1. OCR 레지스트리 초기화
    print("[1] OCR 레지스트리 초기화...")
    initialize_ocr_registry()
    print()

    # 2. 병렬 워크플로우 생성
    print("[2] 병렬 처리 LangGraph 워크플로우 생성...")
    workflow = create_parallel_extraction_workflow()
    print()

    # 3. 초기 상태 생성
    print("[3] 초기 상태 생성...")
    initial_state = create_initial_state(
        job_id="parallel_test_001",
        pdf_path=pdf_path,
        dpi=300,
    )
    print(f"  - Job ID: {initial_state['job_id']}")
    print(f"  - PDF: {initial_state['pdf_path']}")
    print(f"  - DPI: {initial_state['dpi']}")
    print()

    # 4. 워크플로우 실행 (시간 측정)
    print("[4] 병렬 워크플로우 실행...")
    print("-" * 80)

    start_time = time.time()

    try:
        final_state = workflow.invoke(initial_state)

        elapsed = time.time() - start_time

        print("-" * 80)
        print()

        # 5. 결과 출력
        print("[5] 실행 결과:")
        print(f"  - 실행 시간: {elapsed:.2f}초")
        print(f"  - 상태: {final_state['current_state']}")
        print(f"  - 진행률: {final_state['progress']}%")
        print(f"  - 메시지: {final_state['message']}")
        print(f"  - 전체 페이지: {final_state['total_pages']}")
        print()

        # 페이지별 상태
        if final_state.get("page_states"):
            print(f"  📄 페이지별 상태:")
            for page_state in final_state["page_states"]:
                page_num = page_state["page_num"]
                col_count = page_state["column_count"]
                print(f"    - 페이지 {page_num}: {col_count}단")

                for col_state in page_state["column_states"]:
                    col_idx = col_state["column_index"]
                    problems = col_state["found_problems"]
                    print(f"      → 컬럼 {col_idx}: {len(problems)}개 문제 {problems}")
            print()

        print(f"  - 검출된 문제: {final_state['detected_problems']}")
        print(f"  - 누락된 문제: {final_state.get('missing_problems', [])}")
        print(f"  - 출력 디렉토리: {final_state.get('output_dir', 'N/A')}")
        print(f"  - ZIP 경로: {final_state.get('zip_path', 'N/A')}")
        print()

        if final_state.get("error"):
            print(f"  ⚠️ 에러: {final_state['error']}")
        else:
            print(f"  ✅ 성공! (병렬 처리 완료)")

        # ZIP 파일 크기
        if final_state.get("zip_path"):
            zip_path = Path(final_state["zip_path"])
            if zip_path.exists():
                size_mb = zip_path.stat().st_size / (1024 * 1024)
                print(f"  📦 ZIP 파일: {size_mb:.1f}MB")

    except Exception as e:
        print(f"❌ 워크플로우 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
