"""Parsing and filtering in the broad-corpus fetchers, on small inputs written for these tests.

No network: each test feeds a fetcher's pure function a synthetic OAI record,
JATS article, HTML page or README.
"""

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


arxiv = load("fetch_arxiv")
readmes = load("fetch_github_readmes")
lay = load("fetch_expert_lay")

OAI = b"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
 <ListRecords>
  <record><header><identifier>oai:arXiv.org:2401.00001</identifier></header>
   <metadata><arXiv xmlns="http://arxiv.org/OAI/arXiv/">
    <id>2401.00001</id><created>2024-01-02</created>
    <title>A  made-up
      title</title>
    <categories>math.CO cs.DM</categories>
    <license>http://creativecommons.org/licenses/by/4.0/</license>
    <abstract>  We count the widgets $w_n$ in a box.
  Then we bound $$\\sum w_n$$ from above.</abstract>
   </arXiv></metadata></record>
  <record><header><identifier>oai:arXiv.org:2401.00002</identifier></header>
   <metadata><arXiv xmlns="http://arxiv.org/OAI/arXiv/">
    <id>2401.00002</id><created>2024-01-03</created><title>Second</title>
    <categories>hep-th</categories>
    <license>http://arxiv.org/licenses/nonexclusive-distrib/1.0/</license>
    <abstract>Text.</abstract>
   </arXiv></metadata></record>
  <resumptionToken cursor="0">tok123</resumptionToken>
 </ListRecords>
</OAI-PMH>"""


def test_oai_records_are_parsed_with_primary_category_and_token():
    recs, token = arxiv.parse_records(OAI)
    assert token == "tok123"
    assert [r["id"] for r in recs] == ["2401.00001", "2401.00002"]
    assert recs[0]["primary"] == "math.CO"
    assert recs[0]["title"] == "A made-up title"
    assert recs[0]["created"] == "2024-01-02"


def test_oai_without_token_returns_none():
    _, token = arxiv.parse_records(OAI.replace(b'<resumptionToken cursor="0">tok123</resumptionToken>', b""))
    assert token is None


@pytest.mark.parametrize("primary, expected", [
    ("cs.LG", "cs"), ("math.CO", "math"), ("q-bio.NC", "q-bio"), ("q-fin.ST", "q-fin"),
    ("hep-th", "physics"), ("astro-ph.GA", "physics"), ("math-ph", "physics"), ("cond-mat.soft", "physics"),
])
def test_primary_category_maps_to_its_oai_set(primary, expected):
    assert arxiv.set_of(primary) == expected


@pytest.mark.parametrize("url, expected", [
    ("http://creativecommons.org/licenses/by/4.0/", "CC-BY-4.0"),
    ("https://creativecommons.org/licenses/by-sa/4.0/", "CC-BY-SA-4.0"),
    ("http://creativecommons.org/publicdomain/zero/1.0/", "CC0-1.0"),
    ("http://creativecommons.org/licenses/by-nc-sa/4.0/", None),
    ("http://creativecommons.org/licenses/by-nc-nd/4.0/", None),
    ("http://arxiv.org/licenses/nonexclusive-distrib/1.0/", None),
    ("", None),
])
def test_arxiv_licence_filter_keeps_only_reusable_licences(url, expected):
    assert arxiv.license_name(url) == expected


def test_tex_math_becomes_a_token_and_indented_lines_start_paragraphs():
    recs, _ = arxiv.parse_records(OAI)
    text = arxiv.strip_tex_math(recs[0]["abstract"])
    assert text == "We count the widgets [MATH] in a box.\n\nThen we bound [MATH] from above."


INTRO_PAGE = """<html><body>
<div class="ltx_abstract"><p class="ltx_p">Abstract text that is not wanted.</p></div>
<section id="S1" class="ltx_section">
<h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">1 </span>Introduction</h2>
<div id="S1.p1" class="ltx_para"><p class="ltx_p">Widgets fill boxes
<cite class="ltx_cite ltx_citemacro_cite">[<a href="#bib.bib1">1</a>]</cite>. A box holds
<math class="ltx_Math" alttext="n"><semantics><mi>n</mi></semantics></math> widgets.<span class="ltx_note ltx_role_footnote">A footnote.</span></p></div>
<figure class="ltx_figure"><p class="ltx_p">Caption text.</p></figure>
<section id="S1.SS1" class="ltx_subsection"><div class="ltx_para"><p class="ltx_p">Second paragraph.</p></div></section>
</section>
<section id="S2" class="ltx_section"><h2 class="ltx_title ltx_title_section">2 Method</h2>
<div class="ltx_para"><p class="ltx_p">Not part of the introduction.</p></div></section>
</body></html>"""


def test_intro_keeps_section_one_paragraphs_without_citations_notes_or_figures():
    text = arxiv.parse_intro(INTRO_PAGE)
    assert text == "Widgets fill boxes. A box holds [MATH] widgets.\n\nSecond paragraph.\n"


def test_intro_is_none_when_section_one_is_not_an_introduction():
    page = INTRO_PAGE.replace("</span>Introduction</h2>", "</span>Background</h2>")
    assert arxiv.parse_intro(page) is None


JATS = """<article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:ali="http://www.niso.org/schemas/ali/1.0/">
<front><article-meta>
<permissions><license>{licence}</license></permissions>
<abstract><title>Abstract</title><p>Experts measured the widget flux
<xref ref-type="bibr" rid="b1">[1]</xref> at <inline-formula><tex-math>x^2</tex-math></inline-formula> scale.</p>
<p>Second expert paragraph.</p></abstract>
<abstract abstract-type="{lay_type}"><title>Author summary</title><p>We looked at how widgets move.</p></abstract>
<abstract abstract-type="teaser"><p>Teaser.</p></abstract>
</article-meta></front>
<body><sec><p>Body text.</p></sec></body></article>"""

CC_BY = ('<ali:license_ref>https://creativecommons.org/licenses/by/4.0/</ali:license_ref>'
         '<license-p>Distributed under a Creative Commons licence.</license-p>')
CC_BY_TEXT = ('<license-p>Distributed under the terms of the <ext-link xlink:href='
              '"https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution License</ext-link>.</license-p>')
CC_BY_NC = ('<license-p>Distributed under <ext-link xlink:href='
            '"https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC</ext-link>.</license-p>')
CC_BY_NC_NAMED = ('<license-p>Under the <ext-link xlink:href="https://creativecommons.org/licenses/by-nc/4.0/">'
                  'Creative Commons Attribution License</ext-link>, non-commercial use only.</license-p>')
CC0 = '<license-p>Public domain: <ext-link xlink:href="https://creativecommons.org/publicdomain/zero/1.0/">CC0</ext-link>.</license-p>'


def jats(licence=CC_BY, lay_type="summary"):
    return ET.fromstring(JATS.format(licence=licence, lay_type=lay_type))


@pytest.mark.parametrize("licence, expected", [
    (CC_BY, "CC-BY-4.0"), (CC_BY_TEXT, "CC-BY-4.0"), (CC0, "CC0-1.0"), (CC_BY_NC, None), (CC_BY_NC_NAMED, None),
    ("<license-p>All rights reserved.</license-p>", None),
])
def test_jats_licence_filter(licence, expected):
    assert lay.jats_licence(jats(licence)) == expected


@pytest.mark.parametrize("lay_type", ["summary", "plain-language-summary", "executive-summary"])
def test_jats_abstract_and_lay_summary_are_separated(lay_type):
    expert, summaries = lay.jats_abstracts(jats(lay_type=lay_type))
    assert expert == ["Experts measured the widget flux at [MATH] scale.\n\nSecond expert paragraph."]
    assert summaries == ["We looked at how widgets move."]


def test_jats_other_abstract_types_are_neither_side():
    expert, summaries = lay.jats_abstracts(jats(lay_type="graphical"))
    assert len(expert) == 1 and summaries == []


def test_wiki_extract_drops_headings_and_trailing_reference_sections():
    raw = "Lead.\n\n== History ==\nOld.\n\n=== Early ===\nOlder.\n\n== See also ==\nOther page\n\n== Notes ==\n1\n"
    assert lay.clean_extract(raw) == "Lead.\n\nOld.\n\nOlder.\n"


def prose(n: int) -> str:
    return " ".join(["word"] * n)


def test_readme_prose_ignores_code_tables_html_and_badges():
    md = "\n".join([
        "# Title", "[![build](https://example.invalid/b.svg)](https://example.invalid)",
        "```sh", prose(200), "```", "| a | b |", "|---|---|", f"| {prose(50)} | x |",
        "<table><tr><td>" + prose(50) + "</td></tr></table>",
        "    " + prose(40), "This tool reads [the files](https://example.invalid) you give it.",
    ])
    assert readmes.prose_text(md) == "This tool reads the files you give it."


def test_readme_kept_only_with_enough_english_prose():
    def english(_):
        return None

    def french(_):
        return "fr"

    short = "This is a short readme with too few words to count."
    assert readmes.keep_readme(short, english) == "under 100 words of prose"
    long_ = "This library parses widget files and reports what it finds in them. " * 12
    assert readmes.keep_readme(long_, english) is None
    assert readmes.keep_readme(long_, french) == "not English (fr)"


def test_readme_language_filter_with_readcost_lang():
    from readcost.lang import other_language

    french = ("Cette bibliothèque lit les fichiers et elle les transforme pour vous, avec une "
              "interface simple et des exemples dans la documentation qui est en ligne. ") * 10
    assert readmes.keep_readme(french, other_language).startswith("not English")


@pytest.mark.parametrize("licence, expected", [
    ({"spdx_id": "MIT"}, "MIT"), ({"spdx_id": "Apache-2.0"}, "Apache-2.0"),
    ({"spdx_id": "NOASSERTION"}, None), (None, None),
])
def test_readme_licence_filter(licence, expected):
    assert readmes.licence_ok({"license": licence}) == expected


def test_readme_format_from_file_name():
    assert readmes.readme_format("README.md") == "markdown"
    assert readmes.readme_format("README.rst") == "rst"
    assert readmes.readme_format("README") == "text"
