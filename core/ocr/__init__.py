"""
OCR Plugin System

Idris2 명세: Specs/System/Ocr/Interface.idr

핵심 설계:
- OCR 엔진 독립적 인터페이스
- 플러그인 아키텍처 (새 엔진 추가 시 명세 변경 불필요)
- 표준화된 입력/출력 (OcrInput, OcrOutput)
"""

from .interface import (
    OcrInput,
    OcrOutput,
    TextBlock,
    OcrEngineInterface,
    OcrEngineType,
    OcrCategory,
    OcrStrategy,
    OcrExecutionResult,
)

from .registry import OcrEngineRegistry

__all__ = [
    "OcrInput",
    "OcrOutput",
    "TextBlock",
    "OcrEngineInterface",
    "OcrEngineType",
    "OcrCategory",
    "OcrStrategy",
    "OcrExecutionResult",
    "OcrEngineRegistry",
]
