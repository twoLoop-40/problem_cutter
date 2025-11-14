||| Agent Workflow Integration (LangGraph 기반)
|||
||| State + Decision + Tools를 통합한 전체 워크플로우
||| Python 구현: app/agents/workflow.py
|||
||| 핵심:
||| - LangGraph StateGraph 정의
||| - Node 함수 정의
||| - Edge 정의 (sequential + conditional)
||| - Checkpointing 지원

module System.Agent.Workflow

import System.Agent.State
import System.Agent.Decision
import System.Agent.Tools
import System.Ocr.Interface
import System.Ocr.Parser
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- Workflow Graph (LangGraph)
-- =============================================================================

||| LangGraph Node 함수 시그니처
|||
||| Python 구현:
||| ```python
||| def node_function(state: LangGraphState) -> LangGraphState:
|||     # 1. 입력 검증
|||     # 2. 도구 실행
|||     # 3. 상태 업데이트
|||     # 4. 진행률 업데이트
|||     return updated_state
||| ```
public export
NodeFunction : Type
NodeFunction = LangGraphState -> LangGraphState

||| LangGraph Conditional Edge 함수 시그니처
|||
||| Python 구현:
||| ```python
||| def conditional_edge(state: LangGraphState) -> str:
|||     # 상태를 보고 다음 노드 이름 반환
|||     if condition:
|||         return "next_node_name"
|||     else:
|||         return "alternative_node_name"
||| ```
public export
ConditionalEdge : Type
ConditionalEdge = LangGraphState -> String

-- =============================================================================
-- Workflow Definition
-- =============================================================================

||| LangGraph 워크플로우 정의
|||
||| Python 구현:
||| ```python
||| from langgraph.graph import StateGraph, END
|||
||| workflow = StateGraph(LangGraphState)
|||
||| # Add nodes
||| workflow.add_node("convert_pdf", convert_pdf_node)
||| workflow.add_node("detect_layout", detect_layout_node)
||| workflow.add_node("run_ocr_stage1", run_ocr_stage1_node)
||| workflow.add_node("validate_stage1", validate_stage1_node)
||| workflow.add_node("decide", decide_node)
||| workflow.add_node("run_ocr_stage2", run_ocr_stage2_node)
||| workflow.add_node("validate_final", validate_final_node)
||| workflow.add_node("generate_files", generate_files_node)
||| workflow.add_node("create_zip", create_zip_node)
|||
||| # Add edges
||| workflow.set_entry_point("convert_pdf")
||| workflow.add_edge("convert_pdf", "detect_layout")
||| workflow.add_edge("detect_layout", "run_ocr_stage1")
||| workflow.add_edge("run_ocr_stage1", "validate_stage1")
||| workflow.add_edge("validate_stage1", "decide")
|||
||| # Conditional edges
||| workflow.add_conditional_edges(
|||     "decide",
|||     decide_next_step,
|||     {
|||         "generate": "generate_files",
|||         "stage2": "run_ocr_stage2",
|||         "failed": END
|||     }
||| )
|||
||| workflow.add_edge("run_ocr_stage2", "validate_final")
||| workflow.add_edge("validate_final", "generate_files")
||| workflow.add_edge("generate_files", "create_zip")
||| workflow.add_edge("create_zip", END)
|||
||| # Compile
||| app = workflow.compile(checkpointer=MemorySaver())
||| ```
public export
record WorkflowGraph where
  constructor MkWorkflowGraph
  ||| 시작 노드
  entryPoint : String
  ||| 노드 목록
  nodes : List (String, NodeFunction)
  ||| Sequential 엣지 (A → B)
  edges : List (String, String)
  ||| Conditional 엣지 (A → decision → B/C/D)
  conditionalEdges : List (String, ConditionalEdge, List (String, String))

||| 기본 워크플로우 정의
public export
defaultWorkflow : WorkflowGraph
defaultWorkflow = MkWorkflowGraph
  { entryPoint = "convert_pdf"
  , nodes =
      [ ("convert_pdf", believe_me ())         -- TODO: 실제 구현
      , ("detect_layout", believe_me ())
      , ("run_ocr_stage1", believe_me ())
      , ("validate_stage1", believe_me ())
      , ("decide", believe_me ())
      , ("run_ocr_stage2", believe_me ())
      , ("validate_final", believe_me ())
      , ("generate_files", believe_me ())
      , ("create_zip", believe_me ())
      ]
  , edges =
      [ ("convert_pdf", "detect_layout")
      , ("detect_layout", "run_ocr_stage1")
      , ("run_ocr_stage1", "validate_stage1")
      , ("validate_stage1", "decide")
      , ("run_ocr_stage2", "validate_final")
      , ("validate_final", "generate_files")
      , ("generate_files", "create_zip")
      ]
  , conditionalEdges =
      [ ("decide", believe_me (), [("generate", "generate_files"), ("stage2", "run_ocr_stage2")])
      ]
  }

-- =============================================================================
-- Node Implementations (명세)
-- =============================================================================

||| Convert PDF Node
|||
||| Python 구현:
||| ```python
||| def convert_pdf_node(state: LangGraphState) -> LangGraphState:
|||     tool_result = convert_pdf_tool(state["pdf_path"])
|||
|||     if not tool_result.success:
|||         return {**state, "current_state": "Failed", "error": tool_result.error}
|||
|||     return {
|||         **state,
|||         "current_state": "DetectingLayout",
|||         "images": tool_result.value,
|||         "progress": 10,
|||         "message": "PDF → 이미지 변환 완료"
|||     }
||| ```
public export
data ConvertPdfNode : LangGraphState -> LangGraphState -> Type where
  MkConvertPdfNode :
    (inputState : LangGraphState) ->
    (outputState : LangGraphState) ->
    (inputState.currentState = Initial) ->
    (outputState.currentState = DetectingLayout) ->
    (outputState.progress = 10) ->
    ConvertPdfNode inputState outputState

||| Run OCR Node (Stage 1)
|||
||| Python 구현:
||| ```python
||| def run_ocr_stage1_node(state: LangGraphState) -> LangGraphState:
|||     engine_type = state["ocr_config"].stage1_engine
|||     parser_config = state["parser_config"]
|||
|||     tool_result = run_ocr_tool(state["images"], engine_type, parser_config)
|||
|||     if not tool_result.success:
|||         return {**state, "current_state": "Failed", "error": tool_result.error}
|||
|||     return {
|||         **state,
|||         "current_state": "ValidatingStage1",
|||         "ocr_stage1": tool_result.value,
|||         "detected_problems": tool_result.value.detected_problems,
|||         "progress": 50,
|||         "message": f"Stage1 OCR 완료 ({engine_type.name})"
|||     }
||| ```
public export
data RunOcrStage1Node : LangGraphState -> LangGraphState -> Type where
  MkRunOcrStage1Node :
    (inputState : LangGraphState) ->
    (outputState : LangGraphState) ->
    (result : OcrExecutionResult) ->
    (inputState.currentState = RunningOcrStage1) ->
    (outputState.currentState = ValidatingStage1) ->
    (outputState.ocrStage1 = Just result) ->
    (outputState.detectedProblems = result.detectedProblems) ->
    RunOcrStage1Node inputState outputState

||| Decide Node
|||
||| Python 구현:
||| ```python
||| def decide_node(state: LangGraphState) -> LangGraphState:
|||     decision = decide_next_action(
|||         state["detected_problems"],
|||         state["expected_problems"],
|||         DecisionStrategy.RULE_BASED  # 또는 LLM
|||     )
|||
|||     return {
|||         **state,
|||         "current_state": "DecidingNextAction",
|||         "decision": decision_to_edge(decision),
|||         "progress": 65,
|||         "message": "Agent 판단 완료"
|||     }
||| ```
public export
data DecideNode : LangGraphState -> LangGraphState -> Type where
  MkDecideNode :
    (inputState : LangGraphState) ->
    (outputState : LangGraphState) ->
    (decision : AgentDecision) ->
    (inputState.currentState = ValidatingStage1) ->
    (outputState.currentState = DecidingNextAction) ->
    (outputState.decision = Just (decisionToEdge decision)) ->
    DecideNode inputState outputState

-- =============================================================================
-- Conditional Edge Functions
-- =============================================================================

||| Decide Next Step Conditional Edge
|||
||| Python 구현:
||| ```python
||| def decide_next_step(state: LangGraphState) -> str:
|||     decision = state["decision"]
|||
|||     if decision == "proceed":
|||         return "generate"
|||     elif decision == "stage2":
|||         return "stage2"
|||     elif decision == "retry":
|||         return "run_ocr_stage1"  # 재시도
|||     else:
|||         return END
||| ```
public export
decideNextStep : ConditionalEdge
decideNextStep state =
  case state.decision of
    Nothing => "failed"
    Just "proceed" => "generate"
    Just "stage2" => "stage2"
    Just "retry" => "run_ocr_stage1"
    Just _ => "failed"

-- =============================================================================
-- Workflow Execution
-- =============================================================================

||| 워크플로우 실행
|||
||| Python 구현:
||| ```python
||| async def run_workflow(
|||     job_id: str,
|||     pdf_path: str,
|||     ocr_config: OcrConfig
||| ) -> LangGraphState:
|||     initial_state = initial_lang_graph_state(job_id, pdf_path, ocr_config)
|||
|||     # LangGraph 실행
|||     config = {"configurable": {"thread_id": job_id}}
|||     final_state = await app.ainvoke(initial_state, config)
|||
|||     return final_state
||| ```
public export
data WorkflowExecution : LangGraphState -> LangGraphState -> Type where
  MkExecution :
    (initialState : LangGraphState) ->
    (finalState : LangGraphState) ->
    (initialState.currentState = Initial) ->
    (finalState.currentState = Complete) ->
    WorkflowExecution initialState finalState

-- =============================================================================
-- Guarantees
-- =============================================================================

||| 워크플로우가 종료됨을 보장
public export
data WorkflowTerminates : LangGraphState -> Type where
  TerminatesInComplete :
    (state : LangGraphState) ->
    (state.currentState = Complete) ->
    WorkflowTerminates state

  TerminatesInFailed :
    (state : LangGraphState) ->
    (reason : String) ->
    (state.currentState = Failed reason) ->
    WorkflowTerminates state

||| 워크플로우 진행률이 증가함
public export
data ProgressIncreases : LangGraphState -> LangGraphState -> Type where
  MkProgressIncreases :
    (before : LangGraphState) ->
    (after : LangGraphState) ->
    (ValidTransition before.currentState after.currentState) ->
    (LTE before.progress after.progress = True) ->
    ProgressIncreases before after
