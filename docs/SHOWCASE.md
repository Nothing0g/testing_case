# Showcase Notes

## Project

**AI-Powered Retail Operations Copilot** — a Python prototype for retail issue triage, policy retrieval, structured CSV analysis, and human-approved escalation.

## Demo sequence (about 3 minutes)

1. **Routine issue:** run the CLI with a one-register card-reader failure. Explain why it is P3 and show the cited POS runbook.
2. **Data-backed diagnosis:** ask why English Willow Cricket Bats are repeatedly unavailable at ST002. Point to on-hand/system quantity, purchase receipts, and vendor fill rate as separate evidence sources.
3. **Safety:** submit a request to reveal card numbers. Show refusal, masking behavior, P1 escalation, and the mock workflow payload.
4. **Evaluation:** run `python evaluate.py`; explain the denominator and clarify that public tests do not guarantee hidden-test performance.

## Resume-safe project description

Built a policy-grounded retail operations copilot in Python using rule-based triage, heading-aware knowledge retrieval, pandas-backed multi-CSV analysis, PII/payment-data masking, human-in-the-loop escalation payloads, and a reproducible public-test evaluation pipeline.

## Architecture talking points

- Rules are deterministic where incorrect decisions carry business or safety risk.
- Policy answers carry source-file and section citations.
- Quantitative answers come from the supplied CSVs rather than model memory.
- The workflow output is a mock proposal; no real refund, transfer, vendor claim, or notification is executed.
- Optional LLM phrasing is disabled by default and may not change policy decisions.

## Current limitations

The retriever is lexical, triage is rule-based, the supplied records are static synthetic challenge data, and the optional LLM path has not been evaluated in the public test run. Do not present the prototype as a production system or claim hidden-test performance.
