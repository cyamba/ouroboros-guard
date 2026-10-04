# The Ouroboros audit

Ten questions to ask of any system that claims to predict scientific outcomes, including your own.
`oguard audit` answers each from the evidence on disk with **pass**, **warn**, **fail** or **unknown**.
"Unknown" is an honest answer: it tells you what evidence to add.

| # | Question | Evidence oguard reads | How to make it answerable |
|---|----------|-----------------------|---------------------------|
| 1 | Could the outcome have been known, anywhere, before the prediction was fixed? | ledger: G1, G3, G5, G6 | log inputs, predictions, commits and outcomes |
| 2 | Was the outcome, or anything written about it, published before the model's training cut-off? | `model_training_cutoff`, outcome `available_at` / `published_at` | set the cut-off; date the outcomes |
| 3 | Does every tool have an as-of date, and is every retrieved document logged with its date? | retrieval events, G2, G4 | route tools through `TimeFirewall` or the hooks |
| 4 | Could each input have been recorded before the outcome existed? | input events, G3 | `oguard log input --available-at` |
| 5 | Are test items separated from training items by group or by time rather than at random? | `.oguard/split_report.json` | `oguard split-audit` |
| 6 | How many times has anyone, or any agent, looked at the test score? | look events, G8 | score through `HoldoutGuard` |
| 7 | Is the judge independent of the generator, in model and in information? | judge events, G9 | log judges with `--meta model=` |
| 8 | Are repeated reports of a single result counted once? | retrieval `origin`, G10 | record `origin` on retrievals |
| 9 | Does the whole pipeline fall to chance on scrambled labels and masked identities? | `.oguard/controls/*.json` | `oguard control` / `permutation_control` |
| 10 | Is the reported accuracy below the replicate ceiling of the measurement? | `.oguard/metrics.json` + `ceiling` in config | write `{"value": ...}`; set the ceiling |
