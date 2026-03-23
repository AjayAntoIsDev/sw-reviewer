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
  [*Review ID:*], [rev-web-001],
  [*Repository:*], [https://github.com/test/webapp],
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
  [project_type_supported], [✅], [Project type 'web' is supported.],
  [readme_sufficient], [✅], [README is sufficient (321 chars, keywords: \['run', 'usage', 'install'\]).],
  [open_source_heuristic], [✅], [Repository appears to be on a public hosting platform.],
  [no_special_review_account], [✅], [No indication of a required special review account.],
  [not_previously_submitted], [✅], [Manual confirmation required; assumed OK pending human review.],
  [web_demo_url_present], [✅], [Demo URL is present.],
  [web_demo_host_allowed], [✅], [Demo host 'myapp.vercel.app' passes the allowed-host check.],
  [execution_success], [❌], [No primary flow or command completed successfully.],
)

#if true [
  ---
  == Web Flow Results

  #table(
    columns: (1fr, auto, auto),
    [*Flow*], [*Success*], [*Duration (ms)*],
    [main_demo], [❌], [404],
  )
]

#if false [
  ---
  == CLI Command Results

  #table(
    columns: (2fr, auto, auto),
    [*Command*], [*Exit Code*], [*Duration (ms)*],
    [No CLI results], [], [],
  )
]

---

_This report was generated automatically by Shipwright AI Reviewer._
