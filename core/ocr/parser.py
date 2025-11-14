"""
OCR Result Parser

Idris2 명세: Specs/System/Ocr/Parser.idr

OCR 출력 → 구조화된 정보 파싱
"""

import re
from typing import List, Optional
from dataclasses import dataclass

from .interface import OcrOutput, OcrExecutionResult, OcrEngineType


@dataclass
class ProblemMarker:
    """
    문제 번호 마커

    Idris2: Marker (when markerType = ProblemNumberMarker)
    """
    problem_number: int
    bbox: tuple[int, int, int, int]
    confidence: float
    matched_pattern: str
    original_text: str


# 문제 번호 패턴들 (Idris2: problemNumberPatterns)
PROBLEM_NUMBER_PATTERNS = [
    (r'^(\d+)\.$', "dot", 1),                # "1.", "2."
    (r'^[①-⑳]$', "circled", 2),              # "①", "②"
    (r'^\[(\d+)\]$', "bracket", 3),          # "[1]", "[2]"
    (r'^\((\d+)\)$', "parenthesis", 4),      # "(1)", "(2)"
    (r'^(\d{1,2})$', "digit_only", 10),      # "1", "2" (낮은 우선순위)
]


def parse_problem_numbers(
    ocr_output: OcrOutput,
    min_confidence: float = 0.6,
) -> List[int]:
    """
    OCR 출력에서 문제 번호 추출

    Idris2: parseMarkers (simplified)

    Args:
        ocr_output: OCR 출력
        min_confidence: 최소 신뢰도

    Returns:
        List[int]: 검출된 문제 번호 목록 (중복 제거, 정렬됨)
    """
    problem_numbers = []

    for block in ocr_output.blocks:
        if block.confidence < min_confidence:
            continue

        text = block.text.strip()

        # 각 패턴에 대해 매칭 시도
        for pattern, pattern_name, priority in PROBLEM_NUMBER_PATTERNS:
            match = re.match(pattern, text)
            if match:
                # 숫자 추출
                if pattern_name == "circled":
                    # ①-⑳ → 1-20 변환
                    number = ord(text) - ord('①') + 1
                else:
                    # 그룹에서 숫자 추출
                    number = int(match.group(1))

                if 1 <= number <= 50:  # 유효 범위
                    problem_numbers.append(number)
                break  # 첫 번째 매칭만 사용

    # 중복 제거 및 정렬
    return sorted(set(problem_numbers))


def ocr_output_to_execution_result(
    ocr_output: OcrOutput,
    engine: OcrEngineType,
    min_confidence: float = 0.6,
) -> OcrExecutionResult:
    """
    OcrOutput → OcrExecutionResult 변환

    Idris2: ocrOutputToExecutionResult

    Args:
        ocr_output: OCR 출력
        engine: 사용된 엔진
        min_confidence: 최소 신뢰도

    Returns:
        OcrExecutionResult: Agent가 사용하는 OCR 결과
    """
    problem_numbers = parse_problem_numbers(ocr_output, min_confidence)

    return OcrExecutionResult(
        engine=engine,
        detected_problems=problem_numbers,
        confidence=ocr_output.average_confidence,
        execution_time=ocr_output.execution_time,
        raw_output=ocr_output,
    )
