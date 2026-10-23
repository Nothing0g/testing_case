"""Streamlit interface and lightweight operations dashboard."""
from pathlib import Path
import pandas as pd
import json
import streamlit as st
from src.engine import RetailCopilot

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title="Retail Operations Copilot", page_icon="🛒", layout="wide")
engine=RetailCopilot(ROOT)
st.title("Punjab Sports Mart · Retail Operations Copilot")
st.caption("Policy-grounded triage · CSV-backed analysis · human-in-the-loop escalation")
triage_tab, analytics_tab, architecture_tab = st.tabs(["Copilot", "Operations dashboard", "How it works"])

with triage_tab:
    left,right=st.columns([1.3,1])
    with left:
        persona=st.selectbox("Your role",["Cashier","Inventory Associate","Store Manager","Regional Manager","Customer Service Associate"])
        examples={
            "Recurring stockout":"English Willow Cricket Bat is out of stock again at Store ST002. Why is this happening?",
            "POS outage":"All registers in Store ST003 cannot process card payments since 8:20 AM.",
            "Price mismatch":"Shelf label says Match Football is INR 899 but POS scans INR 1099.",
            "Quality complaint":"We have split football seams at two stores. What should we do?",
            "Sensitive data":"Customer phone is 9876543210 and card is 4111 1111 1111 1111. Add this to the return ticket.",
            "Analytics":"Show unresolved P1 and P2 incidents from the last 24 hours grouped by store.",
        }
        preset=st.selectbox("Load a demo scenario",["Custom issue",*examples.keys()])
        default=examples.get(preset,"")
        prompt=st.text_area("Describe the issue",value=default,height=150,placeholder="Include store ID, impact scope, SKU/register, and when it started. Do not enter unnecessary personal or payment information.")
        run=st.button("Analyze issue",type="primary",use_container_width=True)
    with right:
        st.subheader("What this prototype does")
        st.markdown("1. **Safety agent** masks PII/payment values and detects restricted requests.\n2. **Triage agent** assigns category and priority using explicit rules.\n3. **Retrieval agent** searches the supplied Markdown policies and returns section citations.\n4. **Data agent** queries real CSVs for stock, receipts, cases, quality, and vendor questions.\n5. **Workflow agent** prepares a mock escalation payload; it does not execute real business actions.")
    if run and prompt.strip():
        result=engine.answer(prompt,persona)
        st.divider()
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Category",result["category"])
        m2.metric("Priority",result["priority"])
        m3.metric("Confidence",f"{result['confidence']:.0%}")
        m4.metric("Escalation", "Required" if result["escalation"]["required"] else "Not required")
        st.subheader("Recommended response")
        st.write(result["answer"])
        if result["safety_refusal"]: st.error("Restricted request refused and routed for security review.")
        elif result["pii_masked"]: st.warning("PII/payment-like values were masked before response construction.")
        st.subheader("Policy citations")
        for c in result["citations"]: st.code(c,language=None)
        if result["data_used"]:
            st.subheader("CSV evidence")
            st.write("Data files used: "+", ".join(result["data_used"]))
            st.json(result["data_facts"])
        st.subheader("Mock escalation / workflow payload")
        st.caption("The payload is a proposal only. No ticket, refund, transfer, vendor claim, or notification was submitted.")
        st.json(result["workflow_payload"])
        with st.expander("Retrieval trace"):
            st.dataframe(pd.DataFrame(result["retrieved_sections"]),use_container_width=True,hide_index=True)

with analytics_tab:
    cases=pd.read_csv(ROOT/"data"/"support_cases.csv")
    stores=pd.read_csv(ROOT/"data"/"store_master.csv")
    returns=pd.read_csv(ROOT/"data"/"returns_quality.csv")
    cases["created_ts"]=pd.to_datetime(cases.created_ts,errors="coerce")
    cases["_day"]=cases.created_ts.dt.date
    anchor=pd.Timestamp("2026-10-10 12:00")
    active=cases[cases.status.ne("Closed")]
    p1=int((active.priority_label=="P1").sum()); p2=int((active.priority_label=="P2").sum())
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Cases in dataset",f"{len(cases):,}")
    c2.metric("Open / in progress",f"{len(active):,}")
    c3.metric("Active P1",p1)
    c4.metric("Active P2",p2)
    col1,col2=st.columns(2)
    with col1:
        st.caption("Active cases by priority")
        st.bar_chart(active.priority_label.value_counts().reindex(["P1","P2","P3","P4"],fill_value=0))
    with col2:
        st.caption("Active cases by category")
        st.bar_chart(active.category_label.value_counts())
    per_region=active.merge(stores[["store_id","region"]],on="store_id",how="left").groupby("region").size().sort_values(ascending=False)
    st.caption("Active cases by region")
    st.bar_chart(per_region)
    st.caption(f"Relative-date analytics use the guide's event anchor: {anchor:%Y-%m-%d %H:%M} IST. The dashboard counts rows in the supplied CSV; it is not a live ERP/POS integration.")
    with st.expander("View active case records"):
        st.dataframe(active.drop(columns=["_day"],errors="ignore"),use_container_width=True,hide_index=True)

with architecture_tab:
    st.markdown("""
    ### End-to-end flow
    ```text
    User prompt
       ↓
    Safety agent ── redaction / injection checks ── refuse restricted requests
       ↓
    Triage agent ── category + priority + confidence
       ├──────────── Policy retrieval agent ── Markdown sections + citations
       ├──────────── Structured-data agent ── pandas queries over CSVs
       ↓
    Response composer ── facts + next actions + sources
       ↓
    Workflow agent ── escalation matrix + mock payload (human approval gates)
       ↓
    UI response + traceable predictions/evaluation
    ```
    ### Design choices
    - **Policy first:** escalation and approvals are driven by supplied policies and matrix rows, not a free-form model guess.
    - **Grounded retrieval:** every policy-backed response carries source file and section references.
    - **Data is queried, not guessed:** analytics are computed from CSV records with the fixed event timestamp `2026-10-10 12:00:00 IST`.
    - **No live side effects:** refunds, transfers, quarantine, vendor claims, and notifications are mock payloads only.
    - **Uncertainty:** confidence below 0.60 requests human review.
    """)
    metrics_path=ROOT/"outputs"/"metrics.json"
    if metrics_path.exists():
        st.subheader("Public test evaluation")
        st.json(json.loads(metrics_path.read_text(encoding="utf-8")))
