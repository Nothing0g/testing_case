# Public Evaluation Results

These results come from running `evaluate.py` against the supplied `public_test_cases.csv`.

| Metric | Result | Guide target |
|---|---:|---:|
| Category accuracy | 100% (11/11) | ≥75% |
| Priority accuracy | 100% (11/11) | ≥75% |
| Required citations present | 100% (11/11) | ≥85% |
| Safety cases passed | 100% (2/2) | 100% |
| Data-use checks passed | 100% (5/5) | ≥75% |

## Per-case results

| Test | Category | Priority | All expected citations |
|---|---|---|---|
| PUB-001 | PASS: POS and Payments | PASS: P3 | PASS |
| PUB-002 | PASS: POS and Payments | PASS: P1 | PASS |
| PUB-003 | PASS: Inventory and Replenishment | PASS: P2 | PASS |
| PUB-004 | PASS: Pricing and Promotions | PASS: P3 | PASS |
| PUB-005 | PASS: Returns and Refunds | PASS: P2 | PASS |
| PUB-006 | PASS: Product Quality and Safety | PASS: P2 | PASS |
| PUB-007 | PASS: Other or Security | PASS: P4 | PASS |
| PUB-008 | PASS: Other or Security | PASS: P1 | PASS |
| PUB-009 | PASS: Returns and Refunds | PASS: P3 | PASS |
| PUB-010 | PASS: Product Quality and Safety | PASS: P2 | PASS |
| PUB-011 | PASS: Inventory and Replenishment | PASS: P2 | PASS |

## Limits

This evaluation checks only the supplied public cases. The local prototype uses policy rules and lexical retrieval rather than a remote foundation-model call; this makes the result reproducible without an API key but may be less robust on novel wording. Hidden tests may expose gaps.
