"""Text that is clearly not English gets a note, not findings or a reading time."""

import pytest

from readcost import Analyzer, Config
from readcost.lang import other_language

# Constructed for the test, each about the same index and cache.
EN = ("The index serves queries and is rebuilt on compaction. It does not own the cache, which the "
      "caller keeps. Each segment is written once and then only read by the query workers.")
OTHER = {
    "de": ("Der Index beantwortet Anfragen und wird bei der Verdichtung neu aufgebaut. Er besitzt den Cache "
           "nicht, den der Aufrufer behält, und jedes Segment wird nur einmal geschrieben."),
    "es": ("El índice responde a las consultas y se reconstruye al compactar. No es dueño de la caché, que "
           "conserva quien lo llama, y cada segmento se escribe una sola vez."),
    "nl": ("De index beantwoordt vragen en wordt opnieuw opgebouwd bij compactie. Hij bezit de cache niet, "
           "die de aanroeper houdt, en elk segment wordt maar een keer geschreven."),
    "a non-Latin script": ("Индекс обслуживает запросы и перестраивается при уплотнении. Он не владеет "
                           "кэшем, который хранит вызывающий код, и каждый сегмент пишется один раз."),
}


@pytest.mark.parametrize("lang,text", OTHER.items())
def test_other_languages_are_named(lang, text):
    assert other_language(text) == lang


@pytest.mark.parametrize("text", [
    EN,
    "Fix race in WAL rotation; add regression test for fsync ordering on Linux and macOS builds in CI today.",
    "Call parse() on each token, then pass the result to compile() with the flags and options set by the caller.",
    "Der Index.",  # too short to judge: assumed English
])
def test_english_and_short_text_pass(text):
    assert other_language(text) is None


def test_analyzer_skips_other_languages_with_a_note_unless_turned_off():
    r = Analyzer(Config()).check_text(OTHER["de"], "markdown")
    assert r.findings == [] and r.reading_seconds is None and r.words == 0
    assert r.notes and r.notes[0].startswith("text looks like de, not English")
    r = Analyzer(Config(language_check=False)).check_text(OTHER["de"], "markdown")
    assert r.words > 0 and r.reading_seconds is not None
