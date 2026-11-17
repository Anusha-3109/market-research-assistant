"""The app's look.

The styling itself is in ui/static/styles.css. This file only adds it to
the page.
"""

import streamlit as st

from ui.assets import logo_data_uri, style_tag


def apply_styles() -> None:
    """Add the app's CSS to the page."""
    # The stylesheet draws the logo from the --logo variable set here.
    logo = f'<style>:root {{ --logo: url("{logo_data_uri()}"); }}</style>'
    st.html(logo + style_tag("styles.css"))
