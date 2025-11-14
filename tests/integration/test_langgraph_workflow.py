"""
LangGraph Workflow 테스트 스크립트
"""

import sys
from pathlib import Path

from app.agents.workflow_impl import (
    create_extraction_workflow,
    create_initial_state,
    initialize_ocr_registry,
)


def main():
    # PDF 경로
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # 기본 샘플 사용
        pdf_path = "samples/통합과학_1_샘플.pdf"

    if not Path(pdf_path).exists():
        print(f"❌ PDF not found: {pdf_path}")
        return

    print("=" * 80)
    print("LangGraph Workflow 테스트")
    print("=" * 80)
    print(f"PDF: {pdf_path}")
    print()

    # 1. OCR 레지스트리 초기화
    print("[1] OCR 레지스트리 초기화...")
    initialize_ocr_registry()
    print()

    # 2. 워크플로우 생성
    print("[2] LangGraph 워크플로우 생성...")
    workflow = create_extraction_workflow()
    print()

    # 3. 초기 상태 생성
    print("[3] 초기 상태 생성...")
    initial_state = create_initial_state(
        job_id="test_001",
        pdf_path=pdf_path,
    )
    print(f"  - Job ID: {initial_state['job_id']}")
    print(f"  - PDF: {initial_state['pdf_path']}")
    print(f"  - OCR Strategy: {initial_state['ocr_strategy'].stage1_engine.value}")
    print()

    # 4. 워크플로우 실행
    print("[4] 워크플로우 실행...")
    print("-" * 80)

    try:
        final_state = workflow.invoke(initial_state)

        print("-" * 80)
        print()

        # 5. 결과 출력
        print("[5] 실행 결과:")
        print(f"  - 상태: {final_state['current_state']}")
        print(f"  - 진행률: {final_state['progress']}%")
        print(f"  - 메시지: {final_state['message']}")
        print(f"  - 검출된 문제: {final_state['detected_problems']}")
        print(f"  - 누락된 문제: {final_state.get('missing_problems', [])}")
        print(f"  - 출력 디렉토리: {final_state.get('output_dir', 'N/A')}")
        print(f"  - ZIP 경로: {final_state.get('zip_path', 'N/A')}")
        print()

        if final_state.get("error"):
            print(f"  ⚠️ 에러: {final_state['error']}")
        else:
            print("  ✅ 성공!")

    except Exception as e:
        print(f"❌ 워크플로우 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
