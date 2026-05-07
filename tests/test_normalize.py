"""Tests for normalization functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bibtool.normalize import normalize_arxiv, normalize_author, normalize_doi, normalize_title


class TestNormalizeTitle:
    def test_lowercase(self):
        assert normalize_title("Hello World") == "hello world"

    def test_latex_braces(self):
        assert normalize_title("{BERT}: Pre-training") == "bert pre training"

    def test_punctuation(self):
        assert normalize_title("Hello, World!") == "hello world"

    def test_whitespace(self):
        assert normalize_title("  hello   world  ") == "hello world"

    def test_empty(self):
        assert normalize_title("") == ""
        assert normalize_title(None) == ""

    def test_complex(self):
        result = normalize_title("Attention is All You Need")
        assert result == "attention is all you need"


class TestNormalizeDoi:
    def test_url_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"

    def test_doi_prefix(self):
        assert normalize_doi("doi:10.1234/abc") == "10.1234/abc"

    def test_plain(self):
        assert normalize_doi("10.1234/abc") == "10.1234/abc"

    def test_case(self):
        assert normalize_doi("10.1234/ABC") == "10.1234/abc"

    def test_empty(self):
        assert normalize_doi("") == ""
        assert normalize_doi(None) == ""


class TestNormalizeAuthor:
    def test_last_first_format(self):
        assert normalize_author("Rafailov, Rafael") == "rafailov"

    def test_first_last_format(self):
        assert normalize_author("Rafael Rafailov") == "rafailov"

    def test_multiple_authors(self):
        result = normalize_author("Rafailov, Rafael and Sharma, Archit")
        assert result == "rafailov"

    def test_braces(self):
        assert normalize_author("{Devlin}, Jacob") == "devlin"

    def test_empty(self):
        assert normalize_author("") == ""
        assert normalize_author(None) == ""


class TestNormalizeArxiv:
    def test_eprint_field(self):
        entry = {"eprint": "2305.18290"}
        assert normalize_arxiv(entry) == "2305.18290"

    def test_url_field(self):
        entry = {"url": "https://arxiv.org/abs/2011.13456"}
        assert normalize_arxiv(entry) == "2011.13456"

    def test_versioned(self):
        entry = {"eprint": "2305.18290v2"}
        assert normalize_arxiv(entry) == "2305.18290v2"

    def test_no_arxiv(self):
        entry = {"doi": "10.1234/abc"}
        assert normalize_arxiv(entry) == ""

    def test_empty(self):
        assert normalize_arxiv({}) == ""
