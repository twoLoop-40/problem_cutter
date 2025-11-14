||| Agent State Definitions for LangGraph Integration
|||
||| 이 모듈은 LangGraph Agent의 상태를 정의합니다.
||| Python 구현: app/agents/state.py
|||
||| 핵심 설계:
||| - OCR 엔진 추상화 (Tesseract, Mathpix, Claude Vision 등 교체 가능)
||| - 2-Stage 전략: FastOcr → AccurateOcr (비용 최적화)
||| - LangGraph 통합: TypedDict, Reducer, Checkpointing

module System.Agent.State

import System.Base
import System.Ocr.Interface
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- Basic Types
-- =============================================================================

||| Job ID (FastAPI와 연동)
public export
JobId : Type
JobId = String

-- =============================================================================
-- OCR Engine Abstraction (from System.Ocr.Interface)
-- =============================================================================

||| OCR 관련 타입들은 System.Ocr.Interface에서 import됨:
||| - OcrEngineType: OCR 엔진 종류 (Tesseract, Mathpix, Claude Vision, etc.)
||| - OcrStrategy: 2단계 전략 정의
||| - OcrExecutionResult: Agent가 사용하는 OCR 결과
||| - categorizeEngine: Fast/Accurate 분류 함수

-- =============================================================================
-- Agent States (LangGraph Node States)
-- =============================================================================

||| Agent 실행 상태
|||
||| LangGraph에서 각 Node는 이 상태 중 하나에 해당합니다.
||| Node 간 전환은 ValidTransition으로 보장됩니다.
|||
||| 핵심: OCR 엔진 이름을 직접 사용하지 않음 (Stage1, Stage2로 추상화)
public export
data AgentState
  = Initial                    -- 시작
  | ConvertingPdf              -- PDF → 이미지 변환 (Node: convert_pdf)
  | DetectingLayout            -- 레이아웃 감지 (Node: detect_layout)
  | SeparatingColumns          -- 컬럼 분리 (Node: separate_columns)
  | RunningOcrStage1           -- 1단계 OCR 실행 (Node: run_ocr_stage1, Fast)
  | ExtractingProblemsStage1   -- 1단계 문제 추출 (Node: extract_stage1)
  | ValidatingStage1           -- 1단계 검증 (Node: validate_stage1)
  | DecidingNextAction         -- Agent 판단 (Node: decide, with LLM)
  | RunningOcrStage2           -- 2단계 OCR 실행 (Node: run_ocr_stage2, Accurate)
  | ExtractingProblemsStage2   -- 2단계 문제 추출 (Node: extract_stage2)
  | ValidatingFinal            -- 최종 검증 (Node: validate_final)
  | GeneratingFiles            -- 파일 생성 (Node: generate_files)
  | CreatingZip                -- ZIP 패키징 (Node: create_zip)
  | Complete                   -- 완료 (END)
  | Failed String              -- 실패 (END)

||| Show agent state as string
public export
showAgentState : AgentState -> String
showAgentState Initial = "Initial"
showAgentState ConvertingPdf = "ConvertingPdf"
showAgentState DetectingLayout = "DetectingLayout"
showAgentState SeparatingColumns = "SeparatingColumns"
showAgentState RunningOcrStage1 = "RunningOcrStage1"
showAgentState ExtractingProblemsStage1 = "ExtractingProblemsStage1"
showAgentState ValidatingStage1 = "ValidatingStage1"
showAgentState DecidingNextAction = "DecidingNextAction"
showAgentState RunningOcrStage2 = "RunningOcrStage2"
showAgentState ExtractingProblemsStage2 = "ExtractingProblemsStage2"
showAgentState ValidatingFinal = "ValidatingFinal"
showAgentState GeneratingFiles = "GeneratingFiles"
showAgentState CreatingZip = "CreatingZip"
showAgentState Complete = "Complete"
showAgentState (Failed reason) = "Failed: " ++ reason

-- =============================================================================
-- State Transitions (LangGraph Edges)
-- =============================================================================

||| 유효한 Agent 상태 전환
|||
||| LangGraph에서 이것은 add_edge() 및 add_conditional_edges()에 해당합니다.
public export
data ValidTransition : AgentState -> AgentState -> Type where
  -- 순차 진행 (add_edge)
  StartConvert : ValidTransition Initial ConvertingPdf
  ConvertToLayout : ValidTransition ConvertingPdf DetectingLayout
  LayoutToSeparate : ValidTransition DetectingLayout SeparatingColumns
  SeparateToOcr1 : ValidTransition SeparatingColumns RunningOcrStage1
  Ocr1ToExtract1 : ValidTransition RunningOcrStage1 ExtractingProblemsStage1
  Extract1ToValidate1 : ValidTransition ExtractingProblemsStage1 ValidatingStage1
  Validate1ToDecide : ValidTransition ValidatingStage1 DecidingNextAction

  -- Agent 판단 후 분기 (add_conditional_edges)
  DecideToGenerate : ValidTransition DecidingNextAction GeneratingFiles  -- 성공 케이스
  DecideToOcr2 : ValidTransition DecidingNextAction RunningOcrStage2     -- Stage2 필요

  -- Stage2 경로 (add_edge)
  Ocr2ToExtract2 : ValidTransition RunningOcrStage2 ExtractingProblemsStage2
  Extract2ToValidateFinal : ValidTransition ExtractingProblemsStage2 ValidatingFinal
  ValidateFinalToGenerate : ValidTransition ValidatingFinal GeneratingFiles

  -- 파일 생성 및 완료 (add_edge)
  GenerateToZip : ValidTransition GeneratingFiles CreatingZip
  ZipToComplete : ValidTransition CreatingZip Complete

  -- 실패 (add_conditional_edges)
  AnyToFailed : (st : AgentState) -> (reason : String) -> ValidTransition st (Failed reason)

-- =============================================================================
-- Progress Tracking
-- =============================================================================

||| 각 상태별 진행률 매핑 (0-100)
public export
stateToProgress : AgentState -> Nat
stateToProgress Initial = 0
stateToProgress ConvertingPdf = 10
stateToProgress DetectingLayout = 20
stateToProgress SeparatingColumns = 30
stateToProgress RunningOcrStage1 = 40
stateToProgress ExtractingProblemsStage1 = 50
stateToProgress ValidatingStage1 = 60
stateToProgress DecidingNextAction = 65
stateToProgress RunningOcrStage2 = 70
stateToProgress ExtractingProblemsStage2 = 80
stateToProgress ValidatingFinal = 85
stateToProgress GeneratingFiles = 90
stateToProgress CreatingZip = 95
stateToProgress Complete = 100
stateToProgress (Failed _) = 0

||| 각 상태별 메시지 (OCR 엔진 이름은 런타임에 결정)
public export
stateToMessage : AgentState -> String
stateToMessage Initial = "대기 중"
stateToMessage ConvertingPdf = "PDF → 이미지 변환 중"
stateToMessage DetectingLayout = "레이아웃 감지 중"
stateToMessage SeparatingColumns = "컬럼 분리 중"
stateToMessage RunningOcrStage1 = "1단계 OCR 실행 중"  -- 런타임: "Tesseract OCR 실행 중"
stateToMessage ExtractingProblemsStage1 = "문제 추출 중 (1단계)"
stateToMessage ValidatingStage1 = "검증 중 (1단계)"
stateToMessage DecidingNextAction = "Agent 판단 중"
stateToMessage RunningOcrStage2 = "2단계 OCR 실행 중"  -- 런타임: "Mathpix OCR 실행 중"
stateToMessage ExtractingProblemsStage2 = "문제 추출 중 (2단계)"
stateToMessage ValidatingFinal = "최종 검증 중"
stateToMessage GeneratingFiles = "파일 생성 중"
stateToMessage CreatingZip = "ZIP 패키징 중"
stateToMessage Complete = "완료"
stateToMessage (Failed reason) = "실패: " ++ reason

-- =============================================================================
-- LangGraph State Schema
-- =============================================================================

||| LangGraph의 TypedDict에 해당하는 상태 스키마
|||
||| OcrExecutionResult는 System.Ocr.Interface에서 import
|||
||| Python 구현:
||| ```python
||| class ExtractionState(TypedDict):
|||     job_id: str
|||     pdf_path: str
|||     ocr_strategy: OcrStrategy
|||     current_state: str
|||     images: Optional[List[np.ndarray]]
|||     layouts: Optional[List[PageLayout]]
|||     ocr_stage1_result: Optional[OcrExecutionResult]
|||     ocr_stage2_result: Optional[OcrExecutionResult]
|||     detected_problems: List[int]
|||     expected_problems: Optional[List[int]]
|||     missing_problems: List[int]
|||     decision: Optional[str]
|||     output_dir: Optional[str]
|||     zip_path: Optional[str]
|||     progress: int
|||     message: str
|||     error: Optional[str]
||| ```
public export
record LangGraphState where
  constructor MkLangGraphState
  ||| Job ID (FastAPI Job과 연동)
  jobId : JobId
  ||| PDF 경로
  pdfPath : String
  ||| OCR 설정 (엔진 선택)
  ocrStrategy : OcrStrategy
  ||| 현재 Agent 상태
  currentState : AgentState
  ||| PDF 이미지들 (변환 후)
  images : Maybe (List String)  -- 이미지 경로 목록
  ||| 레이아웃 정보
  layouts : Maybe (List String)  -- 레이아웃 JSON 경로 목록
  ||| Stage1 OCR 결과 (엔진 독립적)
  ocrStage1 : Maybe OcrExecutionResult
  ||| Stage2 OCR 결과 (엔진 독립적)
  ocrStage2 : Maybe OcrExecutionResult
  ||| 최종 검출된 문제 번호들
  detectedProblems : List Nat
  ||| 기대하는 문제 번호들
  expectedProblems : Maybe (List Nat)
  ||| 누락된 문제 번호들
  missingProblems : List Nat
  ||| Agent 결정
  decision : Maybe String
  ||| 출력 디렉토리
  outputDir : Maybe String
  ||| ZIP 경로
  zipPath : Maybe String
  ||| 진행률 (0-100)
  progress : Nat
  ||| 현재 메시지
  message : String
  ||| 에러 메시지
  error : Maybe String

||| 초기 LangGraph 상태 생성
public export
initialLangGraphState : JobId -> String -> OcrStrategy -> LangGraphState
initialLangGraphState jid path strategy = MkLangGraphState
  { jobId = jid
  , pdfPath = path
  , ocrStrategy = strategy
  , currentState = Initial
  , images = Nothing
  , layouts = Nothing
  , ocrStage1 = Nothing
  , ocrStage2 = Nothing
  , detectedProblems = []
  , expectedProblems = Nothing
  , missingProblems = []
  , decision = Nothing
  , outputDir = Nothing
  , zipPath = Nothing
  , progress = 0
  , message = "대기 중"
  , error = Nothing
  }
