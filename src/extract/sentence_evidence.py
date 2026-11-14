"""Evidence by sentence number instead of quoted snippet (experimental).

The model sees the document with every sentence numbered ``[S1]``, ``[S2]``,
... and cites a number for each piece of evidence; code then pulls the
sentence itself as the snippet. Two effects, both measured by
scripts/compare_extraction_models.py before anything here reaches the
pipeline (2026-11-14):

- a sentence number is a few output tokens where a quote is ~50, and output
  is the expensive side of the bill;
- a fabricated quote becomes impossible: the snippet is copied from the
  text, so the evidence-fidelity gate checks the citation, not the copying.

Not wired into production extraction. Domain-agnostic by construction.
"""

from __future__ import annotations

import re
from typing import Any

# A sentence ends at . ! or ? followed by whitespace and something that can
# start a sentence. Abbreviations ("U.S. Commerce") over-split, which only
# yields more, shorter sentences -- harmless for citation. Decimals ("3.5 nm")
# have no whitespace after the point and never split. A closing quote or
# bracket after the stop stays with its sentence (two fixed-width
# lookbehinds, since Python's must be fixed-width).
_SENTENCE_BREAK = re.compile(
    r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]]))\s+(?=[\"'“‘(\[]?[A-Z0-9])"
)

# A whole sentence is the quote. 200 chars is the snippet guideline, but in
# the 2026-11-14 sample (50 semiconductors docs) sentences ran median 113,
# p90 259, and 19% over 200 -- cutting at 200 would drop the clause that
# carries the claim. 400 bounds runaway lines (nav junk with no stops);
# over_200 in the stats shows how often the guideline is exceeded.
SNIPPET_MAX_CHARS = 400


def number_sentences(text: str) -> tuple[str, list[str]]:
    """Return (numbered text for the prompt, sentences indexed from 1).

    ``sentences[0]`` is an empty placeholder so ``sentences[n]`` is the
    sentence the model saw as ``[Sn]``. Paragraph breaks are kept.
    """
    sentences = [""]
    paragraphs_out: list[str] = []
    for paragraph in re.split(r"\n\s*\n|\n", text):
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        numbered = []
        for s in _SENTENCE_BREAK.split(paragraph):
            s = s.strip()
            if not s:
                continue
            sentences.append(s)
            numbered.append(f"[S{len(sentences) - 1}] {s}")
        paragraphs_out.append(" ".join(numbered))
    return "\n\n".join(paragraphs_out), sentences


def _snippet(sentence: str, max_chars: int) -> tuple[str, bool]:
    if len(sentence) <= max_chars:
        return sentence, False
    cut = sentence[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut, True


def resolve_sentence_evidence(
    data: dict[str, Any],
    sentences: list[str],
    max_chars: int = SNIPPET_MAX_CHARS,
) -> dict[str, int]:
    """Turn ``{"sentence": n}`` evidence into ``{"snippet": ...}`` in place.

    A citation outside ``1..len(sentences)-1`` is dropped and counted -- the
    sentence-number analogue of a fabricated quote. An asserted relation
    left with no valid evidence is dropped (the schema requires evidence on
    asserted relations), and counted too, so a bad citation costs that one
    claim rather than failing the whole document.

    Returns counts: cited, invalid, over_200, truncated, relations_dropped.
    """
    stats = {"cited": 0, "invalid": 0, "over_200": 0, "truncated": 0,
             "relations_dropped": 0}
    kept_relations = []
    for relation in data.get("relations") or []:
        if not isinstance(relation, dict):
            kept_relations.append(relation)
            continue
        new_evidence = []
        for ev in relation.get("evidence") or []:
            n = ev.get("sentence") if isinstance(ev, dict) else None
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n < len(sentences):
                stats["invalid"] += 1
                continue
            snippet, truncated = _snippet(sentences[n], max_chars)
            stats["cited"] += 1
            stats["over_200"] += len(sentences[n]) > 200
            stats["truncated"] += truncated
            rest = {k: v for k, v in ev.items() if k != "sentence"}
            new_evidence.append({"snippet": snippet, **rest})
        relation["evidence"] = new_evidence
        if relation.get("kind") == "asserted" and not new_evidence:
            stats["relations_dropped"] += 1
            continue
        kept_relations.append(relation)
    if "relations" in data:
        data["relations"] = kept_relations
    return stats
