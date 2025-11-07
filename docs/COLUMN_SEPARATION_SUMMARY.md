# 다단 편집 분리 기능 완성 요약

## 📦 생성된 파일들

### 핵심 모듈
- **`core/column_separator.py`** (530줄)
  - 다단 편집 자동 감지 및 분리
  - 3가지 분리 전략 지원
  - 선형화 (다단 → 1단) 기능
  - 좁은 단 병합 기능

### 테스트 및 예제
- **`tests/test_column_separator.py`** (290줄)
  - 34개 pytest 테스트 케이스
  - 1단/2단/3단 이미지 fixture
  - 엣지 케이스 처리 검증

- **`examples/separate_columns_demo.py`** (330줄)
  - 5가지 데모 시나리오
  - 테스트 이미지 자동 생성
  - 실행 가능한 예제 코드

- **`test_column_separation_samples.py`** (230줄)
  - 실제 샘플 PDF 테스트
  - 전략 비교 (자동/중앙/비율)
  - 시각적 결과 확인 가능

### 문서
- **`docs/COLUMN_SEPARATION_GUIDE.md`**
  - 완전한 사용 가이드
  - API 레퍼런스
  - 문제 해결 FAQ

---

## ✨ 주요 기능

### 1. 자동 단 감지 및 분리
```python
from core.column_separator import separate_columns

result = separate_columns("test.png")
# → 자동으로 1단/2단/3단 감지
# → 수직선 또는 여백 기반 분리
```

### 2. 간단한 2단 분리
```python
from core.column_separator import separate_two_columns_simple

result = separate_two_columns_simple("test.png")
# → 정중앙에서 빠르게 분리 (50:50)
# → 비율 조정 가능 (예: 45:55)
```

### 3. 선형화 (다단 → 1단)
```python
result = separate_columns("test.png")
linear_image = result.get_linearized_image()
# → 모든 단을 세로로 연결
# → 문제 번호 추적에 유용
```

### 4. 좁은 단 병합
```python
from core.column_separator import merge_narrow_columns

merged = merge_narrow_columns(result, min_width_ratio=0.15)
# → 너무 좁은 단(여백, 페이지 번호) 제거
```

---

## 🧪 테스트 결과

### 샘플 파일 테스트 (통합과학_1_샘플.pdf)

```
✅ PDF → 이미지 변환: 성공 (2339x3309px)
✅ 단 개수 감지: 2단
✅ 자동 분리: 성공
   - 전략: vertical_lines (수직선 기반)
   - 단 1: 1129px (48.3%)
   - 단 2: 1210px (51.7%)
✅ 선형화: 3309px → 6618px (2.00x)
```

### 생성된 결과 파일

```
output/column_test_통합과학/
├── 00_original.png     # 원본
├── auto_1.png          # 자동 감지 - 왼쪽 단
├── auto_2.png          # 자동 감지 - 오른쪽 단
├── simple_1.png        # 단순 분리 - 왼쪽 단
├── simple_2.png        # 단순 분리 - 오른쪽 단
└── linearized.png      # 선형화 (1단)

output/column_comparison/
├── strategy1_auto_1.png      # 자동 감지
├── strategy1_auto_2.png
├── strategy2_mid50_1.png     # 중앙선 50%
├── strategy2_mid50_2.png
├── strategy3_45-55_1.png     # 비율 45:55
└── strategy3_45-55_2.png
```

---

## 🎯 분리 전략 비교

| 전략 | 장점 | 단점 | 용도 |
|------|------|------|------|
| **자동 감지** | 유연함, 다양한 레이아웃 대응 | 복잡한 경우 오감지 가능 | 범용 |
| **고정 중앙선** | 빠름, 안정적, 예측 가능 | 비대칭 레이아웃 부적합 | 확실한 2단 |
| **비율 조정** | 비대칭 대응, 커스텀 가능 | 수동 조정 필요 | 특정 레이아웃 |

### 테스트 결과 비교 (통합과학_1_샘플.pdf)

```
자동 감지:   왼쪽 1129px (48.3%) | 오른쪽 1210px (51.7%)
중앙선 50%:  왼쪽 1169px (50.0%) | 오른쪽 1170px (50.0%)
비율 45%:    왼쪽 1052px (45.0%) | 오른쪽 1287px (55.0%)
```

---

## 💡 사용 예시

### 기본 사용
```python
from core.column_separator import separate_columns

# 1. 자동 감지 및 분리
result = separate_columns("test.png")

# 2. 결과 확인
print(f"단 개수: {result.column_count}")
print(f"전략: {result.strategy.value}")

# 3. 각 단 저장
result.save_columns("output", prefix="col")
```

### PDF 처리 파이프라인
```python
from core.pdf_converter import pdf_to_images
from core.column_separator import separate_columns

# 1. PDF → 이미지
images = pdf_to_images("test.pdf", dpi=200)

# 2. 각 페이지 처리
for i, page_img in enumerate(images):
    # 단 분리
    result = separate_columns(page_img)

    # 선형화 (문제 추적용)
    linear = result.get_linearized_image()

    # 저장
    result.save_columns(f"output/page{i+1}")
```

### 전략 비교 및 선택
```python
from core.column_separator import (
    separate_columns,
    separate_two_columns_simple
)

# 여러 전략 시도
results = []
results.append(separate_columns("test.png"))
results.append(separate_two_columns_simple("test.png", 0.5))
results.append(separate_two_columns_simple("test.png", 0.45))

# 결과 비교
for i, r in enumerate(results, 1):
    print(f"전략 {i}: {r.column_count}단")
    for col in r.columns:
        ratio = col.width / r.original_width
        print(f"  단 {col.index+1}: {ratio*100:.1f}%")
```

---

## 📊 성능 측정

### 처리 속도 (테스트 환경: MacBook, Python 3.10)

```
PDF → 이미지 (200 DPI):  ~1초
단 개수 감지:            ~0.1초
자동 분리:              ~0.2초
단순 분리:              ~0.01초 (20배 빠름)
선형화:                 ~0.05초

전체 파이프라인:         ~1.5초/페이지
```

### 메모리 사용

```
원본 이미지 (2339x3309): ~23MB (RGB)
각 단 이미지:           ~11-12MB
선형화 이미지:          ~23MB
```

---

## 🔧 기술 구현

### 1. 수직선 기반 감지
- OpenCV Hough Line Transform 사용
- Canny 엣지 검출
- 페이지 높이의 1/3 이상인 수직선만 인식

### 2. 여백 기반 감지
- 수직 프로젝션 (vertical projection)
- 픽셀 밀도 분석
- 평균 대비 30% 이하 밀도 → 여백으로 판단

### 3. 선형화 알고리즘
- 모든 단을 동일 너비로 패딩
- 흰색(255)으로 빈 공간 채움
- numpy vstack으로 세로 연결

### 4. 좁은 단 병합
- 전체 너비 대비 비율 계산
- 최소 너비 미달 시 인접 단과 병합
- 재귀적 병합 (여러 좁은 단 처리)

---

## 🏗️ 아키텍처

```
column_separator.py
├── separate_columns()           # 메인 함수 (자동 감지)
├── separate_two_columns_simple() # 단순 분리
├── merge_narrow_columns()        # 좁은 단 병합
├── get_column_count()            # 단 개수만 확인
├── split_and_save()              # 분리 + 저장
└── split_to_linear()             # 분리 + 선형화

SeparationResult
├── original_width, original_height
├── column_count
├── strategy
├── columns: List[ColumnRegion]
├── save_columns()                # 파일 저장
└── get_linearized_image()        # 선형화

ColumnRegion
├── index
├── left_x, right_x
├── width, height
├── image
└── to_dict()
```

---

## ✅ 완성도 체크리스트

- [x] 자동 단 감지 (수직선 + 여백)
- [x] 1단/2단/3단 지원
- [x] 단순 중앙 분리 (고속)
- [x] 비율 기반 분리
- [x] 선형화 (다단 → 1단)
- [x] 좁은 단 병합
- [x] 파일 저장 기능
- [x] PDF 처리 통합
- [x] 단위 테스트 (34개)
- [x] 실전 테스트 (샘플 PDF)
- [x] 사용 가이드 문서
- [x] API 레퍼런스
- [x] 예제 코드
- [x] 문제 해결 FAQ

---

## 🚀 다음 단계 제안

### 1. 문제 영역 추출 통합
```python
# column_separator와 problem_extractor 연결
from core.column_separator import separate_columns
from core.problem_extractor import extract_problems

result = separate_columns("test.png")
linear = result.get_linearized_image()

# 선형화된 이미지에서 문제 추출
problems = extract_problems(linear)
```

### 2. 전체 워크플로우 통합
```python
# PDF → 단 분리 → 문제 추출 → 파일 생성
from core.workflow import execute_pdf_extraction

execute_pdf_extraction(
    pdf_path="test.pdf",
    separate_columns=True,  # 단 분리 활성화
    linearize=True          # 선형화 활성화
)
```

### 3. Agent 통합
```python
# AgentTools에 단 분리 기능 추가
from AgentTools import workflow

result = workflow.separate_and_extract(
    pdf_path="test.pdf",
    strategy="auto"  # 또는 "simple", "custom"
)
```

---

## 📝 커밋 메시지 제안

```
feat: 다단 편집 분리 기능 구현

- core/column_separator.py: 자동 감지 및 3가지 분리 전략
- tests/test_column_separator.py: 34개 테스트 케이스
- examples/separate_columns_demo.py: 5가지 데모 시나리오
- test_column_separation_samples.py: 실제 샘플 테스트
- docs/COLUMN_SEPARATION_GUIDE.md: 완전한 사용 가이드

주요 기능:
- 자동 단 감지 (수직선/여백 기반)
- 단순 중앙 분리 (고속, 안정)
- 선형화 (다단 → 1단)
- 좁은 단 병합
- PDF 처리 파이프라인 통합

테스트 결과:
- 통합과학_1_샘플.pdf: ✅ 2단 정확히 분리
- 고3_사회탐구_사회문화_1p.pdf: ✅ 2단 정확히 분리
- 34개 단위 테스트: ✅ 모두 통과
```

---

**작성일:** 2025-11-08
**테스트 환경:** Python 3.10+, OpenCV 4.8+
**샘플 파일:** 통합과학_1_샘플.pdf, 고3_사회탐구_사회문화_1p.pdf
