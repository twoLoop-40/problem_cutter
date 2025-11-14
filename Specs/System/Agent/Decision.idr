||| Agent Decision Logic
|||
||| LangGraph의 conditional_edges에서 사용되는 판단 로직
||| Python 구현: app/agents/decision.py
|||
||| 핵심:
||| - LLM 기반 판단 (Claude, GPT 등)
||| - 규칙 기반 fallback
||| - 비용 최적화 전략

module System.Agent.Decision

import System.Agent.State
import System.Ocr.Interface
import Data.Nat
import Data.List

%default total

-- =============================================================================
-- Decision Types
-- =============================================================================

||| Agent의 판단 결과
|||
||| LangGraph conditional_edges의 반환값
public export
data AgentDecision
  = ProceedToFileGeneration            -- Stage1 결과만으로 충분 → 파일 생성
  | UseStage2Ocr (List Nat)            -- 누락 문제를 Stage2 OCR로 재추출
  | RetryStage1 (List String)          -- Stage1 파라미터 조정 후 재시도
  | AbortWithError String              -- 오류로 중단

||| Decision을 문자열로 변환 (LangGraph edge name)
public export
decisionToEdge : AgentDecision -> String
decisionToEdge ProceedToFileGeneration = "generate"
decisionToEdge (UseStage2Ocr _) = "stage2"
decisionToEdge (RetryStage1 _) = "retry"
decisionToEdge (AbortWithError _) = "failed"

-- =============================================================================
-- Decision Strategy (확장 가능)
-- =============================================================================

||| 판단 전략
|||
||| - RuleBased: 규칙 기반 (빠름, 저렴)
||| - LlmBased: LLM 기반 (느림, 비쌈, 정확)
||| - Hybrid: 규칙 + LLM (균형)
public export
data DecisionStrategy
  = RuleBased                           -- 규칙만 사용
  | LlmBased String                     -- LLM 모델 (예: "claude-3-5-sonnet")
  | Hybrid String (List String)         -- LLM + 규칙 (규칙 우선)

||| 규칙 기반 판단 기준
|||
||| 누락 문제 수에 따른 전략:
||| - 0개: 모두 성공 → 파일 생성
||| - 1-3개: Stage2 OCR 사용 (비용 효율적)
||| - 4개 이상: Stage2 OCR 사용 (또는 재시도)
public export
ruleBasedDecision : (detected : List Nat) -> (expected : List Nat) -> AgentDecision
ruleBasedDecision detected expected =
  let missing = filter (\n => not (elem n detected)) expected
  in case length missing of
       Z => ProceedToFileGeneration
       (S Z) => UseStage2Ocr missing
       (S (S Z)) => UseStage2Ocr missing
       (S (S (S Z))) => UseStage2Ocr missing
       _ => UseStage2Ocr missing  -- 4개 이상도 Stage2 시도

-- =============================================================================
-- LLM Decision Prompt Template
-- =============================================================================

||| LLM에게 제공할 컨텍스트
public export
record DecisionContext where
  constructor MkDecisionContext
  totalExpected : Nat              -- 기대 문제 수
  stage1Detected : List Nat        -- Stage1 검출 결과
  stage1Engine : OcrEngineType     -- Stage1 엔진
  stage1Confidence : Double        -- Stage1 신뢰도
  stage2Available : Bool           -- Stage2 사용 가능 여부
  stage2Engine : OcrEngineType     -- Stage2 엔진
  costBudget : Maybe Nat           -- 비용 예산 (센트)

||| LLM 판단을 위한 프롬프트 생성
|||
||| Python에서 구현:
||| ```python
||| def generate_decision_prompt(context: DecisionContext) -> str:
|||     return f"""
|||     You are an OCR quality assessment agent.
|||
|||     Context:
|||     - Expected problems: {context.total_expected}
|||     - Stage1 ({context.stage1_engine}) detected: {context.stage1_detected}
|||     - Stage1 confidence: {context.stage1_confidence}
|||     - Missing: {context.missing}
|||     - Stage2 available: {context.stage2_available} ({context.stage2_engine})
|||     - Cost budget: {context.cost_budget} cents
|||
|||     Decision options:
|||     1. "proceed" - Use Stage1 results (missing problems acceptable)
|||     2. "stage2" - Use Stage2 for missing problems
|||     3. "retry" - Retry Stage1 with adjusted parameters
|||     4. "abort" - Abort due to unrecoverable errors
|||
|||     Please decide and explain your reasoning.
|||     """
||| ```
public export
generatePromptContext : DecisionContext -> String
generatePromptContext ctx =
  "Expected: " ++ show ctx.totalExpected ++
  ", Stage1(" ++ engineTypeName ctx.stage1Engine ++ "): " ++ show (length ctx.stage1Detected) ++
  " detected, confidence: " ++ show ctx.stage1Confidence

-- =============================================================================
-- Decision Function (통합)
-- =============================================================================

||| Agent 판단 함수 (전략에 따라 분기)
|||
||| Python 구현:
||| ```python
||| def decide_next_action(
|||     state: LangGraphState,
|||     strategy: DecisionStrategy
||| ) -> AgentDecision:
|||     if strategy == DecisionStrategy.RULE_BASED:
|||         return rule_based_decision(state)
|||     elif strategy == DecisionStrategy.LLM_BASED:
|||         return llm_based_decision(state, strategy.model)
|||     else:
|||         return hybrid_decision(state, strategy.model, strategy.rules)
||| ```
public export
decideNextAction :
  (detected : List Nat) ->
  (expected : List Nat) ->
  (strategy : DecisionStrategy) ->
  AgentDecision
decideNextAction detected expected RuleBased =
  ruleBasedDecision detected expected
decideNextAction detected expected (LlmBased model) =
  -- LLM 판단은 Python에서 구현 (외부 API 호출)
  ruleBasedDecision detected expected  -- fallback
decideNextAction detected expected (Hybrid model rules) =
  -- Hybrid: 규칙 먼저, 복잡하면 LLM
  let missing = filter (\n => not (elem n detected)) expected
  in if length missing <= 3
       then ruleBasedDecision detected expected
       else ruleBasedDecision detected expected  -- LLM fallback

-- =============================================================================
-- Guarantees (보장 사항)
-- =============================================================================

||| Stage1이 항상 먼저 실행됨을 보장
public export
data Stage1First : LangGraphState -> Type where
  MkStage1First :
    (st : LangGraphState) ->
    (result : OcrExecutionResult) ->
    (st.currentState = RunningOcrStage2) ->
    (st.ocrStage1 = Just result) ->
    Stage1First st

||| Stage2는 누락 문제가 있을 때만 실행
public export
data Stage2OnlyWhenNeeded : LangGraphState -> Type where
  MkStage2OnlyWhenNeeded :
    (st : LangGraphState) ->
    (result : OcrExecutionResult) ->
    (st.currentState = RunningOcrStage2) ->
    (expected : List Nat) ->
    (detected : List Nat) ->
    (st.expectedProblems = Just expected) ->
    (st.ocrStage1 = Just result) ->
    (length (filter (\n => not (elem n detected)) expected) > 0 = True) ->
    Stage2OnlyWhenNeeded st

||| 완료 시 모든 문제 검출 보장 (또는 부분 성공)
public export
data AllProblemsDetectedOrPartialSuccess : LangGraphState -> Type where
  AllDetected :
    (st : LangGraphState) ->
    (expected : List Nat) ->
    (st.currentState = Complete) ->
    (st.expectedProblems = Just expected) ->
    (st.detectedProblems = expected) ->
    AllProblemsDetectedOrPartialSuccess st

  PartialSuccess :
    (st : LangGraphState) ->
    (expected : List Nat) ->
    (detected : List Nat) ->
    (st.currentState = Complete) ->
    (st.expectedProblems = Just expected) ->
    (st.detectedProblems = detected) ->
    (length detected > 0 = True) ->
    AllProblemsDetectedOrPartialSuccess st
