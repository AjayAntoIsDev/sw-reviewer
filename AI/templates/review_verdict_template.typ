// Shipwright AI Reviewer - Typst Report Template

#set page(margin: (x: 1.8cm, y: 1.8cm))
#set text(lang: "en", size: 10pt)

#let badge(verdict) = {
  if verdict == "approve" {
    block(fill: rgb("#e8f7ec"), inset: 8pt, radius: 6pt)[
      *VERDICT:* #text(fill: rgb("#1f7a3a"))[APPROVE]
    ]
  } else if verdict == "reject" {
    block(fill: rgb("#fdecec"), inset: 8pt, radius: 6pt)[
      *VERDICT:* #text(fill: rgb("#b42318"))[REJECT]
    ]
  } else {
    block(fill: rgb("#fff7e6"), inset: 8pt, radius: 6pt)[
      *VERDICT:* #text(fill: rgb("#b26b00"))[NEEDS HUMAN REVIEW]
    ]
  }
}

#let section_title(title) = [
  #v(0.8em)
  #text(weight: "bold", size: 12pt)[#title]
  #line(length: 100%)
  #v(0.3em)
]

#let kv(key, value) = [*#key:* #value]

= Shipwright AI Review Report

#badge("{{VERDICT}}")

#v(0.8em)
#grid(
  columns: (1fr, 1fr),
  gutter: 10pt,
  [#kv("Review ID", "{{REVIEW_ID}}")],
  [#kv("Project Type", "{{PROJECT_TYPE}}")],
  [#kv("Project Name", "{{PROJECT_NAME}}")],
  [#kv("Repository", "{{REPO_URL}}")],
  [#kv("Demo URL", "{{DEMO_URL}}")],
  [#kv("Generated At", "{{GENERATED_AT}}")],
)

#section_title("1) Verdict Summary")

{{VERDICT_SUMMARY}}

#section_title("2) Rule Checklist")

#table(
  columns: (20%, 15%, 65%),
  stroke: .4pt,
  table.header([*Rule*], [*Status*], [*Reason*]),
  {{CHECKLIST_ROWS}}
)

#section_title("3) Web Validation (Visible + README Flows)")

#table(
  columns: (35%, 12%, 13%, 40%),
  stroke: .4pt,
  table.header([*Flow*], [*Result*], [*Screenshots*], [*Notes*]),
  {{WEB_FLOW_ROWS}}
)

#section_title("4) CLI Validation")

#table(
  columns: (35%, 12%, 13%, 12%, 28%),
  stroke: .4pt,
  table.header([*Command/Step*], [*Result*], [*Exit*], [*Duration*], [*Notes*]),
  {{CLI_ROWS}}
)

#section_title("5) Screenshot Evidence Index")

#table(
  columns: (12%, 33%, 55%),
  stroke: .4pt,
  table.header([*ID*], [*Flow/Feature*], [*Path or URL*]),
  {{SCREENSHOT_ROWS}}
)

#section_title("6) Rejection Reasons / Risk Notes")

{{RISK_NOTES}}

#section_title("7) Suggested Feedback for Submitter")

{{SUBMITTER_FEEDBACK}}

#section_title("8) Artifact Bundle")

- JSON verdict: {{VERDICT_JSON_PATH}}
- Typst source: {{TYP_SOURCE_PATH}}
- PDF output: {{PDF_PATH}}
- Additional logs: {{LOG_PATHS}}
