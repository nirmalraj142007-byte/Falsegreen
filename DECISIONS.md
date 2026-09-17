# Decisions

**Rule:** any code that depends on an OPEN decision reads it from `Settings` (`falsegreen.config`) or from this file, never from a literal.

| ID | Question | Status | Provisional default | Blocks phase |
|---|---|---|---|---|
| U-01 | Which single Bonus Award? Tavily and Most Valuable Feedback are mutually exclusive under the rules. | OPEN | Most Valuable Feedback; Tavily code dropped entirely | 18 |
| U-02 | Headline = raw cold count, or delta vs. published SOTA? The delta requires building a fourth `with_issue` condition. | OPEN | Delta; build `with_issue` | 7, 8 |
| U-03 | Acceptable filtered denominator N_fg. Published work found 449 of 500 usable; our filter adds a fifth criterion. | OPEN | Accept ≥380; halt and ask below that | 5 |
| U-04 | Hours allocated to Design (CLI output + dashboard). Design is 25% of score and the second tiebreaker. | OPEN | 30h, with 25 reserved for CLI output | 10A, 10B, 11A, 11B |
| U-05 | Day-7 trigger if Contree Early Access has not arrived. | OPEN | Continue on Docker backend; hard abort date day 14 | 3 |
| U-06 | Is a static results dashboard sufficient for the required "working demo / hosted application" field, or is an interactive hosted audit needed? | OPEN | Static only | 11A, 16 |
| U-07 | Which real Python repository gets audited at HEAD for the field run. | OPEN | Unassigned — must be named before Phase 17 | 17 |
| U-08 | Nemotron training-cutoff date defining the post-cutoff slice, and its source. | OPEN | None; `--since` required explicitly with a provisional warning | 5 |
| U-09 | Exact model slugs and observed rate limits for both tiers. | OPEN | Resolve from `GET /v1/models` on day 1; never hardcode | 7 |
| U-10 | Does the 3-finding cap apply to benchmark mode, or product mode only? | OPEN | Product mode only; benchmark uncapped | 10B |
