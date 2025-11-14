"""
OCR Engine Registry (플러그인 등록 시스템)

Idris2 명세: Specs/System/Ocr/Interface.idr

새로운 OCR 엔진을 등록하고 관리하는 중앙 레지스트리
"""

from typing import Dict, Optional
from .interface import OcrEngineInterface, OcrEngineType


class OcrEngineRegistry:
    """
    OCR 엔진 레지스트리

    플러그인 패턴: 새 엔진 추가 시 register()만 호출하면 됨
    """

    _engines: Dict[OcrEngineType, OcrEngineInterface] = {}

    @classmethod
    def register(cls, engine_type: OcrEngineType, engine: OcrEngineInterface):
        """
        새 OCR 엔진 등록

        Args:
            engine_type: 엔진 타입
            engine: 엔진 인스턴스 (OcrEngineInterface 구현체)
        """
        cls._engines[engine_type] = engine
        print(f"[Registry] OCR 엔진 등록: {engine_type.value} ({engine.name()})")

    @classmethod
    def get(cls, engine_type: OcrEngineType) -> Optional[OcrEngineInterface]:
        """
        등록된 엔진 가져오기

        Args:
            engine_type: 엔진 타입

        Returns:
            OcrEngineInterface: 엔진 인스턴스 (없으면 None)
        """
        return cls._engines.get(engine_type)

    @classmethod
    def is_available(cls, engine_type: OcrEngineType) -> bool:
        """
        엔진 사용 가능 여부 확인

        Args:
            engine_type: 엔진 타입

        Returns:
            bool: 등록되어 있고 사용 가능하면 True
        """
        engine = cls.get(engine_type)
        return engine is not None and engine.is_available()

    @classmethod
    def list_available(cls) -> list[OcrEngineType]:
        """
        사용 가능한 모든 엔진 목록

        Returns:
            list[OcrEngineType]: 사용 가능한 엔진 타입 목록
        """
        return [
            engine_type
            for engine_type, engine in cls._engines.items()
            if engine.is_available()
        ]
