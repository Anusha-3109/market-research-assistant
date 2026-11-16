"""The HTML, CSS and JavaScript files of the interface.

They live in ui/static/ as ordinary files, so they can be read and edited
with the usual tools for those languages. Python only loads them and fills
in the blanks.

A template is an HTML file with blanks written as $name. fill() escapes
every value it puts into a blank, because titles and addresses come from
the web and must be shown as text. A value that already is HTML (another
filled template) is wrapped in Html and is put in as it is.
"""

from functools import lru_cache
from html import escape
from pathlib import Path
from string import Template

STATIC = Path(__file__).parent / "static"


class Html(str):
    """Text that is already safe HTML and must not be escaped again."""


@lru_cache(maxsize=None)
def load(name: str) -> str:
    """The text of a file in ui/static/. Read once, then kept."""
    return (STATIC / name).read_text(encoding="utf-8")


def fill(name: str, **values) -> Html:
    """Fill the blanks of an HTML template and return the result."""
    safe = {key: value if isinstance(value, Html) else escape(str(value), quote=True)
            for key, value in values.items()}
    return Html(Template(load(name)).substitute(safe))


def join(parts) -> Html:
    """Several pieces of safe HTML as one."""
    return Html("".join(parts))


def style_tag(name: str) -> str:
    return f"<style>{load(name)}</style>"


def script_tag(name: str) -> str:
    return f"<script>{load(name)}</script>"
