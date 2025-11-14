# OpenCV를 이용한 PDF 레이아웃 분석 가이드

## 🎯 개요

이 프로젝트는 **OpenCV**를 사용하여 PDF 시험지의 레이아웃을 자동으로 분석합니다.

### 주요 기능
1. ✅ **수직선 감지** - Hough Line Transform 사용
2. ✅ **컬럼 경계 감지** - 1단/2단/3단 자동 판별
3. ✅ **여백 분석** - 수직선이 없을 때 whitespace 분석
4. ✅ **시각화** - 감지 결과 시각화

## 📦 설치

### 1. 의존성 설치

```bash
cd problem_cutter

# OpenCV 및 필수 라이브러리
pip install -r requirements.txt

# 또는 개별 설치
pip install opencv-python numpy
pip install PyMuPDF  # PDF 변환용 (추천)
# 또는
pip install pdf2image  # 대안
```

### 2. macOS에서 poppler 설치 (pdf2image 사용 시)
```bash
brew install poppler
```

## 🚀 사용 방법

### 기본 사용

```bash
# 예제 실행
python examples/detect_layout.py samples/sample.pdf

# 결과: output_page_1.jpg, output_page_2.jpg 등 생성
```

### Python 코드에서 사용

```python
from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector

# 1. PDF를 이미지로 변환
images = pdf_to_images("sample.pdf", dpi=200)

# 2. 레이아웃 감지기 생성
detector = LayoutDetector(
    min_line_length=100,      # 최소 선 길이
    line_thickness_threshold=5,  # 선 두께 임계값
    gap_threshold=50          # 여백 임계값
)

# 3. 레이아웃 감지
for page_num, image in enumerate(images):
    layout = detector.detect_layout(image)
    
    print(f"페이지 {page_num + 1}:")
    print(f"  컬럼 수: {layout.column_count.value}")
    print(f"  감지 방법: {layout.detection_method.value}")
    
    # 컬럼 정보
    for i, col in enumerate(layout.columns):
        print(f"  컬럼 {i+1}: x=[{col.left_x}, {col.right_x}]")
    
    # 시각화
    vis = detector.visualize_layout(image, layout)
    cv2.imwrite(f"output_{page_num}.jpg", vis)
```

## 🔍 OpenCV 기법 설명

### 1. 수직선 감지 (Vertical Line Detection)

```python
def _detect_vertical_lines(self, gray):
    # 1. Canny Edge Detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # 2. Hough Line Transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,              # 거리 해상도 (픽셀)
        theta=np.pi/180,    # 각도 해상도 (라디안)
        threshold=100,      # 임계값
        minLineLength=100,  # 최소 선 길이
        maxLineGap=20       # 최대 간격
    )
    
    # 3. 수직선 필터링 (x 좌표 변화가 작은 선)
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) <= 5:  # 거의 수직
            # 수직선으로 인정
```

**작동 원리:**
- Canny로 엣지 감지 → 선 후보 찾기
- Hough Transform으로 직선 검출
- x 좌표 변화가 작으면 수직선으로 판단

### 2. 여백 분석 (Content Gap Analysis)

```python
def _layout_from_gaps(self, gray, width, height):
    # 1. 이진화
    _, binary = cv2.threshold(
        gray, 0, 255, 
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    
    # 2. 수직 투영 (Vertical Projection)
    v_projection = np.sum(binary, axis=0)
    # → 각 x 좌표에서 픽셀의 합 계산
    #    컨텐츠가 많으면 값이 크고, 여백이면 작음
    
    # 3. 평활화 (Smoothing)
    v_projection_smooth = cv2.GaussianBlur(
        v_projection.astype(np.float32),
        (kernel_size, 1), 0
    )
    
    # 4. 로컬 미니마 찾기 (여백 위치)
    gaps = self._find_gaps(v_projection_smooth)
```

**수직 투영 예시:**
```
픽셀 합
  |
  |  ██     ██      ██
  |  ██     ██      ██
  |  ██  ░  ██  ░░  ██
  |  ██     ██      ██
  +-------------------> x 좌표
     컬럼1  여백  컬럼2
           ↑
         여기가 경계!
```

### 3. 선 병합 (Line Merging)

```python
def _merge_nearby_vlines(self, vlines, threshold=10):
    # 가까운 수직선들을 하나로 병합
    # 예: x=100, x=105 → x=102 (평균)
    
    vlines = sorted(vlines, key=lambda vl: vl.x)
    merged = [vlines[0]]
    
    for vl in vlines[1:]:
        if abs(vl.x - merged[-1].x) <= threshold:
            # 병합: 평균 x, y 범위 확장
            merged[-1] = VLine(
                (merged[-1].x + vl.x) // 2,
                min(merged[-1].y_start, vl.y_start),
                max(merged[-1].y_end, vl.y_end)
            )
        else:
            merged.append(vl)
```

## 📊 감지 알고리즘 흐름도

```
PDF 입력
  ↓
[pdf_to_images] PDF → 이미지 변환 (300 DPI)
  ↓
[detect_layout] 레이아웃 분석 시작
  ↓
├─→ [_detect_vertical_lines] 수직선 감지 시도
│     ├─ Canny Edge Detection
│     ├─ Hough Line Transform
│     ├─ 수직선 필터링 (각도 확인)
│     └─ 선 병합
│
├─→ 수직선 발견?
│   YES → [_layout_from_vlines] 선 기반 컬럼 결정
│   │       ├─ 0개 → 1단
│   │       ├─ 1개 → 2단
│   │       └─ 2개 → 3단
│   │
│   NO  → [_layout_from_gaps] 여백 기반 컬럼 결정
│           ├─ 이진화 (Otsu)
│           ├─ 수직 투영
│           ├─ 평활화 (Gaussian Blur)
│           ├─ 로컬 미니마 찾기
│           └─ 컬럼 경계 결정
│
└─→ PageLayout 반환
      ├─ column_count: 1/2/3
      ├─ detection_method: VERTICAL_LINES / CONTENT_GAPS
      ├─ columns: [ColumnBound, ...]
      └─ separator_lines: [VLine, ...]
```

## 🎨 시각화 예시

### 감지 결과

```python
vis = detector.visualize_layout(image, layout)
cv2.imshow("Layout", vis)
```

**시각화 요소:**
- 🔴 **빨간 선**: 감지된 수직 구분선
- 🟢 **녹색 선**: 컬럼 경계
- 📝 **텍스트**: 감지 방법 및 컬럼 수

### 출력 예시
```
Method: vertical_lines
Columns: 2

|<-- 컬럼 1 -->|<-- 컬럼 2 -->|
|             🔴              |
|    문항 1    |    문항 3    |
|    문항 2    |    문항 4    |
|             🔴              |
```

## 🔧 파라미터 튜닝

### LayoutDetector 파라미터

| 파라미터 | 기본값 | 설명 | 조정 가이드 |
|---------|--------|------|------------|
| `min_line_length` | 100 | 최소 선 길이 (픽셀) | 작은 PDF: 50, 큰 PDF: 150 |
| `line_thickness_threshold` | 5 | 선 두께 임계값 | 굵은 선: 10, 얇은 선: 3 |
| `gap_threshold` | 50 | 여백 폭 임계값 | 좁은 여백: 30, 넓은 여백: 80 |

### DPI 설정

| DPI | 용도 | 속도 | 품질 |
|-----|------|------|------|
| 150 | 빠른 테스트 | ⚡⚡⚡ | ⭐⭐ |
| 200 | 일반 처리 | ⚡⚡ | ⭐⭐⭐ |
| 300 | 고품질 | ⚡ | ⭐⭐⭐⭐⭐ |

```python
# 빠른 테스트
images = pdf_to_images(pdf_path, dpi=150)

# 프로덕션
images = pdf_to_images(pdf_path, dpi=300)
```

## 📈 성능 최적화

### 1. 이미지 크기 조정
```python
# 큰 이미지는 리사이즈
def resize_if_large(image, max_width=2000):
    h, w = image.shape[:2]
    if w > max_width:
        scale = max_width / w
        new_h = int(h * scale)
        return cv2.resize(image, (max_width, new_h))
    return image
```

### 2. 그레이스케일 사용
```python
# 컬러 불필요하면 그레이스케일로 처리
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
layout = detector.detect_layout(gray)
```

### 3. ROI (Region of Interest) 사용
```python
# 상단 헤더 제외하고 분석
header_height = 100
roi = image[header_height:, :]
layout = detector.detect_layout(roi)
```

## 🐛 트러블슈팅

### 문제 1: 수직선을 못 찾음
**원인:** 선이 너무 흐리거나 짧음

**해결:**
```python
detector = LayoutDetector(
    min_line_length=50,  # 더 짧은 선도 허용
    line_thickness_threshold=10  # 더 두꺼운 선도 허용
)
```

### 문제 2: 여백을 잘못 감지
**원인:** 이미지에 노이즈가 많음

**해결:**
```python
# 전처리 추가
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
denoised = cv2.fastNlMeansDenoising(gray)
layout = detector.detect_layout(denoised)
```

### 문제 3: 컬럼 수가 잘못됨
**원인:** 3단을 2단으로 오인

**해결:**
```python
# gap_threshold 감소 (더 좁은 여백도 감지)
detector = LayoutDetector(gap_threshold=30)
```

## 📚 Idris2 명세와의 대응

| Idris2 타입 | Python 클래스 | OpenCV 기능 |
|------------|--------------|------------|
| `Coord` | `Coord` | `(x, y)` 튜플 |
| `BBox` | `BBox` | `cv2.boundingRect()` |
| `VLine` | `VLine` | `cv2.HoughLinesP()` |
| `ColumnBound` | `ColumnBound` | 수직 투영 분석 |
| `PageLayout` | `PageLayout` | 전체 레이아웃 |

## 🎓 다음 단계

1. ✅ 레이아웃 감지 (완료)
2. ⏳ 문제 번호 인식 (OCR)
3. ⏳ 텍스트 영역 추출
4. ⏳ 이미지 영역 추출
5. ⏳ 문제/정답 매칭

---

**관련 파일:**
- `core/layout_detector.py` - 메인 구현
- `core/base.py` - 기본 타입
- `core/pdf_converter.py` - PDF 변환
- `examples/detect_layout.py` - 사용 예제

**참고 자료:**
- [OpenCV Hough Line Transform](https://docs.opencv.org/4.x/d9/db0/tutorial_hough_lines.html)
- [OpenCV Canny Edge Detection](https://docs.opencv.org/4.x/da/d22/tutorial_py_canny.html)


