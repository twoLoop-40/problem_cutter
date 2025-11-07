"""
검증 툴 - 문제 추출 결과 검증

주요 기능:
1. 순차 검증: 문제 번호가 1, 2, 3... 순서대로 있는지
2. 중복 검사: 같은 번호가 여러 번 나오는지
3. 누락 감지: 빠진 문제 번호 찾기
"""

from typing import List, Tuple, Dict, Optional
from collections import Counter

from .types import ToolResult, ToolDiagnostics


def validate_problem_sequence(
    found_numbers: List[int],
    expected_start: int = 1,
    expected_count: Optional[int] = None
) -> ToolResult:
    """문제 번호 순차 검증"""
    diagnostics = ToolDiagnostics()

    if not found_numbers:
        return ToolResult(
            success=False,
            message="추출된 문제가 없습니다",
            data={"found": [], "missing": [], "duplicates": [], "issues": ["no_problems"]},
            diagnostics=diagnostics
        )

    # 예상 범위 계산
    if expected_count is None:
        expected_count = max(found_numbers) - expected_start + 1

    expected_end = expected_start + expected_count - 1
    expected_numbers = list(range(expected_start, expected_end + 1))

    # 중복 검사
    counter = Counter(found_numbers)
    duplicates = [num for num, count in counter.items() if count > 1]

    # 누락 검사
    found_set = set(found_numbers)
    missing = [num for num in expected_numbers if num not in found_set]

    # 순서 검사
    sorted_numbers = sorted(found_numbers)
    out_of_order = found_numbers != sorted_numbers

    # 이슈 수집
    issues = []
    if duplicates:
        issues.append("duplicate")
    if missing:
        issues.append("missing")
    if out_of_order:
        issues.append("out_of_order")

    # 검증 결과
    is_valid = len(issues) == 0

    result_data = {
        "is_valid": is_valid,
        "expected_count": expected_count,
        "found_count": len(set(found_numbers)),
        "found_numbers": found_numbers,
        "missing": missing,
        "duplicates": duplicates,
        "issues": issues
    }

    message = f"✅ 검증 통과" if is_valid else f"❌ 검증 실패: {len(issues)}개 이슈"

    return ToolResult(
        success=is_valid,
        message=message,
        data=result_data,
        diagnostics=diagnostics
    )


def suggest_retry_params(
    validation_result: Dict,
    current_params: Dict[str, any]
) -> ToolResult:
    """검증 결과를 바탕으로 재시도 파라미터 제안"""
    diagnostics = ToolDiagnostics()
    new_params = current_params.copy()

    issues = validation_result.get("issues", [])

    if "missing" in issues:
        old_x = new_params.get("max_x_position", 300)
        old_conf = new_params.get("min_confidence", 50)
        new_params["max_x_position"] = min(500, old_x + 50)
        new_params["min_confidence"] = max(30, old_conf - 10)

    if "duplicate" in issues:
        old_conf = new_params.get("min_confidence", 50)
        new_params["min_confidence"] = min(70, old_conf + 10)

    return ToolResult(
        success=True,
        message=f"재시도 파라미터 조정 완료",
        data={"old_params": current_params, "new_params": new_params},
        diagnostics=diagnostics
    )
