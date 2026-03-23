#set document(
  title: "Shipwright Review Report",
  author: "Shipwright AI Reviewer",
)
#set page(margin: 1.5cm)
#set text(font: "Liberation Serif", size: 11pt)

= Shipwright Review Report

#grid(
  columns: (auto, 1fr),
  gutter: 0.5em,
  [*Review ID:*], [rev-cli-001],
  [*Repository:*], [https://github.com/test/clitool],
  [*Generated:*], [2026-03-23 15:15 UTC],
  [*Verdict:*], [*REJECT*],
)

---

== Summary

Rejected: 1 required check(s) failed. execution_success: No primary flow or command completed successfully.

---

== Policy Checklist

#table(
  columns: (1fr, auto, 2fr),
  [*Check*], [*Result*], [*Reason*],
  [repo_url_present], [✅], [Repository URL is present.],
  [project_type_supported], [✅], [Project type 'cli' is supported.],
  [readme_sufficient], [✅], [README is sufficient (281 chars, keywords: \['usage', 'install'\]).],
  [open_source_heuristic], [✅], [Repository appears to be on a public hosting platform.],
  [no_special_review_account], [✅], [No indication of a required special review account.],
  [not_previously_submitted], [✅], [Manual confirmation required; assumed OK pending human review.],
  [cli_commands_present], [✅], [1 CLI command(s) documented.],
  [execution_success], [❌], [No primary flow or command completed successfully.],
)

#if false [
  ---
  == Web Flow Results

  #table(
    columns: (1fr, auto, auto),
    [*Flow*], [*Success*], [*Duration (ms)*],
    [No web results], [], [],
  )
]

#if true [
  ---
  == CLI Command Results

  #table(
    columns: (2fr, auto, auto),
    [*Command*], [*Exit Code*], [*Duration (ms)*],
    [pip install mytool], [1], [4750],
  )
]

---

_This report was generated automatically by Shipwright AI Reviewer._
