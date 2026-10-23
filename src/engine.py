"""Orchestrator for the Retail Operations Copilot's cooperating agents."""
from __future__ import annotations
from pathlib import Path
from .safety import SafetyAgent
from .triage import TriageAgent
from .policy import PolicyRetriever
from .data_agent import RetailDataAgent
from .workflow import WorkflowAgent
from .generator import OptionalLLMGenerator

class RetailCopilot:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else Path(__file__).resolve().parents[1]
        self.safety = SafetyAgent()
        self.triage = TriageAgent()
        self.retriever = PolicyRetriever(self.root / "knowledge_base")
        self.data = RetailDataAgent(self.root / "data")
        self.workflow = WorkflowAgent(self.root / "data")
        self.generator = OptionalLLMGenerator()

    def _data_intent(self, prompt: str, category: str) -> str | None:
        t = prompt.lower()
        if any(x in t for x in ["which vendor", "most sports goods quality complaints", "vendor appears linked", "last 30 days"]):
            if "vendor" in t and ("quality" in t or "complaint" in t): return "vendor_quality"
        if any(x in t for x in ["unresolved", "last 24 hours", "open p1", "open high-priority", "grouped by store", "grouped by store"]):
            return "open_cases"
        if category == "Product Quality and Safety" and any(x in t for x in ["two stores", "across stores", "seams", "quality complaint", "split football"]):
            return "quality_product"
        if category == "Inventory and Replenishment" and any(x in t for x in ["out of stock", "not available", "root cause", "why is this happening", "replenishment", "warehouse", "below reorder", "cycle count", "system quantity"]):
            return "inventory_root_cause"
        if category == "Vendor and Supply Chain" and any(x in t for x in ["short shipment", "received only", "fill rate", "delivery delayed"]):
            return "inventory_root_cause"
        if category == "Pricing and Promotions" and any(x in t for x in ["shelf", "pos scans", "price mismatch"]):
            return "pricing_lookup"
        return None

    def _citations(self, category: str, priority: str, intent: str | None, safety_refusal: bool, pii_masked: bool, retrieved: list[dict]) -> list[str]:
        citations=[]
        def add(x):
            if x not in citations: citations.append(x)
        if safety_refusal:
            add("05_responsible_ai_policy.md#prompt-injection")
            add("02_pos_pricing_returns_policy.md#payment-security")
        if pii_masked:
            add("05_responsible_ai_policy.md#pii-and-payment-data-masking")
        if category == "POS and Payments":
            add("02_pos_pricing_returns_policy.md#pos-card-reader-runbook")
            if priority == "P1": add("01_retail_operations_sop.md#priority-rules")
        elif category == "Inventory and Replenishment":
            add("03_inventory_replenishment_policy.md#stock-outs-and-replenishment")
            if intent == "inventory_root_cause": add("03_inventory_replenishment_policy.md#root-cause-hints")
        elif category == "Pricing and Promotions": add("02_pos_pricing_returns_policy.md#pricing-and-promotions")
        elif category == "Returns and Refunds":
            add("02_pos_pricing_returns_policy.md#returns-and-refunds")
            if priority == "P2": add("05_responsible_ai_policy.md#human-in-the-loop")
        elif category == "Vendor and Supply Chain": add("04_vendor_quality_policy.md#short-shipments")
        elif category == "Product Quality and Safety":
            if priority == "P1": add("04_vendor_quality_policy.md#recall-and-safety")
            else: add("04_vendor_quality_policy.md#product-quality-complaints")
            if intent == "vendor_quality": add("04_vendor_quality_policy.md#vendor-performance")
        elif category == "Customer Service": add("02_pos_pricing_returns_policy.md#customer-recovery")
        elif category == "Other or Security":
            if safety_refusal:
                add("05_responsible_ai_policy.md#prompt-injection")
                add("02_pos_pricing_returns_policy.md#payment-security")
            elif intent in {"open_cases", "vendor_quality", "inventory_root_cause", "quality_product", "pricing_lookup"}:
                add("01_retail_operations_sop.md#analytics-rule")
        if intent in {"open_cases", "vendor_quality", "inventory_root_cause", "quality_product", "pricing_lookup"}:
            add("01_retail_operations_sop.md#analytics-rule")
        if intent == "inventory_root_cause" and category == "Inventory and Replenishment": add("04_vendor_quality_policy.md#short-shipments")
        # Retrieved sections may add contextual citations, but only when the section is relevant
        # to the classified workflow. Avoid citations to the document title or unrelated words
        # (for example, a return prompt mentioning "card" should not cite the POS device runbook).
        allowed = {
            "POS and Payments": ["02_pos_pricing_returns_policy.md#", "01_retail_operations_sop.md#priority-rules", "05_responsible_ai_policy.md#payment-security"],
            "Inventory and Replenishment": ["03_inventory_replenishment_policy.md#", "04_vendor_quality_policy.md#short-shipments", "01_retail_operations_sop.md#analytics-rule"],
            "Pricing and Promotions": ["02_pos_pricing_returns_policy.md#pricing-and-promotions", "01_retail_operations_sop.md#priority-rules"],
            "Returns and Refunds": ["02_pos_pricing_returns_policy.md#returns-and-refunds", "05_responsible_ai_policy.md#human-in-the-loop", "05_responsible_ai_policy.md#pii-and-payment-data-masking"],
            "Vendor and Supply Chain": ["04_vendor_quality_policy.md#short-shipments", "04_vendor_quality_policy.md#vendor-performance", "01_retail_operations_sop.md#analytics-rule"],
            "Product Quality and Safety": ["04_vendor_quality_policy.md#product-quality-complaints", "04_vendor_quality_policy.md#recall-and-safety", "04_vendor_quality_policy.md#vendor-performance", "03_inventory_replenishment_policy.md#sports-goods-handling", "01_retail_operations_sop.md#analytics-rule"],
            "Customer Service": ["02_pos_pricing_returns_policy.md#customer-recovery"],
            "Other or Security": ["05_responsible_ai_policy.md#prompt-injection", "02_pos_pricing_returns_policy.md#payment-security", "01_retail_operations_sop.md#analytics-rule"],
        }.get(category, [])
        document_title_anchors = {"#retail-operations-sop", "#pos-pricing-and-returns-policy", "#inventory-and-replenishment-policy", "#vendor-supply-chain-and-product-quality-policy", "#responsible-ai-policy"}
        for item in retrieved:
            citation = item["citation"]
            if category == "Other or Security" and not safety_refusal:
                # Analytics questions must not inherit unrelated security/payment sources
                # just because generic terms such as "case" or "priority" overlap.
                retrieval_is_relevant = (intent in {"open_cases", "vendor_quality", "inventory_root_cause", "quality_product", "pricing_lookup"}
                                         and citation == "01_retail_operations_sop.md#analytics-rule")
            else:
                retrieval_is_relevant = any(citation.startswith(prefix) for prefix in allowed)
            if item["score"] >= 2.0 and retrieval_is_relevant:
                if not any(citation.endswith(anchor) for anchor in document_title_anchors): add(citation)
            if len(citations) >= 6: break
        return citations

    def answer(self, prompt: str, persona: str | None = None) -> dict:
        safe = self.safety.inspect(prompt)
        if safe.safety_refusal:
            self.generator.last_status = "not_used_for_safety_refusal"
        clean = safe.sanitized_text
        if safe.safety_refusal:
            triage = {"category":"Other or Security", "priority":"P1", "confidence":0.99,
                      "reasoning":"The request attempts to obtain restricted data or override safety controls; disclosure is prohibited."}
            intent = None
            data_result = {"answer":"I can’t provide customer card numbers, supplier contract prices, hidden test data, credentials, or restricted records. I have not accessed or disclosed them. Treat this as a security concern and route it to Security for review. I can provide an aggregate, non-sensitive report or help prepare a sanitized incident summary instead.","data_used":[],"facts":{}}
            retrieved = self.retriever.retrieve(clean + " prompt injection payment security", top_k=4)
        else:
            # Initial classification sets an initial branch; data facts can refine the response but
            # priority rules remain transparent and override any model-style interpretation.
            triage = self.triage.classify(clean)
            intent = self._data_intent(clean, triage["category"])
            data_result = None
            if intent == "open_cases": data_result = self.data.open_high_priority_cases()
            elif intent == "vendor_quality": data_result = self.data.vendor_quality_trends()
            elif intent == "quality_product": data_result = self.data.quality_for_product(clean)
            elif intent == "inventory_root_cause": data_result = self.data.inventory_root_cause(clean)
            elif intent == "pricing_lookup": data_result = self.data.pricing_lookup(clean)
            facts = data_result.get("facts", {}) if data_result else {}
            # Re-triage stock-outs using real facts. This does not infer policy from CSVs; it only
            # grounds the scope/severity of the stock condition.
            if intent == "inventory_root_cause" and triage["category"] in {"Inventory and Replenishment", "Vendor and Supply Chain"}:
                triage = self.triage.classify(clean, facts)
                # Apply the documented inventory thresholds when the SKU/store facts are available.
                # A product that is below reorder but still on hand is normally P3; a zero-stock
                # high-demand/academy item is P2. Quantity discrepancies use the supplied policy's
                # >10 units or >20% rule, with severity depending on demand impact.
                if triage["category"] == "Inventory and Replenishment" and facts:
                    on_hand = facts.get("on_hand")
                    system_qty = facts.get("system_qty")
                    reorder = facts.get("reorder_point")
                    high_demand = bool(facts.get("high_demand")) or any(x in clean.lower() for x in ["academy order", "school order", "tournament", "high demand"])
                    if on_hand is not None and on_hand > 0 and reorder is not None and on_hand <= reorder:
                        triage.update({"priority":"P3", "confidence":0.93, "reasoning":"Stock is below the reorder threshold but still available; the supplied policy treats this as a routine P3 issue unless a promotion, school/team order, or tournament-critical need raises impact."})
                    elif on_hand == 0:
                        triage.update({"priority":"P2" if high_demand else "P3", "confidence":0.94, "reasoning":"The item is out of stock" + (" and is high-demand or tied to an academy/school/tournament order, so replenishment impact is P2." if high_demand else "; with no high-demand or urgent-order evidence, treat it as a routine P3 stock issue.")})
                    elif on_hand is not None and system_qty is not None and reorder is not None:
                        diff = abs(int(system_qty) - int(on_hand))
                        pct = diff / max(1, max(abs(int(system_qty)), abs(int(on_hand))))
                        if diff > 10 or pct > 0.20:
                            triage.update({"priority":"P2" if high_demand else "P3", "confidence":0.90, "reasoning":"System quantity and physical on-hand differ by more than the supplied policy threshold; perform a cycle count. Escalation priority depends on whether the product's availability impact is high."})
            retrieved = self.retriever.retrieve(clean + " " + triage["category"] + " " + triage["reasoning"], top_k=5)
        citations = self._citations(triage["category"], triage["priority"], intent, safe.safety_refusal, safe.pii_masked, retrieved)
        if safe.safety_refusal:
            answer_text = data_result["answer"]
        else:
            base = data_result["answer"] if data_result else ""
            policy_answer = self._recommendation(clean, triage, intent)
            if base:
                answer_text = base + "\n\nRecommended action: " + policy_answer
            else:
                answer_text = policy_answer
            if safe.pii_masked:
                masked_items=[]
                if "[REDACTED_CARD]" in clean: masked_items.append("card value → [REDACTED_CARD]")
                phone = "******" + ""  # output already uses last four digits only
                m = __import__("re").search(r"\*{4,}\d{4}", clean)
                if m: masked_items.append("phone → " + m.group(0))
                if "@" in prompt and "*" in clean: masked_items.append("email → masked")
                answer_text += "\n\nPrivacy handling: sensitive values were masked before preparing the response" + (" (" + "; ".join(masked_items) + ")" if masked_items else "") + ". Full payment details are not needed for a return ticket."
        escalate = triage["priority"] == "P1" or triage["confidence"] < 0.60
        if intent is None and not safe.safety_refusal and triage["category"] != "Other or Security":
            # Include clarification when ticket fields are absent; urgent guidance is already given first.
            if not any(__import__("re").search(p, clean, __import__("re").I) for p in [r"\bST\d{3}\b", r"\bWH\d{3}\b"]):
                answer_text += "\n\nFollow-up: Which store ID is affected?"
        # Optional LLM phrasing is opt-in. Deterministic policy decisions and citations cannot be changed.
        generated = None
        if not safe.safety_refusal:
            generated = self.generator.generate(sanitized_prompt=clean, triage=triage, retrieved=retrieved,
                                                data_result=data_result, deterministic_answer=answer_text, citations=citations)
        if generated:
            answer_text = generated
        facts = data_result.get("facts", {}) if data_result else {}
        workflow = self.workflow.prepare({**triage, "confidence":triage["confidence"]}, clean, facts)
        if triage["priority"] == "P1" or triage["confidence"] < 0.60 or workflow["human_approval_required"]:
            escalate = True
        return {
            "category": triage["category"], "priority": triage["priority"],
            "confidence": round(float(triage["confidence"]), 2), "reasoning": triage["reasoning"],
            "answer": answer_text, "citations": citations,
            "retrieved_sections": [{"citation":x["citation"],"section":x["section"],"score":x["score"]} for x in retrieved[:4]],
            "data_used": data_result.get("data_used", []) if data_result else [],
            "escalation": {"required": bool(workflow["escalation_required"] or escalate), "team":workflow["team"], "channel":workflow["channel"], "sla_minutes":workflow["sla_minutes"], "human_approval_required":workflow["human_approval_required"], "reason": triage["reasoning"]},
            "workflow_payload": workflow,
            "pii_masked": bool(safe.pii_masked), "safety_refusal": bool(safe.safety_refusal),
            "generation_mode": self.generator.last_status,
            "sanitized_input": clean,
            "data_facts": facts,
        }

    @staticmethod
    def _recommendation(prompt: str, triage: dict, intent: str | None) -> str:
        category, priority = triage["category"], triage["priority"]
        t=prompt.lower()
        if category == "POS and Payments":
            if priority == "P1": return "Notify the Store Manager and POS Support immediately; log affected register(s), error code, and outage start time. Do not collect card details. Use only an approved alternate tender if store policy permits."
            return "Confirm whether one or all registers are affected, reseat the reader cable or restart the device, try another approved register if available, use an approved alternate tender if allowed, and log a POS ticket with store/register ID, error code, and start time. Do not request card data."
        if category == "Inventory and Replenishment":
            return "Check on-hand versus system quantity, reorder point, recent receipts, vendor fill rate, and related cases. If inventory is zero for a high-demand or academy-order item, escalate to the Store Manager and Inventory Lead; arrange transfer/reorder only with approval."
        if category == "Pricing and Promotions":
            return "Verify SKU, current shelf label, active POS price, and promotion dates. If the displayed lower shelf price is current, follow the policy within manager-approved limits, correct the label, and create a pricing correction ticket. Escalate if multiple SKUs/customers are affected."
        if category == "Returns and Refunds":
            amount_match = __import__("re").search(r"(?:inr|rs\.?|₹)\s*([\d,]+)", t, __import__("re").I)
            no_receipt = "no receipt" in t or "without receipt" in t
            if no_receipt and amount_match:
                try: amount = float(amount_match.group(1).replace(",", ""))
                except ValueError: amount = 0
                if amount >= 1000: return f"Do not approve the refund. This no-receipt return is INR {amount:,.0f}; manager approval is required at INR 1,000 or above when there is no receipt. Prepare a masked summary and route it to the Store Manager for review."
            return "Check receipt presence, item condition, amount, and documented thresholds. Do not approve a refund override or promise compensation; route cases above the policy threshold to the Store Manager."
        if category == "Vendor and Supply Chain":
            return "Compare ordered and received quantities, review the last two receipts and vendor fill rate, record damage evidence if relevant, and route a vendor-claim review to Supply Chain. A human must approve any real claim submission."
        if category == "Product Quality and Safety":
            if priority == "P1": return "Stop use/sale of the potentially unsafe item, keep people away from the hazard, and notify the Store Manager and Product Quality immediately. A human must decide quarantine/recall handling; do not declare the product safe."
            return "Record SKU, store, batch/receipt information, complaint details, and photos if available. Hold affected stock for manager-approved quality review, compare related return/support records, and route repeated complaints to Product Quality. Do not blame the vendor without investigation."
        if category == "Customer Service": return "Acknowledge the inconvenience, explain the documented process, and refer any exception or compensation request to the Store Manager. Do not promise unapproved compensation."
        if triage["confidence"] < 0.60: return "I can't confidently classify this from the supplied details. Provide the store ID, impact scope, when it began, and SKU/register/error code if relevant. I recommend human review because confidence is below 0.60."
        return "Use the provided CSV data for factual analytics, retain the fixed event timestamp for relative-date questions, and cite the relevant policy section. Share the exact metric or issue if you need a more focused result."
