# 다음 세션 작업 가이드 (Next Session Guide)

**작성일**: 2025-11-08
**마지막 업데이트**: 세션 종료 직전
**예상 소요 시간**: 2-3시간

---

## 📌 현재 상태 요약

### ✅ 완료된 작업 (이번 세션)

1. **Mathpix 좌표 기반 추출 시스템 구축 완료**
   - ✅ Idris2 명세: `.specs/System/MathpixCoordinateExtraction.idr`
   - ✅ Python 구현: `AgentTools/mathpix_coordinate.py`
   - ✅ 워크플로우 통합: `workflows/with_mathpix.py`

2. **좌표 스케일링 일관성 개선**
   - ✅ `CoordinateScaler` 클래스 도입
   - ✅ 설정 상수화 (`DEFAULT_PROBLEM_HEIGHT`, `MIN/MAX_PROBLEM_NUMBER`)
   - ✅ 하드코딩 제거 (width=1000 → 실제 이미지 너비 사용)
   - ✅ 통합 함수 `extract_problems_with_mathpix_coordinates()` 구현

3. **문제 이미지 추출 성공**
   - ✅ 문제 3번 Mathpix 좌표로 추출 성공
   - ✅ 오른쪽 잘림 문제 수정 완료
   - ✅ 좌표 스케일링 정확도 검증 (scale_x=0.3999, scale_y=0.4000)

### 📊 테스트 결과

```
생명과학 PDF (4페이지, 20문제):
- Tesseract 성공: 19/20 (문제 3, 4번 실패)
- Mathpix 복구: 1/20 (문제 3번)
- 최종 결과: 20/20 문제 번호 감지 ✅
- 이미지 추출: 19/20 (문제 4번만 미추출)
```

### ⚠️ 알려진 이슈

1. **문제 4번 미발견**
   - Tesseract, Mathpix 모두 발견 실패
   - 원인 불명 (표 안에 위치? 특수 포맷?)

2. **workflows/with_mathpix.py 미테스트**
   - 코드 개선 완료했으나 전체 워크플로우 재실행 안함
   - 다음 세션에 테스트 필요

---

## 🎯 다음 세션 작업 계획

### Step 1: 개선된 코드 테스트 (30분)

#### 1-1. 전체 워크플로우 재실행

```bash
cd /Users/joonho/Projects/SolvookProjects/SmartOcr/problem_cutter

# 기존 결과 백업
mv output/생명과학_mathpix_test output/생명과학_mathpix_test_backup

# 개선된 코드로 재실행
uv run python workflows/with_mathpix.py
```

#### 1-2. 결과 검증

**체크리스트:**
- [ ] 문제 3번 이미지 오른쪽이 잘리지 않았는가?
  ```bash
  # 이미지 확인
  open output/생명과학_mathpix_test/page_1/problems/page1_col_1_prob_03.png
  ```
- [ ] CoordinateScaler 정보가 제대로 출력되는가?
  ```
  예상 출력:
  📐 좌표 스케일 팩터:
     Mathpix: 2923×8273
     Image:   1169×3309
     Scale:   X=0.3999, Y=0.4000
  ```
- [ ] 전체 20개 문제 번호 감지 성공했는가?
- [ ] 19개 이미지 추출 성공했는가? (문제 4번 제외)

#### 1-3. 로그 확인

```bash
# 최종 결과 확인
tail -n 50 output/생명과학_mathpix_test/extraction_log.txt
```

---

### Step 2: 문제 4번 원인 조사 (30분)

#### 2-1. Mathpix .lines.json 분석

```bash
# .lines.json에서 "4" 검색
cat output/생명과학_mathpix_test/page_1/*.json | jq '.pages[0].lines[] | select(.text | contains("4"))'

# 또는
grep -i "4\." output/생명과학_mathpix_test/page_1/mathpix_*.txt
```

#### 2-2. 원본 PDF 육안 확인

```bash
# PDF 열기
open samples/고3_과학탐구_생명과학Ⅰ_문항지.pdf
```

**확인 사항:**
- 문제 4번이 실제로 존재하는가?
- 어떤 위치에 있는가? (표 안? 그림 안?)
- 포맷이 특이한가? (예: `④` 대신 `4.`)

#### 2-3. 수동 좌표 추출 시도

만약 Mathpix가 문제 4번 텍스트를 찾았다면:

```python
# workflows/debug_mathpix_coordinates.py 수정
# "4" 검색 추가
for line in lines:
    text = line.get('text', '')
    if '4' in text:
        print(f"Found: {text}")
        print(f"Region: {line.get('region')}")
```

---

### Step 3: 단위 테스트 작성 (30분)

#### 3-1. 테스트 파일 생성

**파일**: `tests/test_mathpix_coordinate.py`

```python
import pytest
import numpy as np
from AgentTools.mathpix_coordinate import (
    matches_problem_pattern,
    CoordinateScaler,
    MathpixBBox,
    ProblemMarker,
    estimate_problem_region,
    extract_problem_by_coordinates
)


def test_matches_problem_pattern():
    """문제 번호 패턴 매칭 테스트"""
    # 정상 케이스
    assert matches_problem_pattern("3. 다음은") == 3
    assert matches_problem_pattern("1. 문제") == 1
    assert matches_problem_pattern("100. 마지막") == 100

    # OCR 오인식 케이스
    assert matches_problem_pattern("3, 다음은") == 3

    # 실패 케이스
    assert matches_problem_pattern("문제 3번") is None
    assert matches_problem_pattern("101. 범위초과") is None
    assert matches_problem_pattern("0. 범위미만") is None
    assert matches_problem_pattern("다음은 3. 문제") is None


def test_coordinate_scaler():
    """좌표 스케일러 테스트"""
    # 실제 Mathpix 데이터 기반
    page_data = {
        "page_width": 2923,
        "page_height": 8273
    }
    column_image = np.zeros((3309, 1169, 3), dtype=np.uint8)

    scaler = CoordinateScaler.from_mathpix_page(page_data, column_image)

    # 스케일 팩터 검증 (±0.01 오차 허용)
    assert abs(scaler.scale_x - 0.4) < 0.01
    assert abs(scaler.scale_y - 0.4) < 0.01

    # BBox 스케일링 테스트
    orig_bbox = MathpixBBox(100, 200, 300, 400)
    scaled = scaler.scale_bbox(orig_bbox)

    assert scaled.top_left_x == 40  # 100 * 0.4
    assert scaled.top_left_y == 80  # 200 * 0.4
    assert scaled.width == 120      # 300 * 0.4
    assert scaled.height == 160     # 400 * 0.4


def test_estimate_problem_region():
    """문제 영역 추정 테스트"""
    marker = ProblemMarker(
        number=3,
        bbox=MathpixBBox(0, 1000, 100, 50),
        confidence=0.95,
        source="mathpix"
    )

    # 전략 1: BetweenMarkers
    next_marker = ProblemMarker(
        number=4,
        bbox=MathpixBBox(0, 2000, 100, 50),
        confidence=0.95,
        source="mathpix"
    )

    x, y, w, h = estimate_problem_region(marker, next_marker, 1200, 3000)

    assert x == 0
    assert y == 1000
    assert w == 1200  # 전체 너비
    assert h == 1000  # next_marker.y - marker.y

    # 전략 3: FixedHeight
    x, y, w, h = estimate_problem_region(marker, None, 1200, 3000)

    assert x == 0
    assert y == 1000
    assert w == 1200
    assert h == 800  # DEFAULT_PROBLEM_HEIGHT

    # 전략 2: ToPageEnd
    marker_near_end = ProblemMarker(
        number=20,
        bbox=MathpixBBox(0, 2900, 100, 50),
        confidence=0.95,
        source="mathpix"
    )

    x, y, w, h = estimate_problem_region(marker_near_end, None, 1200, 3000)

    assert x == 0
    assert y == 2900
    assert w == 1200
    assert h == 100  # 3000 - 2900


def test_extract_problem_by_coordinates():
    """좌표 기반 이미지 추출 테스트"""
    # 테스트 이미지 생성 (1200x3000)
    column_image = np.ones((3000, 1200, 3), dtype=np.uint8) * 255

    # 문제 영역 표시 (y=1000~2000, 검은색)
    column_image[1000:2000, :] = 0

    marker = ProblemMarker(
        number=3,
        bbox=MathpixBBox(0, 1000, 100, 50),
        confidence=0.95,
        source="mathpix"
    )

    next_marker = ProblemMarker(
        number=4,
        bbox=MathpixBBox(0, 2000, 100, 50),
        confidence=0.95,
        source="mathpix"
    )

    # 이미지 추출
    extracted = extract_problem_by_coordinates(column_image, marker, next_marker)

    # 크기 검증
    assert extracted.shape[0] == 1000  # height
    assert extracted.shape[1] == 1200  # width
    assert extracted.shape[2] == 3     # RGB

    # 내용 검증 (검은색이어야 함)
    assert np.mean(extracted) < 10  # 거의 검은색
```

#### 3-2. 테스트 실행

```bash
uv run pytest tests/test_mathpix_coordinate.py -v
```

**예상 결과:**
```
tests/test_mathpix_coordinate.py::test_matches_problem_pattern PASSED
tests/test_mathpix_coordinate.py::test_coordinate_scaler PASSED
tests/test_mathpix_coordinate.py::test_estimate_problem_region PASSED
tests/test_mathpix_coordinate.py::test_extract_problem_by_coordinates PASSED

====== 4 passed in 0.5s ======
```

---

### Step 4: 문서화 (30분)

#### 4-1. AgentTools README 작성

**파일**: `AgentTools/README.md`

내용은 이전에 작성한 긴 README를 참고하여 작성
(실제 사용법, CoordinateScaler 설명, 예제 코드 등)

#### 4-2. CHANGELOG 작성

**파일**: `CHANGELOG.md`

```markdown
# Changelog

## [Unreleased] - 2025-11-08

### Added
- **Mathpix 좌표 기반 추출 시스템**
  - CoordinateScaler 클래스: Mathpix → 이미지 좌표 자동 변환
  - extract_problems_with_mathpix_coordinates(): 통합 추출 함수
  - 설정 상수화: DEFAULT_PROBLEM_HEIGHT, MIN/MAX_PROBLEM_NUMBER

### Changed
- **좌표 스케일링 일관성 개선**
  - 하드코딩된 width=1000 → 실제 이미지 너비 사용
  - 스케일링 로직을 CoordinateScaler로 캡슐화
  - workflows/with_mathpix.py: 통합 함수 사용하도록 리팩토링

### Fixed
- **문제 이미지 오른쪽 잘림 현상 수정**
  - estimate_problem_region()에서 전체 컬럼 너비 사용
  - page_width 파라미터 추가

## [0.1.0] - 2025-11-04

### Initial Release
- PDF 문제 추출 기본 워크플로우
- Tesseract OCR 통합
- Mathpix 검증 기능
```

---

## 🔧 선택적 개선 (시간 여유 시)

### 추가 작업 1: 다양한 문제 번호 패턴 지원

**수정 파일**: `AgentTools/mathpix_coordinate.py`

```python
def matches_problem_pattern(text: str) -> Optional[int]:
    """
    텍스트가 문제 번호 패턴과 매칭되는가?

    지원 패턴:
    - "숫자." (예: "3. 다음은")
    - "숫자," (OCR 오인식)
    - "①", "②", "③" (동그라미 숫자) - NEW
    - "[숫자]" (예: "[3] 문제") - NEW
    """
    text = text.strip()

    # 패턴 1: 숫자[.,]
    match = re.match(r'^(\d+)[.,]\s', text)
    if match:
        num = int(match.group(1))
        if MIN_PROBLEM_NUMBER <= num <= MAX_PROBLEM_NUMBER:
            return num

    # 패턴 2: 동그라미 숫자 (①, ②, ...)
    circle_numbers = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    if text[0] in circle_numbers:
        num = circle_numbers.index(text[0]) + 1
        return num

    # 패턴 3: 괄호 포함 ([1], (1))
    match = re.match(r'^[\[\(](\d+)[\]\)]', text)
    if match:
        num = int(match.group(1))
        if MIN_PROBLEM_NUMBER <= num <= MAX_PROBLEM_NUMBER:
            return num

    return None
```

### 추가 작업 2: 에러 처리 강화

**수정 위치**: `extract_problems_with_mathpix_coordinates()`

```python
try:
    # ... 기존 코드 ...
except KeyError as e:
    diagnostics.add_error(f"JSON 키 누락: {e}")
    return ToolResult(...)
except ValueError as e:
    diagnostics.add_error(f"좌표 변환 오류: {e}")
    return ToolResult(...)
except Exception as e:
    diagnostics.add_error(f"알 수 없는 오류: {str(e)}")
    import traceback
    diagnostics.add_error(traceback.format_exc())
    return ToolResult(...)
```

---

## 📋 완료 체크리스트

### 필수 작업
- [ ] 전체 워크플로우 재실행 테스트
- [ ] 문제 3번 오른쪽 잘림 해결 확인
- [ ] CoordinateScaler 출력 확인
- [ ] 문제 4번 원인 조사
- [ ] 단위 테스트 작성 및 실행
- [ ] AgentTools README 작성
- [ ] CHANGELOG 작성
- [ ] 코드 커밋

### 선택 작업
- [ ] 동그라미 숫자 패턴 지원 추가
- [ ] 에러 처리 강화
- [ ] 타입 힌트 개선 (Dict → dict)

---

## 💾 커밋 가이드

### 커밋 순서

```bash
# 1. 현재 변경 사항 확인
git status

# 예상 변경 파일:
# - AgentTools/mathpix_coordinate.py (수정)
# - workflows/with_mathpix.py (수정)
# - NEXT_STEPS.md (신규/수정)
# - tests/test_mathpix_coordinate.py (신규 - 다음 세션에 추가)

# 2. 스테이징
git add AgentTools/mathpix_coordinate.py
git add workflows/with_mathpix.py
git add NEXT_STEPS.md

# 3. 커밋
git commit -m "refactor: Improve Mathpix coordinate extraction consistency

- Add CoordinateScaler class for unified scaling logic
- Add configuration constants (DEFAULT_PROBLEM_HEIGHT, MIN/MAX_PROBLEM_NUMBER)
- Fix image width issue (hardcoded 1000px → actual image width)
- Refactor extract_problems_with_mathpix_coordinates() to use integrated approach
- Update workflows/with_mathpix.py to use new API

This fixes the right-side cropping issue in problem 3 extraction.

Related: .specs/System/MathpixCoordinateExtraction.idr"
```

### 다음 세션 커밋 (테스트 작성 후)

```bash
git add tests/test_mathpix_coordinate.py
git add AgentTools/README.md
git add CHANGELOG.md

git commit -m "test: Add unit tests for Mathpix coordinate extraction

- Add test_mathpix_coordinate.py with 4 test cases
- Add AgentTools/README.md with usage documentation
- Add CHANGELOG.md to track changes

All tests passing (4/4)"
```

---

## 🚀 장기 목표 (참고용)

이번 세션 후 남은 작업:

1. **Phase 2: LangGraph 병렬 처리** (4-6시간)
   - 워크플로우 명세 구현
   - 페이지별/컬럼별 병렬 실행
   - 성능 측정

2. **Phase 3: 파일 재구성** (1-2시간)
   - workflows/ 디렉토리 생성
   - import 경로 수정

3. **Phase 4: 배포 준비** (2-3시간)
   - 패키지화
   - CI/CD 설정

---

## 📞 문제 발생 시

### 스케일링 오류
```
증상: 이미지가 여전히 잘림
해결: scaler.print_info() 출력 확인
     scale_x, scale_y 값이 0.4 근처인지 확인
```

### 테스트 실패
```
증상: pytest 실패
해결:
1. 이미지 크기 확인 (column_image.shape)
2. Mathpix 데이터 구조 확인 (page_width, page_height 키 존재?)
3. 에러 메시지 자세히 읽기
```

### Import 오류
```
증상: ModuleNotFoundError
해결: Python 경로 확인
     sys.path.insert(0, str(project_root))
```

---

**마지막 업데이트**: 2025-11-08
**다음 세션 예상 시간**: 2-3시간
**우선순위**: Step 1 → Step 2 → Step 3 → Step 4
