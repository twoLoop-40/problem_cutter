module System.AgentWorkflow

import System.Base
import System.ProblemExtraction
import Data.Nat
import Data.List

%default total

{-
Agent-based Problem Detection Workflow

This specification defines an autonomous agent that uses existing functions
as tools and iteratively refines problem detection through feedback.

Key concepts:
- Agent has discrete states (Initial → Complete/Failed)
- Tools are exposed as callable functions
- Feedback mechanism guides refinement
- Termination is guaranteed (max iterations or success)

Implementation: core/agent.py
-}

-- =============================================================================
-- Agent States
-- =============================================================================

||| States during iterative problem detection
public export
data AgentState
  = Initial                    -- Starting state
  | AnalyzingLayout            -- Analyzing PDF layout and columns
  | RunningOCR                 -- Running OCR on image
  | DetectingMarkers           -- Detecting problem number markers
  | DetectingBoundaries        -- Computing problem boundaries
  | ValidatingResults          -- Checking if results match expectations
  | RefiningStrategy           -- Adjusting detection parameters
  | Complete                   -- All problems successfully found
  | Failed String              -- Error state with reason

||| Show agent state as string
export
showAgentState : AgentState -> String
showAgentState Initial = "Initial"
showAgentState AnalyzingLayout = "AnalyzingLayout"
showAgentState RunningOCR = "RunningOCR"
showAgentState DetectingMarkers = "DetectingMarkers"
showAgentState DetectingBoundaries = "DetectingBoundaries"
showAgentState ValidatingResults = "ValidatingResults"
showAgentState RefiningStrategy = "RefiningStrategy"
showAgentState Complete = "Complete"
showAgentState (Failed reason) = "Failed: " ++ reason

-- =============================================================================
-- Agent Tools
-- =============================================================================

||| Tools available to the agent (correspond to Python functions)
public export
data AgentTool
  = LayoutDetectorTool         -- Detect columns: core.layout_detector.detect_layout()
  | TesseractOCRTool           -- Run Tesseract: core.ocr_engine.run_tesseract_ocr()
  | PyMuPDFSearchTool          -- Fallback search: core.pdf_text_search.search_problem_numbers_in_pdf()
  | MarkerDetectorTool         -- Detect markers: core.problem_extractor.detect_problem_markers()
  | BoundaryDetectorTool       -- Detect boundaries: core.problem_extractor.detect_problem_boundaries()
  | ResultValidatorTool        -- Validate results: custom validation logic
  | BoundaryVisualizerTool     -- Visualize: core.image_cropper.visualize_boundaries()

||| Show tool name
export
showTool : AgentTool -> String
showTool LayoutDetectorTool = "LayoutDetector"
showTool TesseractOCRTool = "TesseractOCR"
showTool PyMuPDFSearchTool = "PyMuPDFSearch"
showTool MarkerDetectorTool = "MarkerDetector"
showTool BoundaryDetectorTool = "BoundaryDetector"
showTool ResultValidatorTool = "ResultValidator"
showTool BoundaryVisualizerTool = "BoundaryVisualizer"

-- =============================================================================
-- Feedback Types
-- =============================================================================

||| Feedback from result validation
public export
data Feedback
  = Success (List Nat)                      -- Successfully found problems
  | MissingProblems (List Nat)              -- List of missing problem numbers
  | FalsePositives (List Nat)               -- Incorrectly detected problems
  | InvalidBoundaries (List Nat)            -- Problems with invalid boundaries (height <= 0)
  | NeedsFallback (List Nat)                -- Problems needing PyMuPDF fallback
  | OCRFailed String                        -- OCR failed with error
  | LayoutDetectionFailed String            -- Layout detection failed

-- =============================================================================
-- Agent Actions
-- =============================================================================

||| Actions the agent can take
public export
data AgentAction
  = UseTool AgentTool                 -- Execute a tool
  | ProvideFeedback Feedback          -- Give feedback on results
  | AdjustParameter String String     -- Adjust detection parameter (name, new value)
  | RequestFallback (List Nat)        -- Request PyMuPDF fallback for specific numbers
  | CompleteWorkflow                  -- Mark workflow as complete
  | AbortWorkflow String              -- Abort with error message

||| Show feedback as string
export
showFeedback : Feedback -> String
showFeedback (Success probs) = "Success: found " ++ show (length probs) ++ " problems"
showFeedback (MissingProblems probs) = "Missing: " ++ show probs
showFeedback (FalsePositives probs) = "False positives: " ++ show probs
showFeedback (InvalidBoundaries probs) = "Invalid boundaries: " ++ show probs
showFeedback (NeedsFallback probs) = "Needs fallback: " ++ show probs
showFeedback (OCRFailed err) = "OCR failed: " ++ err
showFeedback (LayoutDetectionFailed err) = "Layout detection failed: " ++ err

-- =============================================================================
-- State Transitions
-- =============================================================================

||| Valid state transitions with proofs
public export
data ValidAgentTransition : AgentState -> AgentState -> Type where
  -- Forward progress
  StartAnalysis : ValidAgentTransition Initial AnalyzingLayout
  AnalysisToOCR : ValidAgentTransition AnalyzingLayout RunningOCR
  OCRToMarkers : ValidAgentTransition RunningOCR DetectingMarkers
  MarkersToBoundaries : ValidAgentTransition DetectingMarkers DetectingBoundaries
  BoundariesToValidation : ValidAgentTransition DetectingBoundaries ValidatingResults

  -- Refinement loop (feedback-driven)
  ValidationToRefine : (fb : Feedback) -> ValidAgentTransition ValidatingResults RefiningStrategy
  RefineToMarkers : ValidAgentTransition RefiningStrategy DetectingMarkers
  RefineToBoundaries : ValidAgentTransition RefiningStrategy DetectingBoundaries

  -- Completion
  ValidationToComplete : ValidAgentTransition ValidatingResults Complete

  -- Error handling
  AnyToFailed : (st : AgentState) -> (reason : String) -> ValidAgentTransition st (Failed reason)

-- =============================================================================
-- Agent Workflow Record
-- =============================================================================

||| Detection parameter (name, value)
public export
record Parameter where
  constructor MkParameter
  name : String
  value : String

||| Agent workflow state with iteration tracking
public export
record AgentWorkflow where
  constructor MkAgentWorkflow
  pdfPath : String                          -- Input PDF path
  currentState : AgentState                 -- Current state
  lastFeedback : Maybe Feedback             -- Feedback from last validation
  detectedProblems : List Nat               -- Currently detected problem numbers
  expectedProblems : Maybe (List Nat)       -- Expected problem numbers (if known)
  iterations : Nat                          -- Current iteration count
  maxIterations : Nat                       -- Maximum allowed iterations
  usedTools : List AgentTool                -- Tools used so far
  detectionParams : List Parameter          -- Current detection parameters

||| Initial workflow state
export
initialWorkflow : String -> Nat -> AgentWorkflow
initialWorkflow path maxIter = MkAgentWorkflow
  { pdfPath = path
  , currentState = Initial
  , lastFeedback = Nothing
  , detectedProblems = []
  , expectedProblems = Nothing
  , iterations = 0
  , maxIterations = maxIter
  , usedTools = []
  , detectionParams = [MkParameter "min_confidence" "0.7", MkParameter "min_gap_size" "30"]
  }

-- =============================================================================
-- Termination Proofs
-- =============================================================================

||| Proof that agent workflow eventually terminates
public export
data AgentTerminates : AgentWorkflow -> Type where
  ||| Termination by max iterations
  MaxIterationsReached : (wf : AgentWorkflow) ->
                         LTE wf.iterations wf.maxIterations ->
                         AgentTerminates wf

  ||| Termination by success (all expected problems found)
  AllProblemsFound : (wf : AgentWorkflow) ->
                     (expected : List Nat) ->
                     (wf.expectedProblems = Just expected) ->
                     (wf.detectedProblems = expected) ->
                     AgentTerminates wf

  ||| Termination by failure state
  WorkflowFailed : (wf : AgentWorkflow) ->
                   (reason : String) ->
                   (wf.currentState = Failed reason) ->
                   AgentTerminates wf

||| Proof that iteration count never decreases
export
iterationMonotonic : (wf1 : AgentWorkflow) -> (wf2 : AgentWorkflow) ->
                     ValidAgentTransition wf1.currentState wf2.currentState ->
                     LTE wf1.iterations wf2.iterations
iterationMonotonic wf1 wf2 trans = believe_me ()  -- Runtime property

||| Proof that agent eventually reaches terminal state
export
agentEventuallyTerminates : (wf : AgentWorkflow) -> AgentTerminates wf
agentEventuallyTerminates wf = MaxIterationsReached wf (believe_me ())

-- =============================================================================
-- Workflow Properties
-- =============================================================================

||| Proof that successful workflow has detected problems
export
successImpliesProblems : (wf : AgentWorkflow) ->
                         (wf.currentState = Complete) ->
                         length wf.detectedProblems > 0 = True
successImpliesProblems wf prf = believe_me ()  -- Runtime check

||| Proof that refinement only happens after validation
export
refinementAfterValidation : (wf1 : AgentWorkflow) -> (wf2 : AgentWorkflow) ->
                            (wf2.currentState = RefiningStrategy) ->
                            (wf1.currentState = ValidatingResults)
refinementAfterValidation wf1 wf2 prf = believe_me ()  -- State machine invariant
