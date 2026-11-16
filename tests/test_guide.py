"""Tests for the "How it works" guide content (no browser needed)."""

from ui import guide


def test_the_step_row_has_five_numbered_cards_in_order():
    html = guide.steps_html()

    assert html.count('class="gw-step"') == 5
    positions = [html.index(f'<div class="gw-num">{number}</div>') for number in range(1, 6)]
    assert positions == sorted(positions)
    for title in ("Ask", "Find competitors", "You review", "Collect facts", "Report"):
        assert f'<div class="gw-step-title">{title}</div>' in html


def test_the_report_step_shows_one_dot_per_report_section():
    assert guide.steps_html().count('class="gw-dot"') == 6


def test_text_in_the_step_cards_is_escaped():
    original = guide.STEPS[0]
    guide.STEPS[0] = ("<b>Ask</b>", "a & b", ["<tag>"], 0)
    try:
        html = guide.steps_html()
    finally:
        guide.STEPS[0] = original

    assert "&lt;b&gt;Ask&lt;/b&gt;" in html
    assert "a &amp; b" in html
    assert "&lt;tag&gt;" in html


def test_every_topic_has_a_question_an_answer_and_a_note():
    for name, topic in guide.TOPICS.items():
        assert topic["question"].endswith("?"), name
        assert len(topic["answer"].strip()) > 100, name
        assert topic["note"].strip(), name


def test_only_the_main_topic_shows_the_step_cards():
    assert guide.TOPICS["how"]["steps"] is True
    assert all(not guide.TOPICS[name]["steps"] for name in guide.FOLLOW_UPS)


def test_every_follow_up_chip_points_at_a_real_topic():
    assert guide.FOLLOW_UPS
    assert all(name in guide.TOPICS for name in guide.FOLLOW_UPS)


def test_the_main_answer_explains_all_five_steps_and_the_limits():
    answer = guide.TOPICS["how"]["answer"]

    for step in ("You ask.", "It finds the real competitors.", "You review the list.",
                 "It collects the facts.", "You get a report."):
        assert f"**{step}**" in answer
    assert "investment advice" in answer
    assert '"not found"' in answer
