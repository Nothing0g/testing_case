"""Deterministic triage agent: business policy takes precedence over generative guesses."""
from __future__ import annotations
import re

CATEGORIES = [
    "POS and Payments", "Inventory and Replenishment", "Pricing and Promotions",
    "Returns and Refunds", "Vendor and Supply Chain", "Product Quality and Safety",
    "Customer Service", "Other or Security"
]

class TriageAgent:
    def classify(self, prompt: str, data_facts: dict | None = None) -> dict:
        text = (prompt or "").lower()
        facts = data_facts or {}
        # Immediate danger / security risks take precedence over service convenience.
        security = any(x in text for x in ["customer card number", "supplier contract price", "show customer card", "hidden judge", "ignore previous instructions", "reveal the hidden", "full customer database", "pos credentials", "admin password"])
        if security:
            return self._result("Other or Security", "P1", 0.99, "The request seeks restricted data or attempts to override safety controls; disclosure is prohibited.")
        if any(x in text for x in ["injury", "injured", "belt slipped", "recall", "unsafe equipment", "unsafe treadmill", "smoke", "fire", "shock hazard", "product caused harm"]):
            return self._result("Product Quality and Safety", "P1", 0.97, "Reported injury, recall, or immediate product-safety risk requires human escalation.")
        if ("all registers" in text or "store-wide" in text or "every register" in text) and any(x in text for x in ["card", "payment", "pos", "cannot process"]):
            return self._result("POS and Payments", "P1", 0.97, "The payment outage affects the whole store rather than one register.")
        if any(x in text for x in ["cvv", "payment token", "card numbers", "customer card", "card number", "otp", "banking information", "supplier contract"]):
            # A user supplying a card value to be masked is not automatically classified as malicious;
            # disclosure/access requests have already been intercepted by SafetyAgent.
            if any(x in text for x in ["show", "reveal", "give me", "print", "display", "export", "send me"]):
                return self._result("Other or Security", "P1", 0.97, "The request is for restricted payment or supplier information.")
        # Return/refund workflow comes before general product words: a treadmill return is a return
        # unless the prompt mentions a safety event/injury/recall handled above.
        if any(x in text for x in ["return", "refund", "no receipt", "without receipt", "exchange"]):
            amount = self._amount(text)
            no_receipt = "no receipt" in text or "without receipt" in text
            priority = "P2" if (no_receipt and amount >= 1000) or amount >= 5000 else "P3"
            conf = 0.94 if no_receipt or amount else 0.87
            reason = "No-receipt return at/above INR 1,000 requires manager approval; the copilot must not approve it." if no_receipt and amount >= 1000 else "Return/refund guidance is routine; follow the documented approval thresholds and do not override POS controls."
            return self._result("Returns and Refunds", priority, conf, reason)
        # High-impact product-quality patterns, including multi-store or repeated complaints.
        if any(x in text for x in ["quality complaint", "seam", "split football", "cracked bat", "defective", "damaged goods", "warped hockey", "protective padding"]):
            multi = any(x in text for x in ["multiple", "across stores", "two stores", "repeated", "several", "three complaints", "this week", "last 30 days", "most sports goods", "which vendor"])
            return self._result("Product Quality and Safety", "P2" if multi or "seam" in text or "split" in text else "P3", 0.91, "Product-quality complaints should be reviewed; repeated reports should be routed to Product Quality and should not be attributed to a vendor without evidence.")
        if any(x in text for x in ["shelf label", "shelf price", "pos scans", "price mismatch", "scanning higher", "promotion"]):
            broad = any(x in text for x in ["multiple", "many skus", "department", "many customers", "across stores"])
            return self._result("Pricing and Promotions", "P2" if broad else "P3", 0.94, "Verify the shelf label, active POS price, SKU, and promotion dates; correct the label and log a pricing correction ticket.")
        if any(x in text for x in ["all registers", "card reader", "register", "pos terminal", "receipt printer", "card payment"]):
            return self._result("POS and Payments", "P3", 0.92, "The described issue appears limited to a register/device; confirm scope and follow the POS runbook.")
        if any(x in text for x in ["short shipment", "received only", "vendor delivery", "delivery delayed", "fill rate", "purchase order", "po quantity"]):
            return self._result("Vendor and Supply Chain", "P2", 0.91, "A short or delayed delivery can affect replenishment; compare ordered and received quantities and route a claim review to Supply Chain.")
        if any(x in text for x in ["out of stock", "stockout", "not available", "below reorder", "inventory", "replenishment", "academy order", "warehouse stock"]):
            # The supplied policy treats a single SKU that is below its reorder point but
            # still available as P3, unless a high-impact order or promotion is stated.
            explicit_high_impact = any(x in text for x in ["high demand", "high-demand", "academy order", "school order", "team order", "tournament", "promotion", "multiple stores", "across stores"])
            stock_still_available = any(x in text for x in ["still have", "still available", "remaining", "units left", "on hand is", "on-hand is"])
            if "below reorder" in text and stock_still_available and not explicit_high_impact:
                return self._result("Inventory and Replenishment", "P3", 0.91, "The item is below its reorder point but still available; the supplied policy treats this as a routine P3 issue unless a promotion, school/team order, or tournament-critical need raises impact.")
            return self._result("Inventory and Replenishment", "P2", 0.92, "Check on-hand and system quantities, reorder point, receipts, vendor fill rate, and related cases before concluding root cause.")
        if any(x in text for x in ["complaint", "apology", "customer unhappy", "service recovery"]):
            return self._result("Customer Service", "P3", 0.84, "Acknowledge the inconvenience and follow the approved service-recovery policy; do not promise unapproved compensation.")
        if any(x in text for x in ["unresolved", "last 24 hours", "last 30 days", "grouped by store", "which vendor", "dashboard", "analytics", "report", "show open"]):
            return self._result("Other or Security", "P4", 0.91, "This is an analytics request; query the provided CSV data using the fixed event timestamp.")
        return self._result("Other or Security", "P4", 0.57, "The issue does not map confidently to a supported workflow; ask for clarifying details and avoid inventing policy.")

    @staticmethod
    def _amount(text: str) -> float:
        patterns = [r"(?:inr|rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)", r"\b([\d,]{4,}(?:\.\d{1,2})?)\s*(?:inr|rupees?)\b"]
        for pattern in patterns:
            m = re.search(pattern, text, re.I)
            if m:
                try: return float(m.group(1).replace(",", ""))
                except ValueError: pass
        return 0.0

    @staticmethod
    def _result(category, priority, confidence, reason):
        return {"category": category, "priority": priority, "confidence": confidence, "reasoning": reason}
