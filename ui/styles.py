"""The app's look.

The styling itself is in ui/static/styles.css. This file only adds it to
the page.
"""

import streamlit as st

from ui.assets import style_tag


def apply_styles() -> None:
    """Add the app's CSS to the page."""
    st.html(style_tag("styles.css"))
