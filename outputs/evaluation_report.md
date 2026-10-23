# Public Evaluation Results

These results come from running `evaluate.py` against the 11 supplied public test cases and the curated synthetic demo rows.

| Metric | Result | Guide target |
|---|---:|---:|
| Category accuracy | 100% (11/11) | ≥75% |
| Priority accuracy | 100% (11/11) | ≥75% |
| Required citations present | 100% (11/11) | ≥85% |
| Safety cases passed | 100% (2/2) | 100% |
| Data-use checks passed | 100% (5/5) | ≥75% |

## Limits

This evaluation covers the supplied public cases only. The prototype uses deterministic policy rules and lexical retrieval, not an external LLM call. The test set is small and seeded, so hidden-test performance is unknown.
