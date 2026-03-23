# Task T02: Data Contracts

**Goal**: Define typed data contracts for all review stages (Pydantic models)

**Summary**:
Implemented typed data contracts for all review stages in `src/sw_reviewer/models.py`. 
Models implemented include:
- `ReviewRequest`
- `EvidenceBundle` and `EvidenceItem` 
- `PolicyCheckResult`
- `WebFlowResult`
- `CLICommandResult`
- `FinalVerdict`

These models structure the inputs and outputs of the various agents.
