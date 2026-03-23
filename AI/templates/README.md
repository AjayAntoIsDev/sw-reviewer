# Templates

## Typst verdict report

Use [review_verdict_template.typ](review_verdict_template.typ) as the canonical report template.

### Required placeholder fields

- `{{VERDICT}}`
- `{{REVIEW_ID}}`
- `{{PROJECT_TYPE}}`
- `{{PROJECT_NAME}}`
- `{{REPO_URL}}`
- `{{DEMO_URL}}`
- `{{GENERATED_AT}}`
- `{{VERDICT_SUMMARY}}`
- `{{CHECKLIST_ROWS}}`
- `{{WEB_FLOW_ROWS}}`
- `{{CLI_ROWS}}`
- `{{SCREENSHOT_ROWS}}`
- `{{RISK_NOTES}}`
- `{{SUBMITTER_FEEDBACK}}`
- `{{VERDICT_JSON_PATH}}`
- `{{TYP_SOURCE_PATH}}`
- `{{PDF_PATH}}`
- `{{LOG_PATHS}}`

### Expected evidence quality

- Every visible, user-testable feature has screenshot evidence.
- Every README-documented feature has screenshot evidence (web) or command evidence (CLI).
- Verdict section must map directly to checklist results.
