# Idris2 명세 (Formal Specifications)

이 디렉토리는 PDF 문제 추출 시스템의 Idris2 형식 명세를 포함합니다.

## 구조

```
.specs/
├── System/     # 범용 시스템 명세 (재사용 가능)
└── Samples/    # 샘플 PDF별 구체적 명세 (검증용)
```

## System 명세 (범용)

**목적**: 어떤 PDF에도 적용 가능한 범용 타입 시스템

| 파일 | 설명 |
|------|------|
| `Base.idr` | 기본 타입 (Coord, BBox, VLine) |
| `PdfMetadata.idr` | 메타데이터 타입 (Subject, ExamType, etc.) |
| `LayoutDetection.idr` | 레이아웃 감지 (단 구분) |
| `OcrEngine.idr` | OCR 통합 (Tesseract/EasyOCR) |
| `ProblemExtraction.idr` | 문제/정답 추출 |
| `OutputFormat.idr` | 출력 형식 (1_prb, 1_sol, ZIP) |
| `Workflow.idr` | 전체 워크플로우 |

**특징**:
- PDF 파일 경로를 파라미터로 받음
- 특정 샘플에 종속되지 않음
- 증명 타입으로 속성 보장 (NoOverlap, ValidLayout, etc.)

## Samples 명세 (검증용)

**목적**: 특정 샘플 PDF의 구조를 명세로 작성하여 검증

예시:
```idris
-- Samples/SampleA.idr
sampleA_PdfPath : String
sampleA_ExpectedLayout : PageLayout
sampleA_ExpectedProblems : List ProblemNum

-- 추출 결과가 예상과 일치하는지 증명
ValidSampleA : ExtractionResult -> Type
```

**용도**:
- 단위 테스트
- 회귀 테스트
- 시스템 명세 검증

## 개발 원칙

### Formal Spec Driven Development

```
1. Idris2 명세 작성/수정
2. 명세 컴파일 검증 (idris2 --check)
3. Python 코드 구현
4. 실행 중 문제 발견 → 1번으로 돌아가기
```

**명세가 보장하는 것**:
- 타입 안전성 (컴파일 타임 검증)
- 속성 증명 (NoOverlap, AllContained, ValidLayout, etc.)
- 일관성 (코드가 명세를 따름)

### 명세 작성 가이드

1. **System 명세는 범용적으로**
   - PDF 파일을 파라미터로 받기
   - 특정 샘플에 종속되지 않기
   - 재사용 가능하게

2. **Samples 명세는 구체적으로**
   - 실제 PDF 구조 명시
   - 예상 결과 정의
   - 검증용 증명 타입

3. **증명 타입 활용**
   - 중요한 속성은 타입으로 표현
   - 컴파일러가 검증하도록

## 컴파일 방법

```bash
# System 명세 컴파일
cd .specs/System
idris2 --check Base.idr
idris2 --check LayoutDetection.idr
idris2 --check ProblemExtraction.idr
# ... 모든 파일

# 또는 전체 체크
idris2 --check Workflow.idr  # 다른 모듈들을 import하므로 함께 검증됨
```

## Python 구현과의 관계

```
Idris2 명세 (.specs/)       Python 구현 (core/)
├── Base.idr         →      base.py
├── LayoutDetection  →      layout_detector.py
├── ProblemExtraction →     problem_extractor.py (작성 예정)
└── OcrEngine        →      ocr_engine.py (작성 예정)
```

**규칙**:
- Python 코드는 Idris2 명세를 따라 구현
- 타입 이름, 함수 시그니처 최대한 일치
- 명세에 정의된 증명을 런타임 검증으로 구현

## 참고

- [Idris2 공식 문서](https://idris2.readthedocs.io/)
- System 디렉토리의 README.md: 각 모듈 상세 설명

