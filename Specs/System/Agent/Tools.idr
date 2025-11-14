||| Agent Tools (LangGraph Node Functions) - OCR 독립적 설계
|||
||| 각 LangGraph Node에서 사용하는 도구 정의
||| Python 구현: app/agents/tools.py
|||
||| 핵심 설계:
||| - OCR 엔진 독립적 (OcrExecutor 추상화 사용)
||| - 각 도구는 독립적으로 실행 가능
||| - 입력/출력이 명확히 정의됨
||| - 실패 시 재시도 가능

module System.Agent.Tools

import System.Agent.State
import System.Agent.Decision
import System.Ocr.Interface
import System.Ocr.Parser
import System.Base
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- Tool Result Types
-- =============================================================================

||| 도구 실행 결과
|||
||| 모든 도구는 이 타입을 반환
public export
record ToolResult (a : Type) where
  constructor MkToolResult
  success : Bool
  value : Maybe a
  error : Maybe String
  duration : Nat  -- 실행 시간 (초)

||| 성공 결과 생성
public export
succeed : a -> Nat -> ToolResult a
succeed val dur = MkToolResult True (Just val) Nothing dur

||| 실패 결과 생성
public export
fail : String -> Nat -> ToolResult a
fail err dur = MkToolResult False Nothing (Just err) dur

-- =============================================================================
-- Tool Definitions (OCR 독립적)
-- =============================================================================

||| PDF → 이미지 변환 도구
|||
||| Python 구현:
||| ```python
||| def convert_pdf_tool(state: LangGraphState) -> ToolResult:
|||     images = pdf_to_images(state["pdf_path"], dpi=300)
|||     return succeed(images, duration=5)
||| ```
public export
data ConvertPdfTool : Type where
  MkConvertPdfTool :
    (input : String) ->              -- PDF 경로
    (output : ToolResult (List String)) ->  -- 이미지 경로 목록
    ConvertPdfTool

||| 레이아웃 감지 도구
|||
||| Python 구현:
||| ```python
||| def detect_layout_tool(state: LangGraphState) -> ToolResult:
|||     detector = LayoutDetector()
|||     layouts = [detector.detect_layout(img) for img in state["images"]]
|||     return succeed(layouts, duration=2)
||| ```
public export
data DetectLayoutTool : Type where
  MkDetectLayoutTool :
    (input : List String) ->         -- 이미지 경로 목록
    (output : ToolResult (List String)) ->  -- 레이아웃 JSON 경로
    DetectLayoutTool

||| OCR 실행 도구 (엔진 독립적)
|||
||| 핵심: OCR 엔진 세부사항을 모름. OcrExecutor를 통해 실행만 함
|||
||| Python 구현:
||| ```python
||| def run_ocr_tool(
|||     state: LangGraphState,
|||     engine_type: OcrEngineType
||| ) -> ToolResult:
|||     # OcrExecutor가 엔진별 차이를 처리
|||     executor = OcrExecutorRegistry.get(engine_type)
|||
|||     ocr_input = OcrInput(
|||         image_path=state["images"][0],
|||         languages=["kor", "eng"],
|||         dpi=300
|||     )
|||
|||     ocr_output = executor.execute(ocr_input)
|||
|||     # Parser가 문제 번호 추출
|||     parsing_result = parse_markers(ocr_output, state["parser_config"])
|||
|||     return succeed(OcrExecutionResult(
|||         engine=engine_type,
|||         detected_problems=parsing_result.problem_numbers,
|||         confidence=ocr_output.average_confidence,
|||         execution_time=ocr_output.execution_time,
|||         raw_output=ocr_output
|||     ), duration=ocr_output.execution_time)
||| ```
public export
data RunOcrTool : Type where
  MkRunOcrTool :
    (engineType : OcrEngineType) ->
    (input : List String) ->         -- 이미지 경로 목록
    (parserConfig : ParserConfig) ->
    (output : ToolResult OcrExecutionResult) ->
    RunOcrTool

||| 검증 도구
|||
||| Python 구현:
||| ```python
||| def validate_tool(
|||     detected: List[int],
|||     expected: List[int]
||| ) -> ToolResult:
|||     missing = [n for n in expected if n not in detected]
|||     return succeed(missing, duration=0)
||| ```
public export
data ValidateTool : Type where
  MkValidateTool :
    (detected : List Nat) ->
    (expected : List Nat) ->
    (missing : ToolResult (List Nat)) ->
    ValidateTool

||| 판단 도구 (LLM 포함 가능)
|||
||| Python 구현:
||| ```python
||| def decide_tool(
|||     state: LangGraphState,
|||     strategy: DecisionStrategy
||| ) -> ToolResult:
|||     decision = decide_next_action(
|||         state["detected_problems"],
|||         state["expected_problems"],
|||         strategy
|||     )
|||     return succeed(decision, duration=2)
||| ```
public export
data DecideTool : Type where
  MkDecideTool :
    (detected : List Nat) ->
    (expected : List Nat) ->
    (strategy : DecisionStrategy) ->
    (decision : ToolResult AgentDecision) ->
    DecideTool

||| 파일 생성 도구
|||
||| Python 구현:
||| ```python
||| def generate_files_tool(state: LangGraphState) -> ToolResult:
|||     save_problem_images(
|||         state["images"],
|||         state["detected_problems"],
|||         state["output_dir"]
|||     )
|||     return succeed(state["output_dir"], duration=5)
||| ```
public export
data GenerateFilesTool : Type where
  MkGenerateFilesTool :
    (images : List String) ->
    (problems : List Nat) ->
    (outputDir : String) ->
    (result : ToolResult String) ->
    GenerateFilesTool

||| ZIP 생성 도구
|||
||| Python 구현:
||| ```python
||| def create_zip_tool(state: LangGraphState) -> ToolResult:
|||     zip_path = create_zip(state["output_dir"])
|||     return succeed(zip_path, duration=2)
||| ```
public export
data CreateZipTool : Type where
  MkCreateZipTool :
    (inputDir : String) ->
    (zipPath : ToolResult String) ->
    CreateZipTool

-- =============================================================================
-- Tool Registry (확장 가능)
-- =============================================================================

||| 사용 가능한 모든 도구 목록
|||
||| OCR 엔진별 도구가 아니라, 기능별 도구
public export
data ToolType
  = ConvertPdfToolType
  | DetectLayoutToolType
  | RunOcrToolType           -- 엔진 타입은 파라미터로
  | ValidateToolType
  | DecideToolType
  | GenerateFilesToolType
  | CreateZipToolType

||| 도구 이름 (LangGraph Node 이름)
public export
toolName : ToolType -> String
toolName ConvertPdfToolType = "convert_pdf"
toolName DetectLayoutToolType = "detect_layout"
toolName RunOcrToolType = "run_ocr"           -- 엔진 독립적
toolName ValidateToolType = "validate"
toolName DecideToolType = "decide"
toolName GenerateFilesToolType = "generate_files"
toolName CreateZipToolType = "create_zip"

-- =============================================================================
-- Tool Execution Guarantees
-- =============================================================================

||| 도구 실행 시 입력이 유효함을 보장
public export
data ValidToolInput : ToolType -> Type where
  ValidConvertPdfInput :
    (path : String) ->
    (length path > 0 = True) ->
    ValidToolInput ConvertPdfToolType

  ValidRunOcrInput :
    (images : List String) ->
    (length images > 0 = True) ->
    ValidToolInput RunOcrToolType

  ValidValidateInput :
    (detected : List Nat) ->
    (expected : List Nat) ->
    (length expected > 0 = True) ->
    ValidToolInput ValidateToolType

||| 도구 실행 결과가 유효함을 보장
public export
data ValidToolOutput : (t : ToolType) -> ToolResult a -> Type where
  ValidOutput :
    (result : ToolResult a) ->
    (result.success = True) ->
    (result.value = Just val) ->
    ValidToolOutput t result

  ValidError :
    (result : ToolResult a) ->
    (result.success = False) ->
    (result.error = Just err) ->
    ValidToolOutput t result
