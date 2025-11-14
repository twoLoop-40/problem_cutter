"""
OCR Engine Interface (추상화 계층)

Idris2 명세: Specs/System/Ocr/Interface.idr

모든 OCR 엔진은 이 인터페이스를 구현해야 함
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import numpy as np


# =============================================================================
# OCR Input (표준 입력)
# =============================================================================

@dataclass
class OcrInput:
    """
    OCR 입력 (Idris2: OcrInput)

    모든 OCR 엔진이 동일한 입력을 받음
    """
    image_path: str
    """이미지 경로 또는 Base64"""

    languages: List[str] = field(default_factory=lambda: ["kor", "eng"])
    """언어 코드 (예: "kor", "eng", "kor+eng")"""

    dpi: int = 300
    """DPI (이미지 해상도)"""

    options: Dict[str, str] = field(default_factory=dict)
    """추가 옵션 (엔진별로 다를 수 있음)"""


# =============================================================================
# OCR Output (표준 출력)
# =============================================================================

@dataclass
class TextBlock:
    """
    단일 텍스트 블록 결과 (Idris2: TextBlock)

    모든 OCR 엔진이 동일한 출력 형식 사용
    """
    text: str
    """인식된 텍스트"""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    """위치 (BBox)"""

    confidence: float
    """신뢰도 (0.0 ~ 1.0)"""

    detected_language: Optional[str] = None
    """감지된 언어 (있는 경우)"""


@dataclass
class OcrOutput:
    """
    OCR 실행 결과 (Idris2: OcrOutput)
    """
    blocks: List[TextBlock]
    """텍스트 블록 목록"""

    execution_time: int
    """전체 실행 시간 (초)"""

    average_confidence: float
    """전체 평균 신뢰도"""

    engine_name: str
    """사용된 엔진 이름 (디버깅용)"""


# =============================================================================
# OCR Engine Types
# =============================================================================

class OcrEngineType(Enum):
    """
    OCR 엔진 타입 (Idris2: OcrEngineType)

    새로운 엔진 추가 시 여기에 추가만 하면 됨
    """
    TESSERACT = "tesseract"
    MATHPIX = "mathpix"
    CLAUDE_VISION = "claude_vision"
    GPT4_VISION = "gpt4_vision"
    PADDLEOCR = "paddleocr"
    EASYOCR = "easyocr"
    CUSTOM = "custom"


class OcrCategory(Enum):
    """
    OCR 전략 카테고리 (Idris2: OcrCategory)
    """
    FAST = "fast"          # 빠르고 저렴 (Tesseract, PaddleOCR, EasyOCR)
    ACCURATE = "accurate"  # 느리고 비쌈 (Mathpix, Claude Vision, GPT-4V)


def categorize_engine(engine_type: OcrEngineType) -> OcrCategory:
    """
    엔진 타입의 카테고리 분류 (Idris2: categorizeEngine)
    """
    fast_engines = {
        OcrEngineType.TESSERACT,
        OcrEngineType.PADDLEOCR,
        OcrEngineType.EASYOCR,
    }

    if engine_type in fast_engines:
        return OcrCategory.FAST
    else:
        return OcrCategory.ACCURATE


@dataclass
class OcrStrategy:
    """
    OCR 실행 전략 (Idris2: OcrStrategy)

    Agent는 이 전략만 지정하고, 실제 엔진 선택은 런타임에 결정
    """
    stage1_engine: OcrEngineType
    """1단계 엔진 (Fast)"""

    stage2_engine: OcrEngineType
    """2단계 엔진 (Accurate)"""

    max_retries: int = 2
    """최대 재시도 횟수"""

    fallback_engine: Optional[OcrEngineType] = None
    """Fallback 엔진 (실패 시)"""


# 기본 OCR 전략 (Tesseract → Mathpix)
DEFAULT_OCR_STRATEGY = OcrStrategy(
    stage1_engine=OcrEngineType.TESSERACT,
    stage2_engine=OcrEngineType.MATHPIX,
    max_retries=2,
    fallback_engine=OcrEngineType.EASYOCR,
)


# =============================================================================
# OCR Execution Result (Agent 친화적)
# =============================================================================

@dataclass
class OcrExecutionResult:
    """
    OCR 실행 결과 (Agent 친화적) (Idris2: OcrExecutionResult)

    Agent는 텍스트 블록 목록이 아니라 "검출된 문제 번호"만 필요함
    OCR → 문제 번호 파싱은 별도 모듈에서 처리
    """
    engine: OcrEngineType
    """사용된 엔진"""

    detected_problems: List[int]
    """검출된 문제 번호 (파싱 완료)"""

    confidence: float
    """평균 신뢰도"""

    execution_time: int
    """실행 시간"""

    raw_output: Optional[OcrOutput] = None
    """원본 OCR 출력 (디버깅용)"""


# =============================================================================
# OCR Engine Interface (추상 인터페이스)
# =============================================================================

class OcrEngineInterface(ABC):
    """
    OCR 엔진 추상 인터페이스 (Idris2: OcrEngineInterface)

    모든 OCR 엔진은 이 인터페이스를 구현해야 함
    """

    @abstractmethod
    def name(self) -> str:
        """엔진 이름"""
        pass

    @abstractmethod
    def execute(self, input_data: OcrInput) -> OcrOutput:
        """
        OCR 실행

        Args:
            input_data: OCR 입력 (이미지 경로 + 옵션)

        Returns:
            OcrOutput: OCR 출력 (텍스트 블록 목록)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        엔진 사용 가능 여부 (API 키 확인 등)

        Returns:
            bool: 사용 가능하면 True
        """
        pass

    @abstractmethod
    def estimated_cost(self, input_data: OcrInput) -> int:
        """
        예상 비용 (센트 단위, 무료는 0)

        Args:
            input_data: OCR 입력

        Returns:
            int: 예상 비용 (센트)
        """
        pass
