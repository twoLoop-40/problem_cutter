"""AgentTools 패키지
====================

에이전트가 `core` 모듈 기능을 단계별로 호출할 수 있도록 얇은 래퍼와
공용 타입을 제공합니다. 모든 툴은 `ToolResult`를 반환하며, 성공 여부,
메시지, 추가 데이터, 진단 정보를 표준화된 형태로 전달합니다.

주요 하위 모듈
---------------
- ``AgentTools.config``: 기본 설정값과 상수
- ``AgentTools.types``: 툴 결과/예외 타입
- ``AgentTools.pdf``: PDF 로딩 및 메타데이터 수집
- ``AgentTools.layout``: 레이아웃 감지 및 검증
- ``AgentTools.ocr``: OCR 실행(현재 스텁) 및 후처리 헬퍼
- ``AgentTools.extraction``: 문제/해설 추출과 이미지 크롭
- ``AgentTools.workflow``: 전체 파이프라인 실행/검증 래퍼

각 모듈은 ``core`` 패키지의 구현을 재사용하며, 에이전트 환경에서
상태/로그를 쉽게 전달할 수 있는 데이터 구조를 제공합니다.
"""

from .types import ToolResult, ToolDiagnostics, AgentToolError

from . import config, pdf, layout, ocr, extraction, workflow

__all__ = [
    "ToolResult",
    "ToolDiagnostics",
    "AgentToolError",
    "config",
    "pdf",
    "layout",
    "ocr",
    "extraction",
    "workflow",
]

