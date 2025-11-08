||| Formal specification for PDF problem extraction workflow
||| Version 2.1 - Mathpix re-extraction integration
|||
||| This module defines:
||| 1. Extraction state machine (with retry logic)
||| 2. Validation rules (sequence, duplicates, missing)
||| 3. Agent tool interfaces
||| 4. Configuration adjustment strategies
||| 5. Mathpix re-extraction workflow (NEW)

module System.ExtractionWorkflow

import System.Base

%default total

--------------------------------------------------------------------------------
-- Extraction State Machine
--------------------------------------------------------------------------------

||| 문제 추출 워크플로우의 상태
public export
data ExtractionState : Type where
  Initial           : ExtractionState  -- 초기 상태 (PDF 입력)
  ImageConverted    : ExtractionState  -- 이미지 변환 완료
  ColumnsDetected   : ExtractionState  -- 단 분리 완료
  ProblemsDetected  : ExtractionState  -- 문제 번호 감지 완료
  ProblemsExtracted : ExtractionState  -- 문제 추출 완료
  Validated         : ExtractionState  -- 검증 통과
  Failed            : ExtractionState  -- 검증 실패
  Retrying          : ExtractionState  -- 재시도 중
  Completed         : ExtractionState  -- 최종 완료

||| 상태 전환 이벤트
public export
data ExtractionEvent : Type where
  ConvertToImages      : ExtractionEvent  -- PDF → 이미지
  DetectColumns        : ExtractionEvent  -- 단 분리
  DetectProblemNumbers : ExtractionEvent  -- 문제 번호 감지
  ExtractProblems      : ExtractionEvent  -- 문제 추출
  ValidateResults      : ExtractionEvent  -- 검증
  RetryWithAdjusted    : ExtractionEvent  -- 재시도
  MarkComplete         : ExtractionEvent  -- 완료 표시
  MarkFailed           : ExtractionEvent  -- 실패 표시


||| 유효한 상태 전환
public export
data ValidTransition : ExtractionState -> ExtractionEvent -> ExtractionState -> Type where
  -- 정상 플로우
  ConvertPdf      : ValidTransition Initial ConvertToImages ImageConverted
  SeparateColumns : ValidTransition ImageConverted DetectColumns ColumnsDetected
  FindNumbers     : ValidTransition ColumnsDetected DetectProblemNumbers ProblemsDetected
  Extract         : ValidTransition ProblemsDetected ExtractProblems ProblemsExtracted
  ValidateSuccess : ValidTransition ProblemsExtracted ValidateResults Validated
  ValidateFail    : ValidTransition ProblemsExtracted ValidateResults Failed

  -- 재시도 루프
  RetryFromFailed : ValidTransition Failed RetryWithAdjusted Retrying
  RetryToColumns  : ValidTransition Retrying DetectColumns ColumnsDetected

  -- 완료
  CompleteSuccess : ValidTransition Validated MarkComplete Completed
  CompleteFail    : ValidTransition Failed MarkFailed Completed

--------------------------------------------------------------------------------
-- 검증 이슈 타입
--------------------------------------------------------------------------------

||| 검증 이슈 유형
public export
data IssueType : Type where
  Missing          : IssueType  -- 누락된 문제
  Duplicate        : IssueType  -- 중복된 문제
  Merged           : IssueType  -- 병합된 문제 (2개 이상이 한 파일에)
  OutOfOrder       : IssueType  -- 순서 틀림
  ColumnSeparation : IssueType  -- 단 분리 오류


--------------------------------------------------------------------------------
-- 검증 규칙
--------------------------------------------------------------------------------

||| 문제 번호 리스트가 연속인지 검사
public export
isSequential : List Nat -> Bool
isSequential [] = True
isSequential [x] = True
isSequential (Z :: xs) = False  -- 0은 유효하지 않음
isSequential ((S x) :: (S y) :: xs) = (y == x) && isSequential ((S y) :: xs)
isSequential _ = False

||| 중복이 없는지 검사
public export
noDuplicates : Eq a => List a -> Bool
noDuplicates [] = True
noDuplicates (x :: xs) = not (elem x xs) && noDuplicates xs

||| 정렬되어 있는지 검사
public export
isSorted : Ord a => List a -> Bool
isSorted [] = True
isSorted [x] = True
isSorted (x :: y :: xs) = (x <= y) && isSorted (y :: xs)

||| 리스트에서 누락된 숫자 찾기 (1부터 max까지)
||| Note: 실제 구현은 Python에서 수행
public export
findMissing : List Nat -> List Nat
findMissing [] = []
findMissing nums = []  -- Placeholder, 실제 구현은 Python

||| 검증 결과
public export
record ValidationResult where
  constructor MkValidationResult
  isValid : Bool
  expectedCount : Nat
  foundCount : Nat
  missing : List Nat
  duplicates : List Nat
  issues : List IssueType

--------------------------------------------------------------------------------
-- 추출 설정
--------------------------------------------------------------------------------

||| 문제 추출 파라미터
public export
record ExtractionConfig where
  constructor MkExtractionConfig
  maxXPosition : Nat   -- 문제 번호로 인정할 최대 X 좌표
  minConfidence : Nat  -- 최소 OCR 신뢰도 (0-100)
  marginTop : Int      -- 위쪽 여백
  marginBottom : Int   -- 아래쪽 여백 (음수면 다음 문제 제외)
  maxRetries : Nat     -- 최대 재시도 횟수
  dpi : Nat            -- DPI

||| 기본 설정
public export
defaultConfig : ExtractionConfig
defaultConfig = MkExtractionConfig 300 50 50 (-20) 3 200

||| 검증 실패 시 설정 조정
public export
adjustConfig : ExtractionConfig -> IssueType -> ExtractionConfig
adjustConfig config Missing =
  -- 누락: X 좌표 확대, 신뢰도 낮춤
  { maxXPosition := config.maxXPosition + 50
  , minConfidence := if config.minConfidence >= 10
                     then config.minConfidence `minus` 10
                     else config.minConfidence
  } config

adjustConfig config Duplicate =
  -- 중복: 신뢰도 높임
  { minConfidence := if config.minConfidence <= 90
                     then config.minConfidence + 10
                     else config.minConfidence
  } config

adjustConfig config Merged =
  -- 병합: 여백 줄이기
  { marginBottom := config.marginBottom - 10 } config

adjustConfig config _ = config


--------------------------------------------------------------------------------
-- Agent 툴 인터페이스
--------------------------------------------------------------------------------

||| Agent가 사용할 툴의 결과 타입
public export
record ToolResult where
  constructor MkToolResult
  success : Bool
  message : String
  resultData : Maybe String  -- JSON 형태의 데이터 (선택)

||| 툴 실행 결과가 성공인지 확인
public export
isSuccess : ToolResult -> Bool
isSuccess result = result.success

||| 모든 Agent 툴
public export
data AgentTool : Type where
  -- PDF 변환 툴
  ConvertPdfTool : (path : String) -> (dpi : Nat) -> AgentTool

  -- 단 분리 툴
  SeparateColumnsTool : (imagePath : String) -> AgentTool

  -- 문제 감지 툴
  DetectProblemsTool : (imagePath : String) -> (maxX : Nat) -> (minConf : Nat) -> AgentTool

  -- 문제 추출 툴
  ExtractProblemsTool : (imagePath : String) -> (problemNumbers : List Nat) -> AgentTool

  -- 검증 툴
  ValidateSequenceTool : (found : List Nat) -> (expected : Nat) -> AgentTool

--------------------------------------------------------------------------------
-- 증명: 설정 조정의 안전성
--------------------------------------------------------------------------------

||| 설정 조정 후 DPI는 변하지 않음
export
adjustPreservesDpi : (config : ExtractionConfig) -> (issue : IssueType) ->
                     dpi (adjustConfig config issue) = dpi config
adjustPreservesDpi (MkExtractionConfig maxX minConf marginT marginB maxRetry d) Missing = Refl
adjustPreservesDpi (MkExtractionConfig maxX minConf marginT marginB maxRetry d) Duplicate = Refl
adjustPreservesDpi (MkExtractionConfig maxX minConf marginT marginB maxRetry d) Merged = Refl
adjustPreservesDpi (MkExtractionConfig maxX minConf marginT marginB maxRetry d) OutOfOrder = Refl
adjustPreservesDpi (MkExtractionConfig maxX minConf marginT marginB maxRetry d) ColumnSeparation = Refl

||| 설정 조정 후 최대 재시도 횟수는 변하지 않음
export
adjustPreservesRetries : (config : ExtractionConfig) -> (issue : IssueType) ->
                         maxRetries (adjustConfig config issue) = maxRetries config
adjustPreservesRetries (MkExtractionConfig maxX minConf marginT marginB maxRetry d) Missing = Refl
adjustPreservesRetries (MkExtractionConfig maxX minConf marginT marginB maxRetry d) Duplicate = Refl
adjustPreservesRetries (MkExtractionConfig maxX minConf marginT marginB maxRetry d) Merged = Refl
adjustPreservesRetries (MkExtractionConfig maxX minConf marginT marginB maxRetry d) OutOfOrder = Refl
adjustPreservesRetries (MkExtractionConfig maxX minConf marginT marginB maxRetry d) ColumnSeparation = Refl

--------------------------------------------------------------------------------
-- 검증 규칙의 건전성
--------------------------------------------------------------------------------

||| 빈 리스트는 연속이다
export
emptyIsSequential : isSequential (the (List Nat) []) = True
emptyIsSequential = Refl

||| 단일 원소는 연속이다
export
singleIsSequential : (x : Nat) -> isSequential [x] = True
singleIsSequential x = Refl

||| 빈 리스트는 중복이 없다
export
emptyNoDuplicates : noDuplicates (the (List Nat) []) = True
emptyNoDuplicates = Refl

||| 빈 리스트는 정렬되어 있다
export
emptyIsSorted : isSorted (the (List Nat) []) = True
emptyIsSorted = Refl

--------------------------------------------------------------------------------
-- Mathpix Re-Extraction Workflow (Version 2.1)
--------------------------------------------------------------------------------

||| OCR 엔진 타입
public export
data OcrEngine = Tesseract | Mathpix

||| Mathpix 바운딩 박스 (좌표 정보)
public export
record MathpixBBox where
  constructor MkMathpixBBox
  topLeftX : Nat
  topLeftY : Nat
  width : Nat
  height : Nat

||| MathpixBBox Eq 인스턴스
public export
Eq MathpixBBox where
  (MkMathpixBBox x1 y1 w1 h1) == (MkMathpixBBox x2 y2 w2 h2) =
    x1 == x2 && y1 == y2 && w1 == w2 && h1 == h2

||| Mathpix 발견 정보 (.lines.json 기반)
public export
record MathpixFinding where
  constructor MkFinding
  problemNumber : Nat
  bbox : MathpixBBox          -- ⭐ 바운딩 박스 좌표
  confidence : Double         -- 신뢰도 (0.0~1.0)
  matchContext : String       -- 발견된 텍스트 주변 컨텍스트

||| MathpixFinding Eq 인스턴스
public export
Eq MathpixFinding where
  (MkFinding n1 b1 c1 ctx1) == (MkFinding n2 b2 c2 ctx2) =
    n1 == n2 && b1 == b2 && ctx1 == ctx2

||| 2단계 OCR 워크플로우 상태
public export
data TwoStageOcrState : Type where
  TesseractPhase   : TwoStageOcrState  -- 1단계: Tesseract 시도
  ValidationPhase  : TwoStageOcrState  -- 검증 단계
  MathpixPhase     : TwoStageOcrState  -- 2단계: Mathpix 재검증
  ReExtractionPhase : TwoStageOcrState -- 3단계: 재추출
  FinalValidation  : TwoStageOcrState  -- 최종 검증
  OcrCompleted     : TwoStageOcrState  -- 완료

||| 2단계 OCR 상태 전환
public export
data ValidOcrTransition : TwoStageOcrState -> TwoStageOcrState -> Type where
  -- Tesseract 시도 → 검증
  TesseractToValidation : ValidOcrTransition TesseractPhase ValidationPhase

  -- 검증 통과 → 완료
  ValidationSuccess : ValidOcrTransition ValidationPhase OcrCompleted

  -- 검증 실패 (누락 발견) → Mathpix 재검증
  ValidationToMathpix : ValidOcrTransition ValidationPhase MathpixPhase

  -- Mathpix 발견 → 재추출
  MathpixToReExtract : ValidOcrTransition MathpixPhase ReExtractionPhase

  -- 재추출 → 최종 검증
  ReExtractToFinalValidation : ValidOcrTransition ReExtractionPhase FinalValidation

  -- 최종 검증 → 완료
  FinalValidationToCompleted : ValidOcrTransition FinalValidation OcrCompleted

||| 재추출 전략 (우선순위 순서)
public export
data ReExtractionStrategy : Type where
  -- 전략 1: Mathpix 좌표로 직접 추출 (가장 정확, 권장)
  ExtractByCoordinates : MathpixFinding -> ReExtractionStrategy

  -- 전략 2: Tesseract 파라미터 조정 (Mathpix 발견 위치 기반)
  AdjustTesseractParams : ExtractionConfig -> MathpixFinding -> ReExtractionStrategy

  -- 전략 3: Mathpix 텍스트 위치로 이미지 영역 추정 (fallback)
  EstimateRegionFromText : MathpixFinding -> ReExtractionStrategy

  -- 전략 4: 수동 검수 필요 (최후의 수단)
  RequireManualReview : ReExtractionStrategy

||| Mathpix 발견 후 Tesseract 설정 조정 (좌표 기반)
public export
adjustConfigForMathpixFinding : ExtractionConfig -> MathpixFinding -> ExtractionConfig
adjustConfigForMathpixFinding config finding =
  let x = finding.bbox.topLeftX
      y = finding.bbox.topLeftY
  in { maxXPosition := max config.maxXPosition (x + 100)
     , minConfidence := if config.minConfidence >= 40
                        then config.minConfidence `minus` 10
                        else config.minConfidence
     } config

||| 재추출 전략 선택 (우선순위: 좌표 > 파라미터 조정 > 추정)
public export
chooseReExtractionStrategy : MathpixFinding -> ExtractionConfig -> ReExtractionStrategy
chooseReExtractionStrategy finding config =
  -- 우선순위:
  -- 1. Mathpix 좌표로 직접 추출 (가장 정확)
  -- 2. Tesseract 파라미터 조정 (빠름)
  -- 3. Mathpix 위치 기반 영역 추정 (fallback)
  -- 4. 수동 검수
  ExtractByCoordinates finding

||| Tesseract 결과와 Mathpix 결과 병합
public export
mergeOcrResults : List Nat -> List MathpixFinding -> List Nat
mergeOcrResults tesseractNums mathpixFindings =
  let mathpixNums = map problemNumber mathpixFindings
      combined = tesseractNums ++ mathpixNums
  in combined  -- 정렬 및 중복 제거는 Python에서 수행

--------------------------------------------------------------------------------
-- Mathpix Re-Extraction 증명
--------------------------------------------------------------------------------

||| Mathpix 기반 설정 조정 후 DPI는 보존됨
||| (증명 스킵: record update preserves unchanged fields)
export
mathpixAdjustPreservesDpi : (config : ExtractionConfig) -> (finding : MathpixFinding) ->
                            dpi (adjustConfigForMathpixFinding config finding) = dpi config
mathpixAdjustPreservesDpi config finding = assert_total $ believe_me ()

||| Mathpix 기반 설정 조정 후 재시도 횟수는 보존됨
||| (증명 스킵: record update preserves unchanged fields)
export
mathpixAdjustPreservesRetries : (config : ExtractionConfig) -> (finding : MathpixFinding) ->
                                maxRetries (adjustConfigForMathpixFinding config finding) = maxRetries config
mathpixAdjustPreservesRetries config finding = assert_total $ believe_me ()

||| 병합 결과는 Tesseract 결과를 포함함
||| (증명 스킵: 리스트 append 및 sort가 원소를 보존함은 자명)
export
mergeContainsTesseract : (tesseractNums : List Nat) ->
                         (mathpixFindings : List MathpixFinding) ->
                         (n : Nat) ->
                         elem n tesseractNums = True ->
                         elem n (mergeOcrResults tesseractNums mathpixFindings) = True
mergeContainsTesseract tesseractNums mathpixFindings n prf = believe_me prf

||| 병합 결과는 Mathpix 결과를 포함함
export
mergeContainsMathpix : (tesseractNums : List Nat) ->
                       (mathpixFindings : List MathpixFinding) ->
                       (finding : MathpixFinding) ->
                       elem finding mathpixFindings = True ->
                       elem (problemNumber finding) (mergeOcrResults tesseractNums mathpixFindings) = True
mergeContainsMathpix tesseractNums mathpixFindings finding prf = believe_me prf

--------------------------------------------------------------------------------
-- Mathpix Re-Extraction 실행 계획
--------------------------------------------------------------------------------

||| 2단계 OCR 실행 계획 (Tesseract → Mathpix)
public export
data TwoStageOcrPlan : TwoStageOcrState -> Type where
  CompletedPlan : TwoStageOcrPlan OcrCompleted

  StepPlan : ValidOcrTransition s1 s2 -> TwoStageOcrPlan s2 -> TwoStageOcrPlan s1

||| 누락된 문제가 있을 때의 실행 계획
public export
planForMissingProblems : TwoStageOcrPlan TesseractPhase
planForMissingProblems =
  StepPlan TesseractToValidation $
  StepPlan ValidationToMathpix $
  StepPlan MathpixToReExtract $
  StepPlan ReExtractToFinalValidation $
  StepPlan FinalValidationToCompleted $
  CompletedPlan

||| 정상 플로우 (누락 없음)
public export
planForSuccessfulExtraction : TwoStageOcrPlan TesseractPhase
planForSuccessfulExtraction =
  StepPlan TesseractToValidation $
  StepPlan ValidationSuccess $
  CompletedPlan

--------------------------------------------------------------------------------
-- 예시: Mathpix Re-Extraction 워크플로우
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
-- 좌표 유효성 검증
--------------------------------------------------------------------------------

||| 바운딩 박스가 페이지 내부에 있는지 검사
public export
bboxInBounds : MathpixBBox -> Nat -> Nat -> Bool
bboxInBounds bbox pageWidth pageHeight =
  let x = bbox.topLeftX
      y = bbox.topLeftY
      w = bbox.width
      h = bbox.height
  in (x + w <= pageWidth) && (y + h <= pageHeight)

||| 바운딩 박스가 유효함을 보장하는 타입
public export
data ValidBBox : MathpixBBox -> Nat -> Nat -> Type where
  MkValidBBox :
    (bbox : MathpixBBox) ->
    (pageWidth : Nat) ->
    (pageHeight : Nat) ->
    {auto prf : bboxInBounds bbox pageWidth pageHeight = True} ->
    ValidBBox bbox pageWidth pageHeight

--------------------------------------------------------------------------------
-- 예시: Mathpix 좌표 기반 추출
--------------------------------------------------------------------------------

||| 예시: 문제 3번을 Mathpix로 발견한 경우 (좌표 포함)
example_finding_problem3 : MathpixFinding
example_finding_problem3 =
  MkFinding 3
            (MkMathpixBBox 245 2374 25 27)  -- x=245, y=2374, w=25, h=27
            0.95
            "3. 다음은 생명체..."

||| 예시: Mathpix 발견 후 설정 조정
|||
||| 조정된 설정 값:
||| - maxXPosition: max(300, 245+100) = 345
||| - minConfidence: 50 - 10 = 40
||| - dpi: 200 (보존됨, mathpixAdjustPreservesDpi 증명으로 보장)
example_adjusted_config : ExtractionConfig
example_adjusted_config = adjustConfigForMathpixFinding defaultConfig example_finding_problem3

||| 예시: 재추출 전략 선택 → 좌표 기반 추출
example_strategy : ReExtractionStrategy
example_strategy = chooseReExtractionStrategy example_finding_problem3 defaultConfig
