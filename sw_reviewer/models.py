from __future__ import annotations
from pydantic import BaseModel
from enum import Enum

class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail" 
    WARN = "warn"
    SKIP = "skip"

class PreCheckResult(BaseModel):
    """Output of the pre-check stage."""
    detected_project_type: str
    api_given_type: str | None = None
    repo_url: str
    repo_accessible: bool
    readme_exists: bool
    demo_url: str | None = None
    demo_url_reachable: bool | None = None
    is_school_project: bool = False
    is_business_project: bool = False
    is_hackclub_inspired: bool = True
    resubmission_count: int = 0
    demo_url_flags: list[str] | None = None
    instant_reject: bool = False
    reject_reason: str | None = None

class CheckResult(BaseModel):
    """A single check's outcome."""
    status: CheckStatus
    details: str

class ChecksResult(BaseModel):
    """Output of the checks stage."""
    readme_is_raw_github: CheckResult
    readme_matches_repo: CheckResult
    repo_link_valid: CheckResult
    pre_flavortown_commits: CheckResult
    ai_detection: CheckResult
    commit_authorship: CheckResult
    readme_boilerplate: CheckResult
    readme_substance: CheckResult
    demo_validity: CheckResult
    demo_credentials: CheckResult
    api_key_exposure: CheckResult
    description_accuracy: CheckResult
    demo_link_type: CheckResult

class ReviewVerdict(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    FLAG_FOR_HUMAN = "FLAG_FOR_HUMAN"

class ReviewResult(BaseModel):
    """Final output of the reviewer stage."""
    verdict: ReviewVerdict
    project_type: str
    checks_performed: list[str]
    reasoning: str
    required_fixes: list[str] | None = None
    feedback: list[str] | None = None
    special_flags: list[str] | None = None
