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


se = load("fetch_stackexchange")
design = load("fetch_design_docs")
mdn = load("fetch_mdn")
man = load("fetch_man_pages")
releases = load("fetch_release_notes")


def test_se_html_drops_code_blocks_and_quotes_and_keeps_inline_code():
    body = ("<p>Use <code>ls -l</code> to list\nfiles.</p>\n<pre><code>ls -l /tmp\n</code></pre>\n"
            "<blockquote><p>Quoted text.</p></blockquote>\n<ul>\n<li>First item.</li>\n<li>Second &amp; last.</li>\n</ul>")
    assert se.html_to_text(body) == "Use `ls -l` to list files.\n\nFirst item.\n\nSecond & last.\n"


def test_se_tex_becomes_math_token_only_on_math_sites():
    body = "<p>Let $x_n$ tend to $$0$$ fast.</p>"
    assert se.html_to_text(body, math=True) == "Let [MATH] tend to [MATH] fast.\n"
    assert "$x_n$" in se.html_to_text(body)


def test_se_prose_words_skip_inline_code():
    assert se.prose_words("Run `make all now` and wait.") == 3


def test_se_revisions_pair_first_with_last_and_skip_vote_events():
    revs = [{"post_id": 1, "revision_number": 2, "body": "b"}, {"post_id": 1, "revision_number": 3, "body": "c"},
            {"post_id": 1, "revision_number": 1, "body": "a"}, {"post_id": 1, "revision_type": "vote_based"},
            {"post_id": 2, "revision_number": 1, "body": "only"},
            {"post_id": 3, "revision_number": 4, "body": "x"}, {"post_id": 3, "revision_number": 5, "body": "y"}]
    pairs = se.pair_revisions(revs)
    assert list(pairs) == [1]
    assert (pairs[1][0]["body"], pairs[1][1]["body"]) == ("a", "c")


def test_design_doc_cleaning_drops_comments_toc_checklists_and_header_metadata():
    md = ("# Proposal: widgets\n\nAuthor(s): Someone\n\nLast updated: 2020-01-01\n\n<!-- toc -->\n- [Summary](#summary)\n"
          "<!-- /toc -->\n\n## Summary\n\n<!--\nTemplate advice.\n-->\nWidgets help.\n\n- [ ] Approved\n- [x] Tested\n\n"
          "```\nauthor: kept in code\n```\n")
    assert design.clean_design_doc(md) == ("# Proposal: widgets\n\n## Summary\n\nWidgets help.\n\n"
                                           "```\nauthor: kept in code\n```\n")


def test_design_doc_start_date_and_even_spacing():
    assert design.start_date("- Start Date: 2015-03-04\n- RFC PR: x") == "2015-03-04"
    assert design.start_date("no header") is None
    assert design.evenly(list(range(10)), 4) == [0, 3, 6, 9]
    assert design.evenly([1, 2], 5) == [1, 2]


def test_mdn_front_matter_is_split_from_the_body():
    meta, body = mdn.split_front_matter('---\ntitle: "Widget"\nslug: Web/API/Widget\npage-type: web-api-interface\n'
                                        "browser-compat: api.Widget\n---\n\nBody.\n")
    assert meta["page-type"] == "web-api-interface" and meta["slug"] == "Web/API/Widget"
    assert body == "\nBody.\n"


def test_mdn_macros_resolve_to_display_text_and_reference_sections_drop():
    body = ('{{APIRef("Widgets")}}\n\nThe {{domxref("Widget.spin", "spin()")}} method of {{domxref("Widget")}} '
            'turns a {{Glossary("widget")}}.{{experimental_inline}}\n\n> [!NOTE]\n> Spin gently.\n\n'
            "## Specifications\n\n{{Specifications}}\n\n## Browser compatibility\n\n{{Compat}}\n\n## See also\n\n- A link\n")
    assert mdn.clean_mdn(body) == "The spin() method of Widget turns a widget.\n\n> Spin gently.\n"


@pytest.mark.parametrize("page_type, group", [
    ("guide", "guide"), ("learn-module-chapter", "guide"), ("learn-module-assessment", "guide"), ("tutorial-chapter", "guide"),
    ("web-api-interface", "reference"), ("css-property", "reference"), ("landing-page", None), ("", None),
])
def test_mdn_page_type_groups(page_type, group):
    assert mdn.group_of(page_type) == group


def test_mdn_guide_paths():
    assert mdn.is_guide_path("web/css/guides/flexbox/index.md")
    assert mdn.is_guide_path("learn_web_development/core/styling/index.md")
    assert not mdn.is_guide_path("web/api/widget/index.md")


@pytest.mark.parametrize("header, expected", [
    ('.\\" SPDX-License-Identifier: Linux-man-pages-copyleft\n', "Linux-man-pages-copyleft"),
    ('.\\" Permission to use, copy, modify, and distribute this software for any\n.\\" purpose\n', "ISC"),
    (('.\\" Redistribution and use in source and binary forms, with or without\n.\\" 1. Kept.\n.\\" 2. Kept.\n'
      '.\\" 3. Neither the name\n'), "BSD-3-Clause"),
    ('.\\" Redistribution and use in source and binary forms\n.\\" 1. Kept.\n.\\" 2. Kept.\n', "BSD-2-Clause"),
    ('.\\" Redistribution and use in source and binary forms\n.\\" 3. All advertising materials mentioning\n',
     "BSD-4-Clause"),
    ('.\\" This file is in the public domain.\n', "public domain"),
    ('.\\" Copyright someone. All rights reserved.\n', None),
])
def test_man_page_licence_classification(header, expected):
    assert man.page_licence(header + ".Dd today\n") == expected


def test_man_description_section_is_unwrapped_into_paragraphs():
    rendered = ("WIDGET(1)    General Commands Manual    WIDGET(1)\n\nNAME\n     widget - spin widgets\n\n"
                "DESCRIPTION\n     The widget utility spins\n     widgets.\n\n     -f      Spin fast.\n\n"
                "EXIT STATUS\n     0 on success.\n")
    assert man.description(rendered) == "The widget utility spins widgets.\n\n-f      Spin fast.\n"
    assert man.description("NAME\n     x\n") == ""


@pytest.mark.skipif(__import__("shutil").which("mandoc") is None, reason="needs mandoc")
def test_man_render_with_mandoc_keeps_description():
    src = (b".Dd January 1, 2020\n.Dt WIDGET 1\n.Os\n.Sh NAME\n.Nm widget\n.Nd spin widgets\n"
           b".Sh DESCRIPTION\nThe\n.Nm\nutility spins widgets\nquickly.\n.Sh EXIT STATUS\nZero.\n")
    assert man.description(man.render(src)) == "The widget utility spins widgets quickly.\n"


def test_release_generated_detection():
    assert releases.is_generated("## What's Changed\n* Fix by @a in https://x/pull/1\n")
    assert releases.is_generated("Notes.\n\n**Full Changelog**: https://x/compare/a...b\n")
    assert not releases.is_generated("## Highlights\n\nWidgets now spin.\n")


def test_release_cleaning_keeps_titles_and_drops_link_only_lines_and_contributors():
    body = ("## What's Changed\r\n* Make widgets spin by @alice in https://github.com/o/r/pull/12\r\n"
            "* https://github.com/o/r/pull/13\r\n* #14\r\n- abc1234 (@bob)\r\nThanks @carol for the review.\r\n\r\n"
            "## New Contributors\r\n* @dave made their first contribution in https://github.com/o/r/pull/9\r\n\r\n"
            "**Full Changelog**: https://github.com/o/r/compare/v1...v2\r\n")
    assert releases.clean_release(body) == "## What's Changed\n* Make widgets spin\nThanks  for the review.\n"


domains = load("fetch_domains")


def test_gutenberg_body_keeps_only_the_text_between_start_and_end():
    book = ("Header about the project and its licence.\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK A MADE-UP BOOK ***\n\nThe story.\n\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK A MADE-UP BOOK ***\nLicence text.\n")
    assert domains.gutenberg_body(book).strip() == "The story."
    assert domains.gutenberg_body("No markers here.") is None


def test_gutenberg_paragraphs_are_unwrapped_and_headings_dropped():
    body = ("CHAPTER ONE\n\nThe widget maker walked down\nthe long road to the market _every_ day\n"
            "and sold what he made there.\n\n* * *\n\nShort line.\n")
    assert domains.unwrap_paragraphs(body) == [
        "The widget maker walked down the long road to the market every day and sold what he made there."]


def test_passages_are_whole_paragraph_runs_within_the_word_range():
    import random

    paras = [" ".join(["word"] * 100) for _ in range(60)]
    got = domains.passages(paras, random.Random(1), 3)
    assert len(got) == 3
    assert all(400 <= len(p.split()) <= 800 for p in got)
    assert all(p.count("\n\n") == 3 for p in got)          # four paragraphs of 100 words


@pytest.mark.parametrize("row, expected", [
    ({"Language": "en", "Type": "Text", "LoCC": "PR", "Authors": "Doe, Jane, 1800-1870",
      "Subjects": "England -- Fiction"}, "novel"),
    ({"Language": "en", "Type": "Text", "LoCC": "PS", "Authors": "Roe, Al, 1850-1920",
      "Subjects": "American essays"}, "essay"),
    ({"Language": "en", "Type": "Text", "LoCC": "PS", "Authors": "Roe, Al, 1850-1920",
      "Subjects": "Essays; Nature"}, "essay"),
    ({"Language": "en", "Type": "Text", "LoCC": "PR", "Authors": "Doe, Jane, 1900-1980",
      "Subjects": "Fiction"}, None),                                     # died too late
    ({"Language": "fr", "Type": "Text", "LoCC": "PQ", "Authors": "Doe, Jean, 1800-1870",
      "Subjects": "Fiction"}, None),
    ({"Language": "en", "Type": "Text", "LoCC": "PR", "Authors": "Doe, Jane, 1800-1870",
      "Subjects": "Juvenile fiction"}, None),
])
def test_literature_eligibility(row, expected):
    assert domains.literature_kind(row) == expected


def test_wikinews_extract_drops_dateline_headings_and_sources():
    raw = "Monday, March 1, 2010\n\nLead paragraph.\n\n== Details ==\nMore.\n\n== Sources ==\nA source\n"
    assert domains.clean_wiki(raw, dateline=True) == "Lead paragraph.\n\nMore.\n"


@pytest.mark.parametrize("section, topic", [
    ("History", "history"), ("Warfare", "history"), ("Paintings", "arts"), ("Music", "arts"),
    ("Music biographies", "biography"), ("Biographies (art, architecture, and archaeology)", "biography"),
    ("Biology", None), ("Video gaming", None),
])
def test_featured_article_sections_map_to_topics(section, topic):
    assert domains.featured_topic(section) == topic


def test_federal_register_text_starts_at_supplementary_information():
    raw = ("<html><pre>[Federal Register Volume 1]\nSUMMARY: Not wanted.\n\n"
           "SUPPLEMENTARY INFORMATION: The agency made\na rule about widgets.\n"
           "    A second paragraph\n[[Page 12]]\ncontinues here.\n\n"
           "-----\n\nBILLING CODE 1234-56-P\nTrailing.</pre></html>")
    assert domains.federal_register_text(raw) == (
        "The agency made a rule about widgets.\n\nA second paragraph continues here.")


def test_uk_notes_text_elements_in_order():
    xml = (b'<EN xmlns="http://www.legislation.gov.uk/namespaces/legislation" '
           b'xmlns:dc="http://purl.org/dc/elements/1.1/"><Metadata><dc:title>Notes to a Made-up Act</dc:title>'
           b'</Metadata><P><Text>These notes relate to\n the Act.</Text></P><P><Text>Second <Emphasis>one</Emphasis>.'
           b'</Text></P></EN>')
    assert domains.uk_notes_paragraphs(xml) == ("Notes to a Made-up Act", ["These notes relate to the Act.", "Second one."])


def test_only_a_single_lead_opinion_is_taken():
    lead = {"type": "020lead", "opinion_text": "The court holds."}
    assert domains.lead_opinion({"opinions": [lead, {"type": "040dissent", "opinion_text": "No."}]}) == lead
    assert domains.lead_opinion({"opinions": [{"type": "010combined", "opinion_text": "All."}]}) is None
    assert domains.lead_opinion({"opinions": [lead, lead]}) is None


def test_cap_paragraphs_stops_at_the_first_paragraph_end_past_the_cap():
    paras = ["one two three", "four five", "six seven eight", "nine"]
    assert domains.cap_paragraphs(paras, 4) == ["one two three", "four five"]


def test_medline_topics_keep_english_summaries():
    xml = (b'<health-topics><health-topic id="1" title="Widgets" url="https://example.invalid/w" language="English">'
           b'<full-summary>&lt;p&gt;About widgets.&lt;/p&gt;</full-summary></health-topic>'
           b'<health-topic id="2" title="Widgets" language="Spanish"><full-summary>x</full-summary></health-topic>'
           b'</health-topics>')
    assert domains.medline_topics(xml) == [
        {"id": "1", "title": "Widgets", "url": "https://example.invalid/w", "summary": "<p>About widgets.</p>"}]


def test_openalex_abstract_is_rebuilt_in_word_order():
    index = {"Abstract": [0], "Widgets": [1], "are": [2, 5], "small.": [3], "They": [4], "useful.": [6]}
    assert domains.rebuild_abstract(index) == "Widgets are small. They are useful."
    assert domains.rebuild_abstract(None) == ""


def test_federal_register_text_without_supplementary_information_starts_after_the_header_rule():
    raw = ("<html><head><title>Federal Register, Volume 1</title></head><pre>[Federal Register Volume 1]\n"
           "[Notices]\n\n" + "-" * 40 + "\n\nDEPARTMENT OF WIDGETS\n\nThe department asks for comments.\n</pre></html>")
    assert domains.federal_register_text(raw) == "DEPARTMENT OF WIDGETS\n\nThe department asks for comments."


def test_opinion_paragraphs_drop_star_page_markers():
    text = "The court affirms the ruling below.\n*2Plaintiffs sued the widget company for damages.\n"
    assert domains.opinion_paragraphs(text) == ["The court affirms the ruling below.",
                                                 "Plaintiffs sued the widget company for damages."]
