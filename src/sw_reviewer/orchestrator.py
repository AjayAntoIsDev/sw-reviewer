import asyncio
from typing import Any, Dict, Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.gemini import GeminiModel

from sw_reviewer.models import ReviewRequest, FinalVerdict, VerdictDecision
from sw_reviewer.state import JobRepository, JobStatus, JobState

# We use Gemini 3.1 Pro Preview as instructed by the main agent
# Using pydantic-ai's GeminiModel
model = GeminiModel("gemini-3.1-pro-preview")

# The Orchestrator agent handles routing to correct stages
orchestrator_agent = Agent(
    model,
    system_prompt=(
        "You are the main orchestrator agent for the Shipwright AI Reviewer. "
        "Your job is to route the review request through different functional stages: "
        "Web testing, CLI testing, and Policy evaluation. "
        "Analyze the repository and determine which checks to run, then invoke the necessary tools. "
        "Finally, synthesize the results into a final verdict."
    ),
    deps_type=JobState, # Use the JobState as dependency so tools can access and update state
)

class StageRouter:
    """Manages the lifecycle and routing of a review job through various stages."""
    
    def __init__(self, db_path: str = "reviewer_state.db"):
        self.repo = JobRepository(db_path)

    async def start_review(self, request: ReviewRequest) -> JobState:
        """Initializes the job in the database and kicks off the orchestration process."""
        job = JobState(
            review_id=request.review_id,
            status=JobStatus.PENDING,
            repository_url=str(request.repository_url),
            context_data={"metadata": request.metadata, "branch": request.branch}
        )
        self.repo.create_job(job)
        return await self.run_pipeline(job.review_id)
        
    async def run_pipeline(self, review_id: str) -> JobState:
        """Executes the pipeline stages sequentially or via the orchestrator agent."""
        job = self.repo.get_job(review_id)
        if not job:
            raise ValueError(f"Job {review_id} not found.")

        try:
            self.repo.update_job_status(review_id, JobStatus.RUNNING)
            job = self.repo.get_job(review_id) # Refresh state
            
            # 1. Pydantic-AI Orchestrator Execution
            # The agent will decide what to do and call stage tools.
            # Here we just pass the job state as a dependency to the agent.
            result = await orchestrator_agent.run(
                f"Begin review for repository: {job.repository_url}. "
                "Execute web and CLI tests according to policies, then formulate a verdict.",
                deps=job
            )
            
            # 2. Store result and finish
            self.repo.save_context(review_id, {"final_thought": result.data})
            self.repo.update_job_status(review_id, JobStatus.COMPLETED)
            
        except Exception as e:
            self.repo.update_job_status(review_id, JobStatus.FAILED, error_message=str(e))
            
        return self.repo.get_job(review_id)

# ---------------------------------------------------------------------
# Pydantic-AI Tools (Stage Hooks)
# These represent the sub-agents/stages that the orchestrator can call
# ---------------------------------------------------------------------

@orchestrator_agent.tool
async def run_web_testing_stage(ctx: RunContext[JobState]) -> str:
    """Trigger the web testing stage (UI validation, visual captures)."""
    job = ctx.deps
    repo = JobRepository() # In real-world, we'd pass the existing repo connection
    repo.update_job_status(job.review_id, JobStatus.WEB_TESTING)
    
    # Mocking web test work...
    await asyncio.sleep(1)
    
    repo.update_job_status(job.review_id, JobStatus.RUNNING)
    return "Web testing stage completed successfully. No critical UI errors."

@orchestrator_agent.tool
async def run_cli_testing_stage(ctx: RunContext[JobState]) -> str:
    """Trigger the CLI sandbox testing stage (README commands, docker isolation)."""
    job = ctx.deps
    repo = JobRepository()
    repo.update_job_status(job.review_id, JobStatus.CLI_TESTING)
    
    # Mocking CLI test work...
    await asyncio.sleep(1)
    
    repo.update_job_status(job.review_id, JobStatus.RUNNING)
    return "CLI testing stage completed successfully. Exit code 0."

@orchestrator_agent.tool
async def run_policy_eval_stage(ctx: RunContext[JobState], evidence_summary: str) -> FinalVerdict:
    """Trigger the policy evaluation stage to finalize the verdict."""
    job = ctx.deps
    repo = JobRepository()
    repo.update_job_status(job.review_id, JobStatus.POLICY_EVAL)
    
    # Mocking Policy eval work...
    await asyncio.sleep(1)
    
    repo.update_job_status(job.review_id, JobStatus.RUNNING)
    return FinalVerdict(
        review_id=job.review_id,
        decision=VerdictDecision.APPROVE,
        summary="All mandatory checks passed. " + evidence_summary,
        check_results=[],
        web_results=[],
        cli_results=[],
        report_url=None
    )
