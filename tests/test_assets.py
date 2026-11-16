"""Tests for loading the interface's HTML, CSS and JavaScript files."""

from ui.assets import STATIC, Html, fill, join, load, script_tag, style_tag


def test_values_from_the_web_are_escaped_when_put_into_a_template():
    html = fill("guide_question.html", question='<script>x</script> & "more"')

    assert "<script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt; &amp; &quot;more&quot;" in html


def test_html_that_is_already_safe_is_not_escaped_twice():
    badge = fill("source_badge.html")

    row = fill("source_row.html", url="https://a.example", title="T", number=1,
               domain="a.example", letter="A", icon=Html(""), badge=badge)

    assert '<span class="gw-official">Official</span>' in row


def test_joined_pieces_stay_safe_html():
    assert isinstance(join([Html("<b>a</b>"), Html("<i>b</i>")]), Html)


def test_the_stylesheet_and_scripts_are_wrapped_in_their_tags():
    assert style_tag("styles.css").startswith("<style>")
    assert ".stApp" in style_tag("styles.css")
    assert script_tag("start_at_top.js").startswith("<script>")


def test_every_template_blank_is_filled_by_the_code_that_uses_it():
    # A blank left unfilled would raise an error; these calls cover every
    # template in the folder.
    from agent.citations import Source
    from ui.guide import steps_html
    from ui.research import sources_html

    assert "gw-step" in steps_html()
    assert "gw-sources-empty" in sources_html([], "None yet.")
    assert "gw-source-favicon" in sources_html(
        [Source(1, "Title", "a.example", "https://a.example/p", True)], "")
    assert "gw-skeleton" in load("skeleton.html")


def test_the_static_folder_holds_only_html_css_and_javascript():
    kinds = {path.suffix for path in STATIC.iterdir()}

    assert kinds == {".html", ".css", ".js"}
