# 다단 편집 분리 가이드

PDF 시험지의 다단(2단/3단) 편집을 개별 단으로 분리하는 방법을 설명합니다.

## 목차
- [기본 사용법](#기본-사용법)
- [주요 함수](#주요-함수)
- [분리 전략](#분리-전략)
- [실행 결과](#실행-결과)
- [고급 사용법](#고급-사용법)

---

## 기본 사용법

### 1. 가장 간단한 방법 (자동 감지)

```python
from core.column_separator import separate_columns

# 이미지 파일 또는 numpy array
result = separate_columns("test.png")

print(f"감지된 단 개수: {result.column_count}")
print(f"사용된 전략: {result.strategy.value}")

# 각 단을 파일로 저장
result.save_columns("output/columns", prefix="col")
# → output/columns/col_1.png, col_2.png, ...
```

### 2. 빠른 단 분리 + 저장

```python
from core.column_separator import split_and_save

# 한 번에 분리하고 저장
paths = split_and_save("test.png", "output", prefix="page1")
# → output/page1_1.png, output/page1_2.png
```

### 3. 단 개수만 확인

```python
from core.column_separator import get_column_count

count = get_column_count("test.png")
print(f"이 페이지는 {count}단입니다")
```

---

## 주요 함수

### `separate_columns(image, strategy=None, layout_detector=None)`

다단 편집 이미지를 자동으로 감지하여 단별로 분리합니다.

**매개변수:**
- `image`: 입력 이미지 (numpy array, 파일 경로, Path 객체)
- `strategy`: 분리 전략 (None이면 자동 선택)
- `layout_detector`: LayoutDetector 인스턴스 (None이면 기본 설정)

**반환값:** `SeparationResult` 객체

**예시:**
```python
result = separate_columns("test.png")

# 결과 정보
print(f"원본 크기: {result.original_width}x{result.original_height}")
print(f"단 개수: {result.column_count}")

# 각 단 접근
for col in result.columns:
    print(f"단 {col.index + 1}: {col.width}x{col.height}")
    print(f"  위치: x={col.left_x}~{col.right_x}")
```

### `separate_two_columns_simple(image, split_ratio=0.5)`

2단 편집을 단순하게 중앙선으로 분리합니다. (빠르고 안정적)

**매개변수:**
- `image`: 입력 이미지
- `split_ratio`: 분리 비율 (0.5 = 정중앙, 0.45 = 45:55)

**예시:**
```python
# 정중앙에서 분리 (50:50)
result = separate_two_columns_simple("test.png")

# 왼쪽이 약간 좁게 (45:55)
result = separate_two_columns_simple("test.png", split_ratio=0.45)
```

### `SeparationResult` 클래스

분리 결과를 담는 클래스입니다.

**주요 속성:**
- `original_width`, `original_height`: 원본 이미지 크기
- `column_count`: 분리된 단 개수
- `strategy`: 사용된 분리 전략
- `columns`: 단 정보 리스트 (`ColumnRegion` 객체)

**주요 메서드:**
- `save_columns(output_dir, prefix)`: 각 단을 파일로 저장
- `get_linearized_image()`: 모든 단을 세로로 연결하여 1단 이미지 생성

**예시:**
```python
result = separate_columns("test.png")

# 1. 각 단을 파일로 저장
paths = result.save_columns("output", prefix="col")

# 2. 1단으로 선형화
linear_image = result.get_linearized_image()
Image.fromarray(linear_image).save("output/linear.png")
```

---

## 분리 전략

### 1. 자동 감지 (Automatic)

```python
result = separate_columns("test.png")
# 전략: VERTICAL_LINES 또는 CONTENT_GAPS
```

**작동 방식:**
1. 먼저 수직선 감지 시도 (Hough Line Transform)
2. 수직선이 없으면 여백 기반 감지
3. 감지된 경계로 단 분리

**장점:** 다양한 레이아웃에 유연하게 대응
**단점:** 복잡한 레이아웃에서 오감지 가능

### 2. 고정 중앙선 (Fixed Midpoint)

```python
result = separate_two_columns_simple("test.png", split_ratio=0.5)
# 전략: FIXED_MIDPOINT
```

**작동 방식:**
- 페이지를 지정된 비율로 단순 분리
- 기본값 0.5 = 정중앙 (50:50)

**장점:** 빠르고 안정적, 항상 예측 가능
**단점:** 비대칭 레이아웃에는 부적합

### 전략 선택 가이드

| 상황 | 추천 전략 | 함수 |
|------|-----------|------|
| 확실한 2단 편집 (대칭) | 고정 중앙선 | `separate_two_columns_simple()` |
| 비대칭 또는 3단 편집 | 자동 감지 | `separate_columns()` |
| 레이아웃 불확실 | 자동 감지 | `separate_columns()` |

---

## 실행 결과

### 테스트 결과 (통합과학_1_샘플.pdf)

```
[2단계] 단 개수 감지
  감지된 단 개수: 2단

[3단계] 자동 단 분리
  전략: vertical_lines
  분리된 단 개수: 2

  각 단 정보:
    단 1:
      - 위치: x=0~1129
      - 크기: 1129x3309 (48.3%)
    단 2:
      - 위치: x=1129~2339
      - 크기: 1210x3309 (51.7%)

[6단계] 1단 선형화
  원본 높이: 3309px
  선형화 높이: 6618px (2.00x)
```

### 생성된 파일

```
output/column_test_통합과학/
├── 00_original.png     # 원본 (815KB)
├── auto_1.png          # 자동 감지 - 왼쪽 단 (424KB)
├── auto_2.png          # 자동 감지 - 오른쪽 단 (381KB)
├── simple_1.png        # 단순 분리 - 왼쪽 단 (427KB)
├── simple_2.png        # 단순 분리 - 오른쪽 단 (378KB)
└── linearized.png      # 선형화 (807KB)
```

---

## 고급 사용법

### 1. 좁은 단 병합

잘못 감지된 좁은 단(여백, 페이지 번호 등)을 제거합니다.

```python
from core.column_separator import separate_columns, merge_narrow_columns

result = separate_columns("test.png")
print(f"병합 전: {result.column_count}단")

# 전체 너비의 15% 미만인 단을 병합
merged = merge_narrow_columns(result, min_width_ratio=0.15)
print(f"병합 후: {merged.column_count}단")
```

### 2. 선형화 (다단 → 1단)

다단 편집을 1단으로 변환하여 세로 추적을 용이하게 합니다.

```python
from core.column_separator import split_to_linear
from PIL import Image

# 한 번에 선형화
linear_image = split_to_linear("test.png")

# 저장
Image.fromarray(linear_image).save("output/linear.png")
```

**용도:**
- 문제 번호 세로 추적 (1., 2., 3. ...)
- 연속된 영역 감지
- 단 구조 무시하고 순차 처리

### 3. 커스텀 LayoutDetector 사용

감지 파라미터를 조정하여 정확도를 높일 수 있습니다.

```python
from core.layout_detector import LayoutDetector
from core.column_separator import separate_columns

# 커스텀 설정
detector = LayoutDetector(
    min_line_length=200,           # 최소 수직선 길이
    line_thickness_threshold=5,    # 수직선 두께 허용 오차
    gap_threshold=50               # 최소 여백 너비
)

result = separate_columns("test.png", layout_detector=detector)
```

### 4. 분리 결과 검증

```python
result = separate_columns("test.png")

# 각 단의 너비 비율 확인
for col in result.columns:
    ratio = col.width / result.original_width
    print(f"단 {col.index + 1}: {ratio * 100:.1f}%")

    # 비정상적으로 좁은 단 경고
    if ratio < 0.2:
        print(f"  ⚠️ 경고: 단이 너무 좁습니다 ({col.width}px)")
```

### 5. PDF에서 직접 처리

```python
from core.pdf_converter import pdf_to_images
from core.column_separator import separate_columns

# PDF → 이미지 변환
images = pdf_to_images("test.pdf", dpi=200)

# 각 페이지 처리
for i, page_img in enumerate(images):
    result = separate_columns(page_img)
    result.save_columns(f"output/page{i+1}", prefix="col")
```

---

## 문제 해결

### Q: 단이 제대로 감지되지 않아요

**A:** 여러 전략을 시도해보세요.

```python
# 1. 자동 감지
result1 = separate_columns("test.png")

# 2. 단순 중앙 분리
result2 = separate_two_columns_simple("test.png")

# 3. 비율 조정
result3 = separate_two_columns_simple("test.png", split_ratio=0.45)

# 결과 비교
for i, r in enumerate([result1, result2, result3], 1):
    print(f"전략 {i}: {r.column_count}단, {r.strategy.value}")
```

### Q: 3단 편집이 잘 안 돼요

**A:** LayoutDetector 파라미터를 조정하세요.

```python
from core.layout_detector import LayoutDetector

# 더 민감하게 감지
detector = LayoutDetector(
    min_line_length=150,   # 짧은 수직선도 감지
    gap_threshold=30       # 작은 여백도 감지
)

result = separate_columns("test.png", layout_detector=detector)
```

### Q: 여백이나 페이지 번호가 별도 단으로 잡혀요

**A:** `merge_narrow_columns()`로 좁은 단을 병합하세요.

```python
from core.column_separator import merge_narrow_columns

result = separate_columns("test.png")
merged = merge_narrow_columns(result, min_width_ratio=0.15)
```

---

## 참고 자료

- **명세:** `.specs/System/LayoutDetection.idr`
- **구현:** `core/column_separator.py`
- **테스트:** `tests/test_column_separator.py`
- **예제:** `examples/separate_columns_demo.py`
- **실전:** `test_column_separation_samples.py`

---

**최종 업데이트:** 2025-11-08
