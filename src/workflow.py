"""Mock workflow agent; it prepares payloads but never performs a real business action."""
from __future__ import annotations
import uuid
import pandas as pd

class WorkflowAgent:
    def __init__(self, data_dir):
        self.matrix = pd.read_csv(f"{data_dir}/escalation_matrix.csv")

    def prepare(self, result: dict, sanitized_prompt: str, facts: dict | None = None) -> dict:
        category, priority = result["category"], result["priority"]
        rows = self.matrix[self.matrix.category.eq(category) & self.matrix.priority.eq(priority)]
        row = rows.iloc[0] if len(rows) else None
        low_conf = float(result.get("confidence", 0)) < 0.60
        required = priority in {"P1", "P2"} or low_conf or (row is not None and str(row.human_approval_required).lower() == "yes")
        team = str(row.team) if row is not None else ("Store Manager" if required else "Operations Analyst")
        channel = str(row.channel) if row is not None else "manual_review"
        sla = int(row.sla_minutes) if row is not None else None
        approval = bool(row is not None and str(row.human_approval_required).lower() == "yes")
        return {
            "mock": True,
            "ticket_id": f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            "category": category,
            "priority": priority,
            "escalation_required": bool(required),
            "team": team,
            "channel": channel,
            "sla_minutes": sla,
            "human_approval_required": approval or priority == "P1" or low_conf,
            "reason": result.get("reasoning", ""),
            "summary": sanitized_prompt[:400],
            "supporting_facts": facts or {},
            "execution_note": "Prepared payload only. No ticket, refund, transfer, vendor claim, or notification was actually submitted."
        }
