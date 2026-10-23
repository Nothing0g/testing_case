"""Structured-data agent. All analytics answers are computed from supplied CSV files."""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

ANCHOR = pd.Timestamp("2026-10-10 12:00:00")

class RetailDataAgent:
    def __init__(self, data_dir: str | Path):
        p = Path(data_dir)
        self.data_dir = p
        self.inventory = pd.read_csv(p / "inventory.csv", dtype={"store_id": str, "sku": str})
        self.products = pd.read_csv(p / "product_master.csv", dtype={"sku": str})
        self.receipts = pd.read_csv(p / "receipts.csv", dtype={"sku": str, "store_id": str, "vendor_id": str})
        self.vendors = pd.read_csv(p / "vendor_master.csv", dtype={"vendor_id": str})
        self.cases = pd.read_csv(p / "support_cases.csv", dtype={"store_id": str, "sku": str})
        self.returns = pd.read_csv(p / "returns_quality.csv", dtype={"store_id": str, "sku": str})
        self.stores = pd.read_csv(p / "store_master.csv", dtype={"store_id": str})
        self.escalation = pd.read_csv(p / "escalation_matrix.csv")
        self.cases["_dt"] = pd.to_datetime(self.cases["created_ts"], errors="coerce")
        self.returns["_dt"] = pd.to_datetime(self.returns["created_ts"], errors="coerce")
        self.receipts["_dt"] = pd.to_datetime(self.receipts["receipt_date"], errors="coerce")
        self.returns["sku"] = self.returns["sku"].fillna("").astype(str)
        self.cases["sku"] = self.cases["sku"].fillna("").astype(str)
        self.aliases = {
            "english willow cricket bat": "SKU1001",
            "english willow bat": "SKU1001",
            "match football": "SKU2003",
            "football": "SKU2003",
            "tennis ball pack": "SKU7001",
            "tennis balls": "SKU7001",
            "treadmill": "SKU5002",
        }

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

    def resolve_product(self, prompt: str):
        text = self._norm(prompt)
        sku_match = re.search(r"\bSKU\s*[-:]?\s*(\d{4})\b", prompt, re.I)
        sku = f"SKU{sku_match.group(1)}" if sku_match else None
        if sku:
            rows = self.products[self.products.sku.eq(sku)]
            if len(rows): return rows.iloc[0]
        for alias, alias_sku in sorted(self.aliases.items(), key=lambda x: -len(x[0])):
            if alias in text:
                rows = self.products[self.products.sku.eq(alias_sku)]
                if len(rows): return rows.iloc[0]
        # Fuzzy-ish name matching using significant product-name tokens; only return if
        # there is a clear overlap rather than guessing based on a generic word.
        prompt_tokens = set(text.split())
        best, best_score = None, 0
        for _, row in self.products.iterrows():
            name_tokens = set(self._norm(str(row["name"])).split())
            significant = {t for t in name_tokens if t not in {"junior", "senior", "pro", "club", "academy", "training", "size"}}
            score = len(prompt_tokens & significant)
            if score > best_score and score >= min(2, len(significant)):
                best, best_score = row, score
        return best

    def _recent_receipts(self, store: str | None, sku: str):
        df = self.receipts[self.receipts.sku.eq(sku)].copy()
        if store:
            df = df[df.store_id.eq(store)]
        df = df[(df._dt <= ANCHOR) & (df._dt >= ANCHOR - pd.Timedelta(days=30))]
        return df.sort_values("_dt", ascending=False)

    def inventory_root_cause(self, prompt: str) -> dict:
        product = self.resolve_product(prompt)
        store_match = re.search(r"\b(ST\d{3}|WH\d{3})\b", prompt, re.I)
        store = store_match.group(1).upper() if store_match else None
        if product is None:
            return {"answer": "I couldn't confidently match the product to product_master.csv. Please provide its SKU and store ID.", "data_used": [], "facts": {}, "needs_follow_up": True}
        sku = str(product.sku)
        inv = self.inventory[self.inventory.sku.eq(sku)].copy()
        target = inv[inv.store_id.eq(store)] if store else pd.DataFrame()
        if target.empty and len(inv):
            target = inv.sort_values("on_hand").head(1)
        receipts = self._recent_receipts(store, sku)
        # If a warehouse stockout is part of the issue, include WH001 records even when the store differs.
        warehouse = inv[inv.store_id.eq("WH001")]
        if store and receipts.empty:
            receipts = self._recent_receipts("WH001", sku)
        v_id = str(product.vendor_id)
        vendor_rows = self.vendors[self.vendors.vendor_id.eq(v_id)]
        vendor = vendor_rows.iloc[0] if len(vendor_rows) else None
        case_rows = self.cases[self.cases.sku.eq(sku) & (self.cases._dt <= ANCHOR) & (self.cases._dt >= ANCHOR - pd.Timedelta(days=30))]
        parts = [f"Product: {product['name']} ({sku}); listed vendor: {v_id}."]
        facts = {"sku": sku, "product": str(product["name"]), "store_id": store, "vendor_id": v_id, "high_demand": str(product.get("high_demand", "No")).strip().lower() in {"yes", "true", "1"}}
        if not target.empty:
            x = target.iloc[0]
            parts.append(f"{x.store_id} on hand is {int(x.on_hand)}; system quantity is {int(x.system_qty)}; reorder point is {int(x.reorder_point)}.")
            facts.update({"on_hand": int(x.on_hand), "system_qty": int(x.system_qty), "reorder_point": int(x.reorder_point)})
        if len(warehouse):
            w = warehouse.iloc[0]
            parts.append(f"Warehouse WH001 has {int(w.on_hand)} on hand versus reorder point {int(w.reorder_point)}.")
            facts["warehouse_on_hand"] = int(w.on_hand)
        if len(receipts):
            rec_text = []
            for _, r in receipts.head(3).iterrows():
                qty_pct = (int(r.received_qty) / int(r.po_qty) * 100) if int(r.po_qty) else 0
                rec_text.append(f"{r.receipt_id} on {r.receipt_date}: {int(r.received_qty)} of {int(r.po_qty)} received ({qty_pct:.0f}% fill)")
            parts.append("Recent receipts: " + "; ".join(rec_text) + ".")
            facts["recent_receipts"] = [{"receipt_id": str(r.receipt_id), "date": str(r.receipt_date), "po_qty": int(r.po_qty), "received_qty": int(r.received_qty)} for _, r in receipts.head(3).iterrows()]
        if vendor is not None:
            parts.append(f"Vendor {vendor['name']} fill rate is {float(vendor.fill_rate):.0%}; on-time rate is {float(vendor.on_time_rate):.0%}; status is {vendor.status}.")
            facts.update({"vendor_name": str(vendor["name"]), "vendor_fill_rate": float(vendor.fill_rate), "vendor_on_time_rate": float(vendor.on_time_rate)})
        if len(case_rows):
            hints = case_rows.root_cause_hint.dropna().astype(str).unique().tolist()[:3]
            parts.append(f"There are {len(case_rows)} related support case(s) in the last 30 days before the event anchor" + (f"; recorded hints: {', '.join(hints)}." if hints else "."))
            facts["related_case_count"] = int(len(case_rows))
        is_stockout = (not target.empty and int(target.iloc[0].on_hand) == 0)
        wh_stockout = (not warehouse.empty and int(warehouse.iloc[0].on_hand) == 0)
        short_receipt = len(receipts) and any((r.received_qty < r.po_qty) for _, r in receipts.iterrows())
        if is_stockout and wh_stockout:
            conclusion = "The strongest supported explanation is a stockout at both the store and warehouse, so there is no warehouse stock available to replenish the store."
        elif short_receipt and vendor is not None and float(vendor.fill_rate) < .80:
            conclusion = "The evidence points to a likely replenishment constraint: recent deliveries were short and the vendor's recorded fill rate is below 80%. This is a signal for review, not proof of fault."
        elif is_stockout:
            conclusion = "The item is out of stock at the store. The provided data does not establish a single root cause; check recent receipts, warehouse availability, and related cases before attributing cause."
        else:
            conclusion = "The available inventory evidence does not show a store-level stockout. Confirm the exact SKU/store and whether this is a shelf, system-quantity, or replenishment issue."
        answer = conclusion + " " + " ".join(parts)
        used = ["product_master.csv", "inventory.csv"]
        if len(receipts): used.append("receipts.csv")
        if vendor is not None: used.append("vendor_master.csv")
        if len(case_rows): used.append("support_cases.csv")
        return {"answer": answer, "data_used": list(dict.fromkeys(used)), "facts": facts, "needs_follow_up": product is None or store is None}

    def open_high_priority_cases(self) -> dict:
        start = ANCHOR - pd.Timedelta(hours=24)
        df = self.cases[(self.cases._dt >= start) & (self.cases._dt <= ANCHOR) & self.cases.priority_label.isin(["P1", "P2"]) & self.cases.status.ne("Closed")].copy()
        rows = []
        if len(df):
            for store, grp in df.groupby("store_id", dropna=False):
                details = []
                for _, r in grp.sort_values("_dt").iterrows():
                    details.append(f"{r.case_id} ({r.priority_label}, {r.category_label}, {r.status})")
                rows.append(f"{store}: {', '.join(details)}")
        answer = f"Using the event anchor {ANCHOR:%Y-%m-%d %H:%M} IST, there are {len(df)} unresolved P1/P2 case(s) in the last 24 hours across {df.store_id.nunique()} store(s). "
        answer += " | ".join(rows) if rows else "No unresolved P1/P2 cases match the window."
        return {"answer": answer, "data_used": ["support_cases.csv", "store_master.csv"], "facts": {"case_count": int(len(df)), "stores": df.store_id.nunique(), "case_ids": df.case_id.astype(str).tolist()}}

    def vendor_quality_trends(self) -> dict:
        start = ANCHOR - pd.Timedelta(days=30)
        # Use returns/quality and support cases separately; these records have different grains,
        # so counts are not silently deduplicated or added together as if they were one event set.
        ret = self.returns[(self.returns._dt >= start) & (self.returns._dt <= ANCHOR)].copy()
        ret = ret[ret.reason.astype(str).str.contains(r"quality|seam|split|crack|defect|belt slipped|lost air", case=False, regex=True)]
        retj = ret.merge(self.products[["sku", "vendor_id", "name"]], on="sku", how="left")
        ret_counts = retj.groupby("vendor_id").size().sort_values(ascending=False)
        cases = self.cases[(self.cases._dt >= start) & (self.cases._dt <= ANCHOR) & (self.cases.category_label.eq("Product Quality and Safety"))].copy()
        # Resolve vendor IDs through SKU/product master; aggregate complaint mentions by record.
        casej = cases.merge(self.products[["sku", "vendor_id", "name"]], on="sku", how="left")
        case_counts = casej.groupby("vendor_id").size().sort_values(ascending=False)
        candidate_ids = set(ret_counts.index.astype(str)) | set(case_counts.index.astype(str))
        stats=[]
        for vid in candidate_ids:
            if not vid or vid == "nan": continue
            rv=int(ret_counts.get(vid,0)); cv=int(case_counts.get(vid,0))
            # Combine only for ranking and explicitly disclose the source-separated counts.
            stats.append((rv+cv, vid, rv, cv))
        stats.sort(reverse=True)
        lines=[]
        for total, vid, rv, cv in stats[:5]:
            vr = self.vendors[self.vendors.vendor_id.eq(vid)]
            name = str(vr.iloc[0]['name']) if len(vr) else vid
            lines.append(f"{name} ({vid}): {rv} matching returns/quality records + {cv} Product Quality and Safety support cases")
        if stats:
            top = stats[0]
            vr = self.vendors[self.vendors.vendor_id.eq(top[1])]
            name = str(vr.iloc[0]['name']) if len(vr) else top[1]
            answer = (f"For the 30-day window ending {ANCHOR:%Y-%m-%d %H:%M} IST, {name} ({top[1]}) has the highest count in this merged ranking: {top[2]} matching returns/quality records and {top[3]} matching Product Quality and Safety cases. "
                      "These are record counts across two sources with potentially overlapping incidents; they indicate where to review, not proof that a vendor caused the issues. Ranking details: " + "; ".join(lines) + ".")
            facts={"top_vendor_id":top[1],"top_vendor_name":name,"returns_quality_count":top[2],"support_case_count":top[3],"ranking":lines}
        else:
            answer="No quality-related records matched the 30-day event window in the supplied sources."
            facts={"ranking":[]}
        return {"answer": answer, "data_used": ["returns_quality.csv", "support_cases.csv", "product_master.csv", "vendor_master.csv"], "facts": facts}

    def quality_for_product(self, prompt: str) -> dict:
        product = self.resolve_product(prompt)
        sku = str(product.sku) if product is not None else None
        store_ids = re.findall(r"\bST\d{3}\b", prompt.upper())
        ret = self.returns[(self.returns._dt <= ANCHOR) & (self.returns._dt >= ANCHOR - pd.Timedelta(days=30))].copy()
        if sku: ret = ret[ret.sku.eq(sku)]
        if store_ids: ret = ret[ret.store_id.isin(store_ids)]
        ret = ret[ret.reason.astype(str).str.contains(r"quality|seam|split|crack|defect|belt slipped|lost air", case=False, regex=True)]
        cases = self.cases[(self.cases._dt <= ANCHOR) & (self.cases._dt >= ANCHOR - pd.Timedelta(days=30)) & self.cases.category_label.eq("Product Quality and Safety")].copy()
        if sku: cases = cases[cases.sku.eq(sku)]
        ret_summary = "; ".join(f"{r.return_id} at {r.store_id}: {r.reason} ({r.status})" for _,r in ret.head(8).iterrows())
        case_summary = "; ".join(f"{r.case_id} at {r.store_id}: {r.issue_text} ({r.status})" for _,r in cases.head(8).iterrows())
        answer = f"Within the 30-day window ending {ANCHOR:%Y-%m-%d %H:%M} IST, I found {len(ret)} matching quality-related return/quality record(s)" + (f" ({ret_summary})" if ret_summary else "") + f" and {len(cases)} matching Product Quality and Safety support case(s)" + (f" ({case_summary})" if case_summary else "") + ". Treat repeated reports as a reason to hold affected stock for human quality review; do not conclude the product or supplier is definitively at fault without investigation."
        return {"answer": answer, "data_used": ["returns_quality.csv", "support_cases.csv", "product_master.csv"], "facts": {"returns_count":int(len(ret)),"cases_count":int(len(cases))}}

    def pricing_lookup(self, prompt: str) -> dict:
        p = self.resolve_product(prompt)
        if p is None:
            return {"answer":"I couldn't match the product to product_master.csv. Verify the SKU before changing the POS price.","data_used":["product_master.csv"],"facts":{},"needs_follow_up":True}
        return {"answer":f"Product master lists {p['name']} ({p['sku']}) at INR {float(p['list_price']):,.0f}. This is a reference list price, not proof of the active POS price or a promotion. Verify the current shelf label, POS price, SKU, and promotion dates, correct the label if wrong, and raise a pricing correction ticket.","data_used":["product_master.csv"],"facts":{"sku":str(p['sku']),"list_price":float(p['list_price'])}}
