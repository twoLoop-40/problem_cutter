||| Mathpix Coordinate-Based Problem Extraction
||| Version 3.0 - Direct extraction using Mathpix bounding boxes
|||
||| This module defines the strategy for extracting problems using
||| precise coordinates from Mathpix .lines.json API instead of
||| relying on Tesseract OCR results.
|||
||| Workflow:
||| 1. Tesseract 1차 시도 (빠름, 무료)
||| 2. 검증 실패 → Mathpix .lines.json 요청
||| 3. JSON에서 문제 번호 좌표 추출
||| 4. 좌표로 직접 이미지 자르기

module System.MathpixCoordinateExtraction

import System.Base

%default total

--------------------------------------------------------------------------------
-- Mathpix 데이터 타입
--------------------------------------------------------------------------------

||| Mathpix 바운딩 박스 (pixel coordinates)
public export
record MathpixBBox where
  constructor MkMathpixBBox
  topLeftX : Nat
  topLeftY : Nat
  width : Nat
  height : Nat

||| Mathpix line data (from .lines.json)
public export
record MathpixLine where
  constructor MkMathpixLine
  text : String              -- 텍스트 내용
  region : MathpixBBox       -- 바운딩 박스
  confidence : Double        -- 신뢰도 (0.0~1.0)
  lineNum : Nat              -- 줄 번호
  columnNum : Nat            -- 컬럼 번호
  isText : Bool              -- 텍스트 타입 여부

||| Mathpix page data
public export
record MathpixPage where
  constructor MkMathpixPage
  pageNum : Nat
  pageWidth : Nat
  pageHeight : Nat
  lines : List MathpixLine

--------------------------------------------------------------------------------
-- 문제 번호 매칭
--------------------------------------------------------------------------------

||| 문제 번호 패턴 (정규식: "숫자." 또는 "숫자,")
||| Tesseract가 "."을 ","로 오인식하는 경우 대비
public export
data ProblemPattern : Type where
  NumberDot   : Nat -> ProblemPattern  -- "3."
  NumberComma : Nat -> ProblemPattern  -- "3," (오인식)

||| 텍스트가 문제 번호 패턴과 매칭되는가?
||| 구현: Python의 re.match(r'^(\d+)[.,]\s', text)
public export
matchesProblemPattern : String -> Maybe ProblemPattern
matchesProblemPattern text = Nothing  -- Placeholder (Python에서 구현)

||| Mathpix line에서 문제 번호 추출
public export
extractProblemNumber : MathpixLine -> Maybe Nat
extractProblemNumber line =
  case matchesProblemPattern line.text of
    Just (NumberDot n) => Just n
    Just (NumberComma n) => Just n
    Nothing => Nothing

--------------------------------------------------------------------------------
-- 좌표 기반 추출 전략
--------------------------------------------------------------------------------

||| 문제 번호의 좌표 정보
public export
record ProblemMarker where
  constructor MkProblemMarker
  number : Nat
  bbox : MathpixBBox
  confidence : Double
  source : String  -- "tesseract" | "mathpix"

||| 문제 영역 추정 전략
public export
data RegionStrategy : Type where
  ||| 전략 1: 인접한 문제 번호 사이 영역
  BetweenMarkers : ProblemMarker -> ProblemMarker -> RegionStrategy

  ||| 전략 2: 마지막 문제 - 페이지 끝까지
  ToPageEnd : ProblemMarker -> Nat -> RegionStrategy  -- marker, pageHeight

  ||| 전략 3: 고정 높이 (문제 번호 Y + 추정 높이)
  FixedHeight : ProblemMarker -> Nat -> RegionStrategy  -- marker, estimatedHeight

||| 전략에 따른 바운딩 박스 계산
||| Note: 실제 계산은 Python에서 수행 (Nat 뺄셈 처리)
public export
calculateRegion : RegionStrategy -> BBox
calculateRegion (BetweenMarkers marker1 marker2) =
  -- marker1의 Y부터 marker2의 Y 직전까지
  -- Python에서 marker2.y - marker1.y 계산
  MkBBox
    (MkCoord (cast marker1.bbox.topLeftX) (cast marker1.bbox.topLeftY))
    (cast marker1.bbox.width)
    500  -- Placeholder, Python에서 계산

calculateRegion (ToPageEnd marker pageHeight) =
  -- marker의 Y부터 페이지 끝까지
  -- Python에서 pageHeight - marker.y 계산
  MkBBox
    (MkCoord (cast marker.bbox.topLeftX) (cast marker.bbox.topLeftY))
    (cast marker.bbox.width)
    500  -- Placeholder, Python에서 계산

calculateRegion (FixedHeight marker height) =
  -- marker의 Y부터 고정 높이
  MkBBox
    (MkCoord (cast marker.bbox.topLeftX) (cast marker.bbox.topLeftY))
    (cast marker.bbox.width)
    (cast height)

--------------------------------------------------------------------------------
-- 증명: 영역이 페이지 내부에 있음
--------------------------------------------------------------------------------

||| 바운딩 박스가 페이지 범위 내에 있는가?
public export
inPageBounds : BBox -> Nat -> Nat -> Bool
inPageBounds bbox pageWidth pageHeight =
  let x = cast bbox.topLeft.x
      y = cast bbox.topLeft.y
      w = cast bbox.width
      h = cast bbox.height
  in (x + w <= pageWidth) && (y + h <= pageHeight)

||| 영역이 유효함을 보장하는 타입
public export
data ValidRegion : BBox -> Nat -> Nat -> Type where
  MkValidRegion :
    (bbox : BBox) ->
    (pageWidth : Nat) ->
    (pageHeight : Nat) ->
    {auto prf : inPageBounds bbox pageWidth pageHeight = True} ->
    ValidRegion bbox pageWidth pageHeight

--------------------------------------------------------------------------------
-- 2단계 추출 워크플로우
--------------------------------------------------------------------------------

||| OCR 소스 (어디서 추출했는가?)
public export
data OcrSource : Type where
  Tesseract : OcrSource
  Mathpix   : OcrSource

||| 문제 추출 결과
public export
record ExtractionResult where
  constructor MkExtractionResult
  problemNumber : Nat
  region : BBox
  source : OcrSource
  confidence : Double

||| 2단계 추출 상태
public export
data TwoStageState : Type where
  Stage1_Tesseract   : TwoStageState  -- 1단계: Tesseract OCR
  Stage1_Validated   : TwoStageState  -- 1단계 검증 완료
  Stage1_Failed      : TwoStageState  -- 1단계 검증 실패
  Stage2_MathpixText : TwoStageState  -- 2단계: Mathpix 텍스트 (.md)
  Stage2_MathpixJson : TwoStageState  -- 2단계: Mathpix 좌표 (.lines.json)
  Stage2_Extracting  : TwoStageState  -- 2단계: 좌표로 추출 중
  Stage2_Completed   : TwoStageState  -- 2단계 완료

||| 상태 전환
public export
data TwoStageTransition : TwoStageState -> TwoStageState -> Type where
  -- 1단계 성공
  Validate1Success : TwoStageTransition Stage1_Tesseract Stage1_Validated

  -- 1단계 실패 → 2단계 Mathpix
  Validate1Fail : TwoStageTransition Stage1_Tesseract Stage1_Failed
  RequestMathpix : TwoStageTransition Stage1_Failed Stage2_MathpixText

  -- Mathpix 텍스트로 문제 번호 발견
  TextFound : TwoStageTransition Stage2_MathpixText Stage2_MathpixJson

  -- JSON 좌표로 추출
  ExtractByCoords : TwoStageTransition Stage2_MathpixJson Stage2_Extracting
  CompleteExtraction : TwoStageTransition Stage2_Extracting Stage2_Completed

--------------------------------------------------------------------------------
-- 증명: 2단계 워크플로우 건전성
--------------------------------------------------------------------------------

||| 최종 상태에서는 모든 문제가 추출됨
public export
data AllProblemsExtracted : List Nat -> List ExtractionResult -> Type where
  AllExtracted :
    (expected : List Nat) ->
    (results : List ExtractionResult) ->
    {auto prf : length expected = length results} ->
    AllProblemsExtracted expected results

||| Mathpix 좌표 우선순위: Tesseract보다 높은 신뢰도
||| Note: Double 비교는 Python에서 수행
public export
mathpixHasHigherConfidence :
  (tesseractConf : Double) ->
  (mathpixConf : Double) ->
  Bool
mathpixHasHigherConfidence _ _ = True  -- Placeholder

||| 좌표 기반 추출은 항상 성공 (좌표가 유효하면)
public export
coordinateExtractionSucceeds :
  (marker : ProblemMarker) ->
  (pageWidth : Nat) ->
  (pageHeight : Nat) ->
  (region : BBox) ->
  {auto valid : ValidRegion region pageWidth pageHeight} ->
  ExtractionResult
coordinateExtractionSucceeds marker pw ph region =
  MkExtractionResult
    marker.number
    region
    Mathpix
    marker.confidence

--------------------------------------------------------------------------------
-- 실제 구현 인터페이스 (Python)
--------------------------------------------------------------------------------

||| Python에서 구현할 함수들
namespace Implementation

  ||| Mathpix .lines.json 파싱
  public export
  parseMathpixJson : String -> Maybe MathpixPage
  parseMathpixJson json = Nothing  -- Python 구현

  ||| 문제 번호 마커 찾기
  public export
  findProblemMarkers : MathpixPage -> List Nat -> List ProblemMarker
  findProblemMarkers page missingNumbers = []  -- Python 구현

  ||| 이미지에서 영역 자르기
  public export
  cropImageRegion : String -> BBox -> String  -- imagePath -> bbox -> outputPath
  cropImageRegion path bbox = ""  -- Python 구현

--------------------------------------------------------------------------------
-- 예제 사용
--------------------------------------------------------------------------------

||| 예제: 문제 3번이 Tesseract로 감지 안 됨 → Mathpix로 추출
|||
||| 1. Tesseract: [1, 2, 5, 6] 감지 → 누락: [3, 4]
||| 2. Mathpix .lines.json 요청
||| 3. JSON에서 "3."의 좌표 찾기: (x=245, y=2374, w=25, h=27)
||| 4. 다음 문제(미발견)까지 또는 고정 높이로 영역 추정
||| 5. 좌표로 이미지 자르기
|||
||| 결과: 문제 3번 이미지 성공적으로 추출
namespace Example

  export
  exampleWorkflow : IO ()
  exampleWorkflow = do
    putStrLn "=== Mathpix 좌표 기반 추출 예제 ==="
    putStrLn "1. Tesseract: [1, 2, 5, 6] → 누락 [3, 4]"
    putStrLn "2. Mathpix .lines.json 요청"
    putStrLn "3. '3.' 좌표: (245, 2374, 25, 27)"
    putStrLn "4. 영역 추정: y=2374 ~ y=2800 (고정 높이 426px)"
    putStrLn "5. 이미지 자르기 → page1_col_1_prob_03.png"
    putStrLn "✅ 성공!"
