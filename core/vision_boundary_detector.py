"""
Vision-based Problem Boundary Detection

핵심: Claude Vision으로 이미지를 보고 문제 번호 위치 파악
OCR은 확인용으로만 사용

워크플로우:
1. 컬럼 이미지를 여러 조각으로 분할 (슬라이싱)
2. 각 조각을 Claude Vision에게 전달
3. Claude Vision이 문제 번호와 Y 좌표 반환
4. 조각별 결과를 전체 좌표로 변환
5. 경계 확정

Idris2 명세: Specs/System/VisionBoundaryDetection.idr (TODO)
"""

from typing import List, Dict, Optional, Tuple
import cv2
import numpy as np
from dataclasses import dataclass
import base64
import anthropic
import os


@dataclass
class ProblemLocation:
    """문제 번호 위치 정보"""
    problem_num: int
    y_coordinate: int  # 조각 내부 좌표
    confidence: float  # 0.0 ~ 1.0 (Claude의 확신도)


@dataclass
class ImageSlice:
    """이미지 조각"""
    slice_index: int
    y_start: int  # 전체 이미지에서의 시작 Y
    y_end: int    # 전체 이미지에서의 끝 Y
    image: np.ndarray


def split_image_into_slices(
    image: np.ndarray,
    num_slices: int = 10,
    overlap: int = 50,
) -> List[ImageSlice]:
    """
    이미지를 여러 조각으로 분할 (오버랩 포함)

    Args:
        image: 컬럼 이미지
        num_slices: 조각 개수
        overlap: 조각 간 오버랩 (문제가 경계에 걸릴 경우 대비)

    Returns:
        이미지 조각 리스트
    """
    height = image.shape[0]
    slice_height = height // num_slices

    slices = []
    for i in range(num_slices):
        y_start = max(0, i * slice_height - overlap)
        y_end = min(height, (i + 1) * slice_height + overlap)

        slice_img = image[y_start:y_end, :]

        slices.append(ImageSlice(
            slice_index=i,
            y_start=y_start,
            y_end=y_end,
            image=slice_img,
        ))

    return slices


def encode_image_to_base64(image: np.ndarray) -> str:
    """이미지를 base64로 인코딩"""
    # PNG로 인코딩
    success, buffer = cv2.imencode('.png', image)
    if not success:
        raise ValueError("Failed to encode image")

    # base64 인코딩
    return base64.b64encode(buffer).decode('utf-8')


def ask_claude_vision_for_boundaries(
    image_slice: ImageSlice,
    api_key: Optional[str] = None,
) -> List[ProblemLocation]:
    """
    Claude Vision에게 이미지 조각에서 문제 번호 위치 물어보기

    Args:
        image_slice: 이미지 조각
        api_key: Anthropic API 키 (None이면 환경변수에서 가져옴)

    Returns:
        문제 위치 리스트
    """
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found")

    client = anthropic.Anthropic(api_key=api_key)

    # 이미지 인코딩
    image_b64 = encode_image_to_base64(image_slice.image)

    # Claude Vision에게 질문
    prompt = """이 이미지는 시험지의 일부입니다.

이미지에서 **각 문제의 대략적인 위치 영역**을 찾아주세요.

**중요:**
- 정확한 문제 번호를 읽을 필요는 없습니다
- 시각적으로 문제들이 어디에 위치하는지 대략적인 영역만 파악하세요
- 각 문제 영역의 시작 Y 좌표를 찾으세요 (문제가 시작되는 위치)
- 페이지 번호, 점수 표시 등은 무시하세요
- 빈 공간이나 여백은 무시하세요
- 실제로 텍스트나 내용이 있는 문제 영역만 찾으세요

각 문제 영역에 대해 다음 정보를 JSON 형태로 반환해주세요:
```json
[
  {
    "problem_num": 1,
    "y_coordinate": 150,
    "confidence": 0.95
  },
  {
    "problem_num": 2,
    "y_coordinate": 450,
    "confidence": 0.90
  }
]
```

- problem_num: 몇 번째 문제인지 (1부터 시작, 순서대로)
- y_coordinate: 문제 영역이 시작되는 Y 좌표 (픽셀, 위에서부터)
- confidence: 확신도 (0.0 ~ 1.0)

**JSON만 반환하세요 (설명 없이)**
"""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                }
            ],
        }],
    )

    # 응답 파싱
    import json
    response_text = response.content[0].text.strip()

    # JSON 추출 (```json ... ``` 형태일 수 있음)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    try:
        locations_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 실패: {response_text}")
        return []

    # ProblemLocation 객체로 변환
    locations = []
    for loc_data in locations_data:
        locations.append(ProblemLocation(
            problem_num=loc_data["problem_num"],
            y_coordinate=loc_data["y_coordinate"],
            confidence=loc_data.get("confidence", 0.8),
        ))

    return locations


def detect_boundaries_with_vision(
    image: np.ndarray,
    num_slices: int = 5,
    api_key: Optional[str] = None,
) -> Dict[int, Tuple[int, int]]:
    """
    Claude Vision으로 문제 경계 감지

    Args:
        image: 컬럼 이미지
        num_slices: 조각 개수
        api_key: Anthropic API 키

    Returns:
        {problem_num: (y_start, y_end)}
    """
    # 1. 이미지 조각내기
    slices = split_image_into_slices(image, num_slices=num_slices)

    # 2. 각 조각에서 문제 위치 찾기
    all_locations = []

    for slice_obj in slices:
        print(f"  [Vision] 조각 {slice_obj.slice_index + 1}/{num_slices} 분석 중...")

        locations = ask_claude_vision_for_boundaries(slice_obj, api_key=api_key)

        # 조각 내부 좌표를 전체 좌표로 변환
        for loc in locations:
            global_y = slice_obj.y_start + loc.y_coordinate
            all_locations.append(ProblemLocation(
                problem_num=loc.problem_num,
                y_coordinate=global_y,
                confidence=loc.confidence,
            ))

        print(f"    → {len(locations)}개 문제 번호 발견")

    # 3. 중복 제거 (같은 문제 번호가 여러 조각에서 발견될 수 있음)
    problem_positions = {}  # {problem_num: [(y, confidence), ...]}

    for loc in all_locations:
        if loc.problem_num not in problem_positions:
            problem_positions[loc.problem_num] = []
        problem_positions[loc.problem_num].append((loc.y_coordinate, loc.confidence))

    # 4. 각 문제 번호의 대표 위치 선택 (가중 평균)
    unique_locations = []

    for prob_num, positions in problem_positions.items():
        # 확신도로 가중 평균
        total_weight = sum(conf for _, conf in positions)
        weighted_y = sum(y * conf for y, conf in positions) / total_weight
        avg_confidence = total_weight / len(positions)

        unique_locations.append(ProblemLocation(
            problem_num=prob_num,
            y_coordinate=int(weighted_y),
            confidence=avg_confidence,
        ))

    # 5. Y 좌표로 정렬
    unique_locations.sort(key=lambda loc: loc.y_coordinate)

    # 6. 경계 계산
    height = image.shape[0]
    boundaries = {}

    for i, loc in enumerate(unique_locations):
        # 시작: 문제 번호 위 50px (또는 이전 문제 끝에서 중간)
        if i == 0:
            y_start = max(0, loc.y_coordinate - 50)
        else:
            prev_loc = unique_locations[i - 1]
            y_start = (prev_loc.y_coordinate + loc.y_coordinate) // 2

        # 끝: 다음 문제 번호 직전 (또는 이미지 끝)
        if i + 1 < len(unique_locations):
            next_loc = unique_locations[i + 1]
            y_end = (loc.y_coordinate + next_loc.y_coordinate) // 2
        else:
            y_end = height

        boundaries[loc.problem_num] = (y_start, y_end)

    return boundaries
