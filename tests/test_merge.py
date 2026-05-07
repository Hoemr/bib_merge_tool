"""Tests for merge strategies."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bibtool.keygen import generate_key, resolve_key_conflicts
from bibtool.merge import auto_merge_group
from bibtool.search import search_entries


class TestAutoMerge:
    def test_prefers_nonempty_doi(self):
        group = [
            {"ID": "a", "ENTRYTYPE": "article", "title": "Paper", "doi": ""},
            {"ID": "b", "ENTRYTYPE": "article", "title": "Paper", "doi": "10.1234/abc"},
        ]
        merged = auto_merge_group(group)
        assert merged["doi"] == "10.1234/abc"

    def test_prefers_journal_over_booktitle(self):
        group = [
            {"ID": "a", "ENTRYTYPE": "article", "title": "Paper", "booktitle": "ICML"},
            {"ID": "b", "ENTRYTYPE": "article", "title": "Paper", "journal": "JMLR"},
        ]
        merged = auto_merge_group(group)
        assert merged.get("journal") == "JMLR"
        assert "booktitle" not in merged

    def test_prefers_longer_title(self):
        group = [
            {"ID": "a", "ENTRYTYPE": "article", "title": "Short"},
            {"ID": "b", "ENTRYTYPE": "article", "title": "A Much Longer and More Descriptive Title"},
        ]
        merged = auto_merge_group(group)
        assert merged["title"] == "A Much Longer and More Descriptive Title"

    def test_strips_dirty_fields(self):
        group = [
            {"ID": "a", "ENTRYTYPE": "article", "title": "T", "abstract": "long abstract", "keywords": "kw", "file": "f.pdf"},
        ]
        merged = auto_merge_group(group, keep_extras=False)
        assert "abstract" not in merged
        assert "keywords" not in merged
        assert "file" not in merged

    def test_keeps_extras_when_flagged(self):
        group = [
            {"ID": "a", "ENTRYTYPE": "article", "title": "T", "abstract": "abs"},
        ]
        merged = auto_merge_group(group, keep_extras=True)
        assert merged.get("abstract") == "abs"

    def test_prefers_nonempty_pages(self):
        group = [
            {"ID": "a", "ENTRYTYPE": "article", "title": "T", "pages": ""},
            {"ID": "b", "ENTRYTYPE": "article", "title": "T", "pages": "1--15"},
        ]
        merged = auto_merge_group(group)
        assert merged["pages"] == "1--15"


class TestKeyGeneration:
    def test_basic_key(self):
        entry = {"author": "Rafailov, Rafael", "title": "Direct Preference Optimization", "year": "2023"}
        key = generate_key(entry)
        assert key == "rafailov2023direct"

    def test_key_with_latex(self):
        entry = {"author": "Devlin, Jacob", "title": "{BERT}: Pre-training of Deep Bidirectional Transformers", "year": "2019"}
        key = generate_key(entry)
        assert key == "devlin2019bert"

    def test_conflict_resolution(self):
        entries = [
            {"ID": "smith2020paper", "author": "Smith", "title": "Paper", "year": "2020"},
            {"ID": "smith2020paper", "author": "Smith", "title": "Paper", "year": "2020"},
        ]
        resolve_key_conflicts(entries, preserve_existing=True)
        assert entries[0]["ID"] == "smith2020paper"
        assert entries[1]["ID"] == "smith2020papera"

    def test_conflict_abc(self):
        entries = [
            {"ID": "", "author": "Smith", "title": "Test Paper", "year": "2020"},
            {"ID": "", "author": "Smith", "title": "Test Paper", "year": "2020"},
            {"ID": "", "author": "Smith", "title": "Test Paper", "year": "2020"},
        ]
        resolve_key_conflicts(entries, preserve_existing=False)
        keys = [e["ID"] for e in entries]
        # All keys should be unique
        assert len(set(keys)) == 3


class TestSearch:
    def _make_entries(self):
        return [
            {"ID": "a", "title": "Attention is All You Need", "author": "Vaswani", "year": "2017", "doi": "10.1234/att"},
            {"ID": "b", "title": "BERT Pre-training", "author": "Devlin", "year": "2019", "doi": "10.1234/bert"},
            {"ID": "c", "title": "GPT-3 Language Models", "author": "Brown", "year": "2020", "journal": "NeurIPS"},
        ]

    def test_search_by_title(self):
        results = search_entries(self._make_entries(), "attention")
        assert len(results) == 1
        assert results[0]["ID"] == "a"

    def test_search_by_author(self):
        results = search_entries(self._make_entries(), "devlin")
        assert len(results) == 1
        assert results[0]["ID"] == "b"

    def test_search_by_doi(self):
        results = search_entries(self._make_entries(), "10.1234/bert")
        assert len(results) == 1

    def test_search_multi_keyword_and(self):
        results = search_entries(self._make_entries(), "language models")
        assert len(results) == 1
        assert results[0]["ID"] == "c"

    def test_search_case_insensitive(self):
        results = search_entries(self._make_entries(), "ATTENTION")
        assert len(results) == 1

    def test_search_empty_query(self):
        results = search_entries(self._make_entries(), "")
        assert len(results) == 3
