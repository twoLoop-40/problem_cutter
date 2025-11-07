# PDF Problem Cutter - PDF 문제 분리 프로젝트

> PDF 시험지에서 문제와 정답을 자동으로 분리하여 개별 파일로 저장하는 도구

## 📋 프로젝트 개요

이 프로젝트는 PDF 형식의 시험지에서:
- **문제**(1_prb, 2_prb, ...)와 **정답**(1_sol, 2_sol, ...)을 자동 분리
- 2단/3단 편집된 PDF 처리
- 메타데이터 추출 (과목, 학교, 시험 종류 등)
- 개별 이미지/PDF 파일로 출력
- ZIP 파일로 패키징

## 🏗️ 프로젝트 구조

```
problem_cutter/
├── .specs/                    # Idris2 타입 명세 (설계)
│   ├── Base.idr              # ✅ 기본 타입 (BBox, Coord, Region)
│   ├── PdfMetadata.idr       # ✅ 메타데이터 타입
│   ├── LayoutDetection.idr   # ✅ 레이아웃 감지 (1단/2단/3단)
│   ├── ProblemExtraction.idr # ✅ 문제/정답 추출
│   ├── OutputFormat.idr      # ✅ 출력 형식 (파일명, ZIP)
│   └── Workflow.idr          # ✅ 전체 워크플로우
│
├── core/                      # Python 구현 (예정)
├── tests/                     # 테스트 (예정)
├── samples/                   # 샘플 PDF
├── output/                    # 결과물
└── README.md                  # 이 파일

```

## ✅ 현재 상태

### 완료된 작업
- ✅ **6개 Idris2 명세 작성 완료** (모두 컴파일 성공)
- ✅ 타입 시스템 설계 완료
- ✅ 증명 타입 정의 (NoOverlap, ValidLayout, ProblemsInOrder 등)

### 다음 단계
- ⏳ Python 구현 (`core/` 모듈)
- ⏳ OCR 통합 (Mathpix 또는 Tesseract)
- ⏳ 테스트 작성
- ⏳ CLI 인터페이스

## 📐 Idris2 명세 개요

### 1. Base.idr - 기본 타입
```idris
- Coord: 2D 좌표
- BBox: 바운딩 박스
- VLine: 수직선 (컬럼 구분)
- NoOverlap: 영역 겹침 방지 증명
- AllContained: 포함 관계 증명
```

### 2. PdfMetadata.idr - 메타데이터
```idris
- Subject: 과목 (수학, 과학, 국어 등)
- ExamType: 시험 종류 (중간고사, 기말고사 등)
- GradeLevel: 학년 (초/중/고)
- PdfMeta: 완전한 메타데이터 레코드
```

### 3. LayoutDetection.idr - 레이아웃 감지
```idris
- ColumnCount: 1단/2단/3단
- DetectionMethod: 감지 방법 (수직선/여백/문제 위치)
- PageLayout: 페이지 레이아웃 정보
- ValidLayout: 유효한 레이아웃 증명
```

### 4. ProblemExtraction.idr - 문제 추출
```idris
- ContentType: 컨텐츠 타입 (문제/정답/헤더)
- NumberMarker: 번호 마커 (1., [1], ① 등)
- ProblemItem: 문제 항목
- SolutionItem: 정답 항목
- ExtractionResult: 추출 결과
- ValidProblem/ValidSolution: 유효성 증명
```

### 5. OutputFormat.idr - 출력 형식
```idris
- FileFormat: PNG, JPEG, PDF, SVG
- OutputType: ProblemFile (_prb), SolutionFile (_sol)
- OutputFile: 출력 파일 스펙
- OutputPackage: ZIP 패키지
- UniqueFilenames: 파일명 중복 방지 증명
```

### 6. Workflow.idr - 워크플로우
```idris
- WorkflowState: 워크플로우 상태
- WorkflowStep: 각 단계
- ValidTransition: 상태 전환 증명
- executePdfExtraction: 메인 함수 시그니처
```

## 🎯 설계 원칙 (cutting_pdf.md 기반)

### 요구사항
1. ✅ **메타데이터 파악**: 수학영역, 학교, 시험 종류 등
2. ✅ **수직선 감지**: 2단/3단 편집 판별
3. ✅ **레이아웃 감지**: 수직선 또는 여백 기반
4. ✅ **문제 번호 인식**: 1., 2. 형식
5. ✅ **정답 인식**: [정답] 키워드
6. ✅ **파일 출력**: 1_prb, 1_sol 형식
7. ✅ **ZIP 패키징**: 전체 결과물 압축

### 워크플로우
```
PDF 입력
  ↓
메타데이터 추출 (과목, 학교, 시험 종류)
  ↓
레이아웃 감지 (1단/2단/3단)
  ↓
수직선 감지 → 컬럼 경계 결정
  ↓
문제 영역 추출 (1., 2., ...)
  ↓
정답 영역 추출 ([정답], 번호)
  ↓
문제-정답 페어링
  ↓
개별 파일 생성 (PNG/JPEG/PDF)
  ↓
ZIP 패키징
```

## 🔍 증명 타입

이 프로젝트는 **Formal Specification Driven Development**를 따릅니다:

### 증명 1: NoOverlap
```idris
-- 문제들이 서로 겹치지 않음을 증명
NoOverlap : List BBox -> Type
```

### 증명 2: ValidLayout
```idris
-- 레이아웃이 올바른 컬럼 수와 겹치지 않는 컬럼을 가짐을 증명
ValidLayout : PageLayout -> Type
```

### 증명 3: ProblemsInOrder
```idris
-- 문제 번호가 오름차순임을 증명
ProblemsInOrder : List ProblemItem -> Type
```

### 증명 4: UniqueFilenames
```idris
-- 출력 파일명이 중복되지 않음을 증명
UniqueFilenames : List OutputFile -> Type
```

### 증명 5: CompleteOutput
```idris
-- 모든 문제와 정답에 대응하는 출력 파일이 존재함을 증명
CompleteOutput : ExtractionResult -> List OutputFile -> Type
```

## 🚀 사용 예정 방법 (Python 구현 후)

```bash
# 기본 사용
uv run python core/extract.py sample.pdf

# 출력 형식 지정
uv run python core/extract.py sample.pdf --format png

# 출력 디렉토리 지정
uv run python core/extract.py sample.pdf --output ./output

# 결과물
output/
├── sample_extracted.zip
└── sample_extracted/
    ├── 1_prb.png
    ├── 1_sol.png
    ├── 2_prb.png
    ├── 2_sol.png
    └── ...
```

## 📝 Idris2 명세 검증

모든 명세가 컴파일되는지 확인:

```bash
cd problem_cutter/.specs

# 개별 파일 확인
idris2 --check Base.idr               # ✅
idris2 --check PdfMetadata.idr        # ✅
idris2 --check LayoutDetection.idr    # ✅
idris2 --check ProblemExtraction.idr  # ✅
idris2 --check OutputFormat.idr       # ✅
idris2 --check Workflow.idr           # ✅
```

## 🔧 필요한 증명 (추후 구현 시)

Python 구현에서 다음 증명을 제공해야 합니다:

1. **NoOverlap 증명**: 문제 영역들이 겹치지 않음
2. **ValidLayout 증명**: 감지된 레이아웃이 유효함
3. **ValidColumnBounds 증명**: 컬럼 경계가 올바름
4. **ProblemsInOrder 증명**: 추출된 문제들이 순서대로 정렬됨
5. **UniqueFilenames 증명**: 출력 파일명이 중복되지 않음
6. **CompleteOutput 증명**: 모든 문제/정답이 출력됨

## 🎓 학습 가이드

### Idris2 명세 읽는 법

1. **데이터 타입**: `data`, `record` - 구조 정의
2. **타입 별칭**: `Type` - 간단한 타입 이름
3. **증명 타입**: `data ... : Type where` - 속성 증명
4. **함수 시그니처**: `->` - 입력과 출력 타입

### 예시
```idris
-- 레코드 정의
record BBox where
  constructor MkBBox
  topLeft : Coord
  width : Nat
  height : Nat

-- 증명 타입
data NoOverlap : List BBox -> Type where
  NoOverlapNil : NoOverlap []
  NoOverlapOne : (box : BBox) -> NoOverlap [box]
  NoOverlapCons : ...
```

## 📚 참고 자료

- [Idris2 공식 문서](https://idris2.readthedocs.io/)
- [Dependent Types 소개](https://en.wikipedia.org/wiki/Dependent_type)
- 원본 요구사항: `../direction/cutting_pdf.md`

## 🤝 기여

현재 명세 단계이므로 Python 구현이 필요합니다:
1. `core/` 디렉토리에 Python 모듈 작성
2. Idris2 명세를 참고하여 타입 안전한 구현
3. 테스트 작성

---

**현재 진행률**: 명세 설계 100% 완료 ✅ | Python 구현 0% 

**마지막 업데이트**: 2025-11-07

