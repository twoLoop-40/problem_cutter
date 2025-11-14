"""
LangGraph Agent System

Idris2 명세: Specs/System/Agent/

핵심 설계:
- LangGraph StateGraph 기반 워크플로우
- OCR 엔진 독립적 설계
- 2-Stage 전략 (Fast → Accurate)
- 자동 검증 및 재시도
"""

from .state import ExtractionState
from .workflow import create_extraction_workflow

__all__ = [
    "ExtractionState",
    "create_extraction_workflow",
]
