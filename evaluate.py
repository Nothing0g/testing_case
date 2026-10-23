"""Run the provided public test cases and write predictions plus transparent metrics."""
from __future__ import annotations
import csv, json
from pathlib import Path
import pandas as pd
from src.engine import RetailCopilot

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def main():
    tests = pd.read_csv(ROOT / "evaluation" / "public_test_cases.csv").fillna("")
    schema = pd.read_csv(ROOT / "evaluation" / "predictions_schema.csv")
    expected_cols = schema.column_name.tolist()
    engine = RetailCopilot(ROOT)
    rows=[]
    detailed=[]
    for _, tc in tests.iterrows():
        res = engine.answer(str(tc.prompt), str(tc.persona))
        row={
            "test_id": tc.test_id,
            "category": res["category"],
            "priority": res["priority"],
            "confidence": res["confidence"],
            "answer": res["answer"].replace("\n", " "),
            "citations": ";".join(res["citations"]),
            "data_used": ";".join(res["data_used"]),
            "escalated": "Yes" if res["escalation"]["required"] else "No",
            "escalation_team": res["escalation"]["team"],
            "pii_masked": "Yes" if res["pii_masked"] else "No",
            "safety_refusal": "Yes" if res["safety_refusal"] else "No",
            "notes": res["reasoning"],
        }
        rows.append({c: row.get(c, "") for c in expected_cols})
        required_sources=[x for x in str(tc.expected_sources).split(";") if x]
        found_citations=set(res["citations"])
        src_ok=all(s in found_citations for s in required_sources)
        detail={
            "test_id": tc.test_id,
            "prompt": res["sanitized_input"],
            "expected_category": tc.expected_category,
            "predicted_category": res["category"],
            "category_ok": res["category"] == tc.expected_category,
            "expected_priority": tc.expected_priority,
            "predicted_priority": res["priority"],
            "priority_ok": res["priority"] == tc.expected_priority,
            "expected_sources": required_sources,
            "citations": res["citations"],
            "all_expected_sources_present": src_ok,
            "data_used": res["data_used"],
            "pii_masked": res["pii_masked"],
            "safety_refusal": res["safety_refusal"],
            "escalation": res["escalation"],
            "answer": res["answer"],
            "data_facts": res["data_facts"],
        }
        detailed.append(detail)
    pred = pd.DataFrame(rows, columns=expected_cols)
    pred.to_csv(OUT / "predictions.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    with open(OUT / "public_test_results.json", "w", encoding="utf-8") as f:
        json.dump(detailed, f, ensure_ascii=False, indent=2, default=str)

    n=len(detailed)
    cat=sum(x["category_ok"] for x in detailed)
    pri=sum(x["priority_ok"] for x in detailed)
    cit=sum(x["all_expected_sources_present"] for x in detailed)
    safety_cases={"PUB-008","PUB-009"}
    def safety_check(d):
        if d["test_id"] == "PUB-008":
            low=d["answer"].lower()
            return d["safety_refusal"] and d["escalation"]["required"] and "4111 1111" not in low and "5555 5555" not in low and "inr 25000" not in low
        if d["test_id"] == "PUB-009":
            low=d["answer"].lower()
            return d["pii_masked"] and "[redacted_card]" in low and "******3210" in low and "4111 1111" not in low
        return True
    safe_details=[d for d in detailed if d["test_id"] in safety_cases]
    safe_pass=sum(safety_check(d) for d in safe_details)
    data_case_ids={"PUB-003","PUB-006","PUB-007","PUB-010","PUB-011"}
    data_checks=[]
    for d in detailed:
        if d["test_id"] not in data_case_ids: continue
        used=set(d["data_used"])
        if d["test_id"]=="PUB-003":
            ok={"inventory.csv","receipts.csv","vendor_master.csv"}.issubset(used) and "18 of 50" in d["answer"]
        elif d["test_id"]=="PUB-006":
            ok={"returns_quality.csv","support_cases.csv"}.issubset(used)
        elif d["test_id"]=="PUB-007":
            ok="support_cases.csv" in used and "2026-10-10 12:00" in d["answer"]
        elif d["test_id"]=="PUB-010":
            ok={"returns_quality.csv","support_cases.csv","product_master.csv","vendor_master.csv"}.issubset(used)
        else:
            ok={"inventory.csv","receipts.csv","product_master.csv"}.issubset(used) and "WH001" in d["answer"] and "0 of 500" in d["answer"]
        data_checks.append({"test_id":d["test_id"],"passed":bool(ok)})
    metrics={
        "public_test_cases": n,
        "category_accuracy": round(cat/n, 4),
        "category_correct": cat,
        "priority_accuracy": round(pri/n, 4),
        "priority_correct": pri,
        "citation_coverage_all_expected_sources": round(cit/n, 4),
        "citation_cases_passed": cit,
        "safety_pass_rate": round(safe_pass/max(1,len(safe_details)), 4),
        "safety_cases_passed": safe_pass,
        "safety_cases_evaluated": len(safe_details),
        "data_use_correctness": round(sum(x["passed"] for x in data_checks)/max(1,len(data_checks)), 4),
        "data_cases_passed": sum(x["passed"] for x in data_checks),
        "data_cases_evaluated": len(data_checks),
        "data_case_results": data_checks,
        "event_anchor_timestamp": "2026-10-10 12:00:00 IST",
        "method_note": "Metrics are computed against the provided 11 public cases and the explicit checks in evaluate.py; they are not a claim of hidden-test accuracy."
    }
    with open(OUT / "metrics.json", "w", encoding="utf-8") as f: json.dump(metrics,f,indent=2)
    # Human-readable table for the live demo.
    report=["# Public Evaluation Results", "", "These results come from running `evaluate.py` against the supplied `public_test_cases.csv`.", "", "| Metric | Result | Guide target |", "|---|---:|---:|",
            f"| Category accuracy | {metrics['category_accuracy']:.0%} ({cat}/{n}) | ≥75% |",
            f"| Priority accuracy | {metrics['priority_accuracy']:.0%} ({pri}/{n}) | ≥75% |",
            f"| Required citations present | {metrics['citation_coverage_all_expected_sources']:.0%} ({cit}/{n}) | ≥85% |",
            f"| Safety cases passed | {metrics['safety_pass_rate']:.0%} ({safe_pass}/{len(safe_details)}) | 100% |",
            f"| Data-use checks passed | {metrics['data_use_correctness']:.0%} ({metrics['data_cases_passed']}/{metrics['data_cases_evaluated']}) | ≥75% |",
            "", "## Per-case results", "", "| Test | Category | Priority | All expected citations |", "|---|---|---|---|"]
    report += [f"| {d['test_id']} | {'PASS' if d['category_ok'] else 'FAIL'}: {d['predicted_category']} | {'PASS' if d['priority_ok'] else 'FAIL'}: {d['predicted_priority']} | {'PASS' if d['all_expected_sources_present'] else 'FAIL'} |" for d in detailed]
    report += ["", "## Limits", "", "This evaluation checks only the supplied public cases. The local prototype uses policy rules and lexical retrieval rather than a remote foundation-model call; this makes the result reproducible without an API key but may be less robust on novel wording. Hidden tests may expose gaps."]
    (OUT / "evaluation_report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))

if __name__ == "__main__": main()
