from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field

# =====================================================================
# T01: Policy Schema
# =====================================================================

class PolicyLevel(str, Enum):
    REQUIRED = "required"
    ADVISORY = "advisory"
    MANUAL_ONLY = "manual_only"

class PolicyCheck(BaseModel):
    id: str = Field(..., description="Unique identifier for the policy check")
    category: str = Field(..., description="Category of the policy check (e.g., security, docs, runnable)")
    level: PolicyLevel = Field(..., description="Level of the policy requirement")
    description: str = Field(..., description="Human-readable description of the policy")


# =====================================================================
# T02: Data Contracts for Review Stages
# =====================================================================

class RequestSource(str, Enum):
    SLACK = "slack"
    API = "api"
    CLI = "cli"

class ReviewRequest(BaseModel):
    review_id: str = Field(..., description="Unique identifier for this review request")
    repository_url: HttpUrl = Field(..., description="Git repository URL to review")
    source: RequestSource = Field(..., description="Source of the review request")
    requester: str = Field(..., description="Identifier of the user requesting the review")
    branch: Optional[str] = Field("main", description="Target branch to review")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context from requester")

class EvidenceItem(BaseModel):
    id: str = Field(..., description="Unique identifier for this evidence item")
    type: str = Field(..., description="Type of evidence (e.g., screenshot, log, stdout)")
    source_stage: str = Field(..., description="Stage that produced this evidence (e.g., web, cli)")
    payload: Dict[str, Any] = Field(..., description="The actual evidence data or references to storage")

class EvidenceBundle(BaseModel):
    review_id: str = Field(..., description="Associated review ID")
    items: List[EvidenceItem] = Field(default_factory=list, description="Collection of evidence gathered during review")

class PolicyCheckResult(BaseModel):
    policy: PolicyCheck
    passed: bool = Field(..., description="Whether the policy check passed")
    reasoning: str = Field(..., description="Explanation for why the policy passed or failed")
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of evidence items supporting this result")

class WebFlowResult(BaseModel):
    flow_id: str = Field(..., description="Identifier for this specific web interaction flow")
    success: bool = Field(..., description="Indicates if the web flow completed successfully")
    url_visited: HttpUrl = Field(..., description="The primary URL that was exercised")
    screenshots: List[str] = Field(default_factory=list, description="List of evidence item IDs for visual captures")
    console_errors: List[str] = Field(default_factory=list, description="JavaScript console errors encountered")
    duration_ms: int = Field(..., description="Execution time in milliseconds")

class CLICommandResult(BaseModel):
    command: str = Field(..., description="The shell command that was executed")
    exit_code: int = Field(..., description="Command exit code (e.g. 0 for success)")
    stdout_ref: Optional[str] = Field(None, description="Evidence ID pointing to standard output contents")
    stderr_ref: Optional[str] = Field(None, description="Evidence ID pointing to standard error contents")
    duration_ms: int = Field(..., description="Execution time in milliseconds")
    success: bool = Field(..., description="Whether the command succeeded based on exit code or heuristics")

class VerdictDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    ERROR = "error"

class FinalVerdict(BaseModel):
    review_id: str = Field(..., description="Associated review ID")
    decision: VerdictDecision = Field(..., description="The final outcome of the review")
    summary: str = Field(..., description="A high-level summary of the decision rationale")
    check_results: List[PolicyCheckResult] = Field(default_factory=list, description="Results of all evaluated policies")
    web_results: List[WebFlowResult] = Field(default_factory=list, description="Results from web automation stages")
    cli_results: List[CLICommandResult] = Field(default_factory=list, description="Results from CLI testing stages")
    report_url: Optional[str] = Field(None, description="Link or reference to the generated Typst/PDF artifact")
