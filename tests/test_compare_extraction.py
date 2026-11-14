"""Tests for the extraction model comparison (no network, no LLM).

Covers sentence-number evidence (src/extract/sentence_evidence.py) and the
offline parts of scripts/compare_extraction_models.py: prompt rewriting,
schema shape, and the overlap maths the report is built on.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from extract import ANTHROPIC_EXTRACTION_SCHEMA
from extract.sentence_evidence import number_sentences, resolve_sentence_evidence

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_extraction_models.py"
_spec = importlib.util.spec_from_file_location("compare_extraction_models", _SCRIPT)
cem = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cem   # dataclasses look their module up here
_spec.loader.exec_module(cem)


class TestNumberSentences:
    def test_numbers_sentences_and_keeps_paragraphs(self):
        text = "TSMC ships N2. Yields are up!\n\nIntel waits. Why? Nobody knows."
        numbered, sentences = number_sentences(text)
        assert sentences[1:] == ["TSMC ships N2.", "Yields are up!", "Intel waits.",
                                 "Why?", "Nobody knows."]
        assert numbered == ("[S1] TSMC ships N2. [S2] Yields are up!\n\n"
                            "[S3] Intel waits. [S4] Why? [S5] Nobody knows.")

    def test_decimals_and_lowercase_continuations_do_not_split(self):
        _, sentences = number_sentences("The 3.5 nm node beat Inc. rivals by 2.1x. Next one.")
        assert sentences[1:] == ["The 3.5 nm node beat Inc. rivals by 2.1x.", "Next one."]

    def test_closing_quote_stays_with_its_sentence(self):
        _, sentences = number_sentences('He said "yes." Then left.')
        assert sentences[1:] == ['He said "yes."', "Then left."]

    def test_empty_text(self):
        numbered, sentences = number_sentences("")
        assert numbered == "" and sentences == [""]


class TestResolveSentenceEvidence:
    SENTENCES = ["", "Acme buys Globex.", "x" * 450 + " tail", "y" * 250]

    def _data(self, *evidence, kind="asserted"):
        return {"relations": [{"source": "Acme", "rel": "ACQUIRES", "target": "Globex",
                               "kind": kind, "confidence": 0.9, "evidence": list(evidence)}]}

    def test_valid_citation_becomes_snippet(self):
        data = self._data({"sentence": 1})
        stats = resolve_sentence_evidence(data, self.SENTENCES)
        assert data["relations"][0]["evidence"] == [{"snippet": "Acme buys Globex."}]
        assert stats == {"cited": 1, "invalid": 0, "over_200": 0, "truncated": 0,
                         "relations_dropped": 0}

    def test_sentence_over_200_is_kept_whole_and_counted(self):
        data = self._data({"sentence": 3})
        stats = resolve_sentence_evidence(data, self.SENTENCES)
        assert data["relations"][0]["evidence"][0]["snippet"] == "y" * 250
        assert (stats["over_200"], stats["truncated"]) == (1, 0)

    def test_invalid_citations_are_dropped_and_counted(self):
        data = self._data({"sentence": 1}, {"sentence": 0}, {"sentence": 99},
                          {"sentence": True}, {"sentence": "1"})
        stats = resolve_sentence_evidence(data, self.SENTENCES)
        assert len(data["relations"][0]["evidence"]) == 1
        assert stats["invalid"] == 4

    def test_asserted_relation_with_no_valid_evidence_is_dropped(self):
        data = self._data({"sentence": 42})
        stats = resolve_sentence_evidence(data, self.SENTENCES)
        assert data["relations"] == [] and stats["relations_dropped"] == 1

    def test_hypothesis_without_evidence_is_kept(self):
        data = self._data({"sentence": 42}, kind="hypothesis")
        resolve_sentence_evidence(data, self.SENTENCES)
        assert len(data["relations"]) == 1 and data["relations"][0]["evidence"] == []

    def test_runaway_sentence_is_truncated_on_a_word_boundary(self):
        data = self._data({"sentence": 2})
        stats = resolve_sentence_evidence(data, self.SENTENCES)
        snippet = data["relations"][0]["evidence"][0]["snippet"]
        assert len(snippet) <= 400 and stats["truncated"] == 1
        assert self.SENTENCES[2].startswith(snippet)   # still a quote of the text


class TestArmRequests:
    def test_sentence_schema_replaces_only_evidence(self):
        schema = cem.sentence_schema()
        ev = schema["properties"]["relations"]["items"]["properties"]["evidence"]["items"]
        assert ev["required"] == ["sentence"]
        assert ev["properties"]["sentence"]["type"] == "integer"
        prod = ANTHROPIC_EXTRACTION_SCHEMA["properties"]["relations"]["items"]
        assert prod["properties"]["evidence"]["items"]["required"] == ["snippet"]

    def test_sub_once_fails_loudly_when_template_moves(self):
        assert cem._sub_once("a\nb\n", r"^b$", "c") == "a\nc\n"
        with pytest.raises(RuntimeError, match="expected 1 match"):
            cem._sub_once("a\nb\nb\n", r"^b$", "c")
        with pytest.raises(RuntimeError, match="expected 1 match"):
            cem._sub_once("a\n", r"^b$", "c")

    def test_thinking_omitted_only_when_arm_says_so(self):
        doc = {"docId": "d", "title": "t", "url": "u", "published": "p", "text": "One. Two."}
        assert "thinking" not in cem.request_params(doc, cem.ARMS["haiku45"])
        assert cem.request_params(doc, cem.ARMS["haiku55"])["thinking"] == {"type": "disabled"}

    def test_every_arm_has_a_rate(self):
        from db import _compute_cost
        for name, arm in cem.ARMS.items():
            assert _compute_cost(arm.model, 1000, 1000, "batch") is not None, name


class TestScoring:
    @staticmethod
    def canon(name, etype):
        return f"{etype.lower()}:{name.lower().replace(' ', '_')}"

    def _ext(self, entities, relations):
        return {"entities": [{"name": n, "type": t} for n, t in entities],
                "relations": [{"source": s, "rel": r, "target": t, "kind": k}
                              for s, r, t, k in relations]}

    def test_compare_counts_overlap(self):
        base = self._ext([("Acme", "Company"), ("Globex", "Company"), ("Bob", "Person")],
                         [("Acme", "ACQUIRES", "Globex", "asserted"),
                          ("Bob", "WORKS_AT", "Acme", "asserted")])
        arm = self._ext([("Acme", "Company"), ("Globex", "Org")],      # Globex typed differently
                        [("Acme", "ACQUIRES", "Globex", "asserted")])
        c = cem.compare(cem.summarize(base, self.canon), cem.summarize(arm, self.canon))
        assert (c["ent_base"], c["ent_arm"], c["ent_both"]) == (3, 2, 1)
        assert (c["name_base"], c["name_both"]) == (3, 2)   # type ignored
        assert (c["rel_base"], c["rel_both"]) == (2, 0)      # Globex resolves elsewhere
        assert c["pair_both"] == 0

    def test_identical_extractions_agree_fully(self):
        ext = self._ext([("Acme", "Company"), ("Globex", "Company")],
                        [("Acme", "PARTNERS_WITH", "Globex", "hypothesis")])
        s = cem.summarize(ext, self.canon)
        c = cem.compare(s, s)
        assert c["ent_both"] == c["ent_base"] and c["rel_both"] == c["rel_base"] == 1
        assert c["kind_same"] == c["kind_both"] == 1

    def test_relation_endpoints_resolve_through_aliases(self):
        ext = {"entities": [{"name": "TSMC", "type": "Company", "aliases": ["Taiwan Semi"]},
                            {"name": "Apple", "type": "Company"}],
               "relations": [{"source": "Taiwan Semi", "rel": "SUPPLIES", "target": "Apple",
                              "kind": "asserted"}]}
        s = cem.summarize(ext, self.canon)
        assert s["triples"] == {("company:tsmc", "SUPPLIES", "company:apple")}
