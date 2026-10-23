"""Policy retrieval over the supplied Markdown knowledge base.

The retriever is deliberately local and inspectable: it chunks by headings, scores lexical
relevance, and returns citations tied to the exact source file and heading. No policy text is
invented by this module.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from collections import Counter

STOP = set("a an and are as at be but by can could do does for from had has have how i if in into is it me my of on or our please should so that the their them then there this to us was we what when where which why will with would you your again all one any is not".split())


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def tokens(s: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", (s or "").lower())
    return [x for x in raw if x not in STOP and len(x) > 1]

@dataclass
class PolicyChunk:
    file_name: str
    heading: str
    text: str
    citation: str

class PolicyRetriever:
    def __init__(self, knowledge_dir: str | Path):
        self.knowledge_dir = Path(knowledge_dir)
        self.chunks: list[PolicyChunk] = []
        for path in sorted(self.knowledge_dir.glob("*.md")):
            self.chunks.extend(self._parse_file(path))
        if not self.chunks:
            raise RuntimeError(f"No Markdown policy documents found in {self.knowledge_dir}")
        # Inverse document frequency is used to reduce the impact of generic terms.
        docs = [set(tokens(c.heading + " " + c.text)) for c in self.chunks]
        self.idf: Counter[str] = Counter()
        all_terms = set().union(*docs)
        for term in all_terms:
            df = sum(term in doc for doc in docs)
            self.idf[term] = 1.0 + __import__("math").log((1 + len(docs)) / (1 + df))
        self.doc_terms = docs

    def _parse_file(self, path: Path) -> list[PolicyChunk]:
        lines = path.read_text(encoding="utf-8").splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_heading = path.stem.replace("_", " ")
        current_lines: list[str] = []
        for line in lines:
            match = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
            if match:
                if current_lines and "".join(current_lines).strip():
                    sections.append((current_heading, current_lines))
                current_heading = match.group(2).strip()
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines and "".join(current_lines).strip():
            sections.append((current_heading, current_lines))
        out = []
        for heading, block in sections:
            body = "\n".join(block).strip()
            # The document title / metadata chunk is retained because it can be useful
            # when retrieval finds no more specific heading.
            citation = f"{path.name}#{slugify(heading)}"
            out.append(PolicyChunk(path.name, heading, body, citation))
        return out

    def retrieve(self, query: str, top_k: int = 4) -> list[dict]:
        q_terms = set(tokens(query))
        if not q_terms:
            return []
        scored = []
        for chunk, d_terms in zip(self.chunks, self.doc_terms):
            overlap = q_terms & d_terms
            if not overlap:
                continue
            score = sum(self.idf[t] for t in overlap)
            # Exact/near phrase matches in headings are a useful boost.
            heading_terms = set(tokens(chunk.heading))
            score += 1.75 * sum(self.idf[t] for t in (q_terms & heading_terms))
            # Mild normalization prevents very long sections from dominating.
            score /= (1 + 0.015 * max(0, len(d_terms) - 30))
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"citation": c.citation, "file": c.file_name, "section": c.heading,
             "score": round(score, 3), "excerpt": c.text[:1500]}
            for score, c in scored[:top_k]
        ]
