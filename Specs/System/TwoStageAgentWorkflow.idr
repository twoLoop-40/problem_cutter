||| 2-Stage OCR Agent Workflow (Tesseract → Mathpix)
|||
||| FastAPI + Agent 기반 자동 문제 추출 워크플로우
|||
||| 핵심 전략:
||| 1. Tesseract로 1차 OCR (빠르고 무료)
||| 2. Agent가 검증 (누락된 문제 번호 파악)
||| 3. 누락된 문제만 Mathpix로 재추출 (비용 절감)
||| 4. 최종 검증 및 결과 생성
|||
||| Python 구현: app/services/agent_extraction_service.py

module System.TwoStageAgentWorkflow

import System.Base
import System.ExtractionWorkflow
import System.AppArchitecture
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- OCR Stage (단계)
-- =============================================================================

||| OCR 단계
public export
data OcrStage
  = TesseractStage    -- 1단계: Tesseract OCR (빠름)
  | MathpixStage      -- 2단계: Mathpix OCR (정확함)

||| OCR 결과
public export
record OcrResult where
  constructor MkOcrResult
  stage : OcrStage
  detectedNumbers : List Nat
  confidence : Double

-- =============================================================================
-- Agent States (웹 앱 통합)
-- =============================================================================

||| Agent 상태 (FastAPI Job 상태와 연동)
public export
data AgentState
  = Initial                    -- 시작
  | ConvertingPdf              -- PDF → 이미지 변환
  | DetectingLayout            -- 레이아웃 감지
  | SeparatingColumns          -- 컬럼 분리
  | RunningTesseract           -- Tesseract OCR 실행
  | ExtractingProblemsStage1   -- 1단계 문제 추출
  | ValidatingStage1           -- 1단계 검증
  | DecidingNextAction         -- Agent 판단 (Mathpix 필요 여부)
  | RunningMathpix             -- Mathpix OCR 실행 (누락 문제만)
  | ExtractingProblemsStage2   -- 2단계 문제 추출 (좌표 기반)
  | ValidatingFinal            -- 최종 검증
  | GeneratingFiles            -- 파일 생성 (개별 이미지)
  | CreatingZip                -- ZIP 패키징
  | Complete                   -- 완료
  | Failed String              -- 실패

-- =============================================================================
-- Agent Tools (실제 구현 매핑)
-- =============================================================================

||| Agent가 사용할 수 있는 도구
public export
data AgentTool
  = PdfConverterTool           -- core.pdf_converter.convert_pdf_to_images()
  | LayoutDetectorTool         -- core.layout_detector.detect_layout()
  | ColumnSeparatorTool        -- core.column_separator.separate_columns()
  | TesseractOCRTool           -- core.ocr_engine.run_tesseract_ocr()
  | ProblemExtractorTool       -- core.problem_extractor.extract_problems()
  | MathpixOCRTool             -- core.mathpix_client.run_mathpix_ocr()
  | CoordinateExtractorTool    -- AgentTools.mathpix_coordinate.extract_problems_with_mathpix_coordinates()
  | ValidationTool             -- AgentTools.validation.validate_problem_sequence()
  | FileGeneratorTool          -- core.file_generator.save_problem_images()
  | ZipCreatorTool             -- zipfile.ZipFile()

-- =============================================================================
-- Agent Decision (판단)
-- =============================================================================

||| Agent의 판단 결과
public export
data AgentDecision
  = ProceedToFileGeneration                    -- Tesseract 결과만으로 충분 → 파일 생성
  | UseMathpixForMissing (List Nat)            -- 누락 문제를 Mathpix로 재추출
  | RetryTesseract (List String)               -- Tesseract 파라미터 조정 후 재시도
  | AbortWithError String                      -- 오류로 중단

||| 판단 기준
|||
||| 누락 문제 수에 따른 전략:
||| - 0개: 모두 성공 → 파일 생성
||| - 1-3개: Mathpix 사용 (비용 효율적)
||| - 4개 이상: Tesseract 재시도 또는 Mathpix 사용 (사용자 설정)
public export
decideNextAction : (detected : List Nat) -> (expected : List Nat) -> AgentDecision
decideNextAction detected expected =
  let missing = filter (\n => not (elem n detected)) expected
  in case length missing of
       Z => ProceedToFileGeneration
       (S Z) => UseMathpixForMissing missing
       (S (S Z)) => UseMathpixForMissing missing
       (S (S (S Z))) => UseMathpixForMissing missing
       _ => UseMathpixForMissing missing  -- 4개 이상도 Mathpix 시도

-- =============================================================================
-- Workflow State (Job + Agent 통합)
-- =============================================================================

||| 2-Stage Agent 워크플로우 상태
public export
record TwoStageAgentWorkflow where
  constructor MkTwoStageAgentWorkflow
  ||| Job ID (FastAPI Job과 연동)
  jobId : JobId
  ||| PDF 경로
  pdfPath : String
  ||| 현재 Agent 상태
  currentState : AgentState
  ||| Tesseract 결과
  tesseractResult : Maybe OcrResult
  ||| Mathpix 결과
  mathpixResult : Maybe OcrResult
  ||| 최종 검출된 문제 번호들
  detectedProblems : List Nat
  ||| 기대하는 문제 번호들 (1부터 N까지)
  expectedProblems : Maybe (List Nat)
  ||| Agent 결정
  lastDecision : Maybe AgentDecision
  ||| 진행률 (0-100)
  progressPercentage : Nat
  ||| 현재 메시지
  currentMessage : String
  ||| Mathpix 설정 (API 키, App ID)
  mathpixConfig : Maybe (String, String)

||| 초기 워크플로우 생성
public export
initialTwoStageWorkflow : JobId -> String -> Maybe (String, String) -> TwoStageAgentWorkflow
initialTwoStageWorkflow jid path mathpixCfg = MkTwoStageAgentWorkflow
  { jobId = jid
  , pdfPath = path
  , currentState = Initial
  , tesseractResult = Nothing
  , mathpixResult = Nothing
  , detectedProblems = []
  , expectedProblems = Nothing
  , lastDecision = Nothing
  , progressPercentage = 0
  , currentMessage = "대기 중"
  , mathpixConfig = mathpixCfg
  }

-- =============================================================================
-- State Transitions (상태 전환)
-- =============================================================================

||| 유효한 Agent 상태 전환
public export
data ValidTwoStageTransition : AgentState -> AgentState -> Type where
  -- 순차 진행
  StartConvert : ValidTwoStageTransition Initial ConvertingPdf
  ConvertToLayout : ValidTwoStageTransition ConvertingPdf DetectingLayout
  LayoutToSeparate : ValidTwoStageTransition DetectingLayout SeparatingColumns
  SeparateToTesseract : ValidTwoStageTransition SeparatingColumns RunningTesseract
  TesseractToExtract1 : ValidTwoStageTransition RunningTesseract ExtractingProblemsStage1
  Extract1ToValidate1 : ValidTwoStageTransition ExtractingProblemsStage1 ValidatingStage1
  Validate1ToDecide : ValidTwoStageTransition ValidatingStage1 DecidingNextAction

  -- Agent 판단 후 분기
  DecideToGenerate : ValidTwoStageTransition DecidingNextAction GeneratingFiles  -- 성공 케이스
  DecideToMathpix : ValidTwoStageTransition DecidingNextAction RunningMathpix    -- Mathpix 필요

  -- Mathpix 경로
  MathpixToExtract2 : ValidTwoStageTransition RunningMathpix ExtractingProblemsStage2
  Extract2ToValidateFinal : ValidTwoStageTransition ExtractingProblemsStage2 ValidatingFinal
  ValidateFinalToGenerate : ValidTwoStageTransition ValidatingFinal GeneratingFiles

  -- 파일 생성 및 완료
  GenerateToZip : ValidTwoStageTransition GeneratingFiles CreatingZip
  ZipToComplete : ValidTwoStageTransition CreatingZip Complete

  -- 실패
  AnyToFailed : (st : AgentState) -> (reason : String) -> ValidTwoStageTransition st (Failed reason)

-- =============================================================================
-- Progress Tracking (진행률 계산)
-- =============================================================================

||| 각 상태별 진행률 매핑
public export
stateToProgress : AgentState -> Nat
stateToProgress Initial = 0
stateToProgress ConvertingPdf = 10
stateToProgress DetectingLayout = 20
stateToProgress SeparatingColumns = 30
stateToProgress RunningTesseract = 40
stateToProgress ExtractingProblemsStage1 = 50
stateToProgress ValidatingStage1 = 60
stateToProgress DecidingNextAction = 65
stateToProgress RunningMathpix = 70
stateToProgress ExtractingProblemsStage2 = 80
stateToProgress ValidatingFinal = 85
stateToProgress GeneratingFiles = 90
stateToProgress CreatingZip = 95
stateToProgress Complete = 100
stateToProgress (Failed _) = 0

||| 각 상태별 메시지
public export
stateToMessage : AgentState -> String
stateToMessage Initial = "대기 중"
stateToMessage ConvertingPdf = "PDF → 이미지 변환 중"
stateToMessage DetectingLayout = "레이아웃 감지 중"
stateToMessage SeparatingColumns = "컬럼 분리 중"
stateToMessage RunningTesseract = "Tesseract OCR 실행 중"
stateToMessage ExtractingProblemsStage1 = "문제 추출 중 (1단계)"
stateToMessage ValidatingStage1 = "검증 중 (1단계)"
stateToMessage DecidingNextAction = "Agent 판단 중"
stateToMessage RunningMathpix = "Mathpix OCR 실행 중"
stateToMessage ExtractingProblemsStage2 = "문제 추출 중 (2단계, 좌표 기반)"
stateToMessage ValidatingFinal = "최종 검증 중"
stateToMessage GeneratingFiles = "파일 생성 중"
stateToMessage CreatingZip = "ZIP 패키징 중"
stateToMessage Complete = "완료"
stateToMessage (Failed reason) = "실패: " ++ reason

-- =============================================================================
-- Guarantees (보장 사항)
-- =============================================================================

||| Tesseract 단계는 항상 먼저 실행됨
public export
data TesseractFirst : TwoStageAgentWorkflow -> Type where
  MkTesseractFirst :
    (wf : TwoStageAgentWorkflow) ->
    (result : OcrResult) ->
    (wf.currentState = RunningMathpix) ->
    (wf.tesseractResult = Just result) ->
    TesseractFirst wf

||| Mathpix는 누락 문제가 있을 때만 실행
public export
data MathpixOnlyWhenNeeded : TwoStageAgentWorkflow -> Type where
  MkMathpixOnlyWhenNeeded :
    (wf : TwoStageAgentWorkflow) ->
    (result : OcrResult) ->
    (wf.currentState = RunningMathpix) ->
    (expected : List Nat) ->
    (detected : List Nat) ->
    (wf.expectedProblems = Just expected) ->
    (wf.tesseractResult = Just result) ->
    (length (filter (\n => not (elem n detected)) expected) > 0 = True) ->
    MathpixOnlyWhenNeeded wf

||| 완료 시 모든 문제 검출 보장
public export
data AllProblemsDetectedWhenComplete : TwoStageAgentWorkflow -> Type where
  MkAllDetected :
    (wf : TwoStageAgentWorkflow) ->
    (expected : List Nat) ->
    (wf.currentState = Complete) ->
    (wf.expectedProblems = Just expected) ->
    (wf.detectedProblems = expected) ->
    AllProblemsDetectedWhenComplete wf
