import re

import pytest

from app.domain.news import (
    CATEGORIES,
    SOURCES,
    TITLE_MAX_LENGTH,
    clean_title,
    is_on_topic,
    link_allowed,
)


def test_the_sources_are_a_fixed_safe_list():
    ids = [source.id for source in SOURCES]
    assert len(ids) == len(set(ids))
    for source in SOURCES:
        assert source.category in CATEGORIES
        # Only https feeds, and every feed lives on a host its links may point to
        assert source.feed_url.startswith("https://")
        host = re.match(r"https://([^/]+)/", source.feed_url)
        assert host and any(host.group(1).endswith(allowed) for allowed in source.hosts)
    # Every column of the page has something to collect
    assert {source.category for source in SOURCES} == set(CATEGORIES)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Plain   title \n", "Plain title"),
        ("Fish &amp; chips", "Fish & chips"),
        ("<b>Bold</b> move", "Bold move"),
        ("<script>alert(1)</script>Safe", "alert(1) Safe"),
        # An escaped tag is decoded first and then removed, so it cannot come back as markup
        ("&lt;img src=x onerror=alert(1)&gt;Hi", "Hi"),
        ("", ""),
    ],
)
def test_a_title_becomes_plain_text(raw: str, expected: str):
    assert clean_title(raw) == expected


def test_a_long_title_is_cut_at_a_word_with_an_ellipsis():
    cleaned = clean_title("слово " * 80)

    assert len(cleaned) <= TITLE_MAX_LENGTH
    assert cleaned.endswith("…")
    assert not cleaned[:-1].endswith(" ")


@pytest.mark.parametrize(
    "url",
    [
        "https://suspilne.media/1/x",
        "http://suspilne.media/1/x",
        "https://www.suspilne.media/1/x",
        "https://sport.suspilne.media/x",
    ],
)
def test_a_link_on_the_source_host_is_accepted(url: str):
    assert link_allowed(url, ("suspilne.media",))


@pytest.mark.parametrize(
    "url",
    [
        "",
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "ftp://suspilne.media/x",
        "https://evil.example/x",
        "https://suspilne.media.evil.example/x",
        "https://evil.example/suspilne.media",
        "https://notsuspilne.media/x",
        "https://user:pass@suspilne.media/x",
        "https://suspilne.media/x\nSet-Cookie: a=b",
        "https://suspilne.media/" + "a" * 1000,
    ],
)
def test_any_other_link_is_refused(url: str):
    assert not link_allowed(url, ("suspilne.media",))


@pytest.mark.parametrize(
    "title",
    [
        "Спортсменам і тренерам з паралімпійського і дефлімпійського спорту виплатять премії",
        "Ветеран зі Львівщини став переможцем міжнародного турніру з боккії",
        "Ігри нескорених 2027: Україна оголосила склад збірної",
        "Invictus Games team announced",
        "Адаптивний спорт: у Києві відкрили новий простір",
        "Параспорт розвивається у громадах",
    ],
)
def test_items_about_adaptive_or_veterans_sport_are_on_topic(title: str):
    assert is_on_topic(title)


@pytest.mark.parametrize(
    "title",
    [
        "Українська делегація прибула в Абу-Дабі на тристоронні переговори",
        "Мессі з новим рекордом потрапив до символічної збірної року",
        "Ветеран отримав нове посвідчення",
        "На Бакоті завершився туристичний сезон",
    ],
)
def test_other_news_is_not(title: str):
    assert not is_on_topic(title)


def test_the_summary_can_carry_the_topic():
    assert is_on_topic(
        "Новини дня", "У змаганнях взяли участь ветерани та людей з інвалідністю, спорт"
    )
    assert not is_on_topic("Новини дня", "Погода на завтра")


@pytest.mark.parametrize(
    "title",
    [
        "Людей з інвалідністю запрошують на змагання з плавання",
        "Протезування для бігу: ветеран готується до старту",
    ],
)
def test_sport_of_people_with_disabilities_is_on_topic(title: str):
    assert is_on_topic(title)


def test_the_wider_support_topic_takes_rehabilitation_and_prostheses_too():
    assert is_on_topic("У Львові відкрили центр реабілітації для військових", topic="support")
    assert is_on_topic("Нова програма для ветеранів", topic="support")
    assert not is_on_topic("Погода на завтра", topic="support")
    # The same title is not about sport
    assert not is_on_topic("У Львові відкрили центр реабілітації для військових")
