"""The two approval forms.

When the agent stops for the user (a Pause), one of these forms is shown in
the chat. Submitting it returns the answer that resumes the agent; the
forms themselves do not talk to the agent.
"""

import streamlit as st

from agent.approval import (
    SAVE_KIND,
    Pause,
    review_answer,
    review_answer_from_form,
    save_answer_from_form,
)
from agent.tools import safe_filename
from ui.texts import t


def render_pause(pause: Pause) -> dict | None:
    """Show the form for a pause. Returns the user's answer once they have
    submitted it, otherwise None."""
    if pause.kind == SAVE_KIND:
        return _save_form(pause.data)
    return _review_form(pause.data)


def _review_form(data: dict) -> dict | None:
    """Competitor review: tick boxes, add companies, continue or cancel."""
    with st.container(key="approval_review"):
        st.markdown(t("review.title", product=data["product"], country=data["country"]))
        st.caption(t("review.help"))

        # A form sends all its inputs together when a button is pressed, so
        # ticking a box does not rerun the page each time.
        with st.form("review_form", border=False):
            kept = {}
            for index, competitor in enumerate(data["competitors"]):
                website = competitor["website"] or t("review.no_website")
                kept[competitor["name"]] = st.checkbox(
                    f"**{competitor['name']}** :gray[{website}]",
                    value=True, key=f"keep_{index}")

            extra = {}
            if data["left_out"]:
                st.caption(t("review.left_out"))
                for index, name in enumerate(data["left_out"]):
                    extra[name] = st.checkbox(name, value=False, key=f"extra_{index}")

            typed = st.text_input(
                t("review.add"), key="review_add", placeholder=t("review.add_example"))

            if data["dropped"]:
                with st.expander(t("review.dropped", count=len(data["dropped"])), type="compact"):
                    for dropped in data["dropped"]:
                        st.caption(f"**{dropped['name']}**: {dropped['reason']}")

            with st.container(horizontal=True):
                go = st.form_submit_button(t("review.continue"), type="primary",
                                           icon=":material/arrow_forward:")
                cancel = st.form_submit_button(t("review.cancel"))

    if cancel:
        return review_answer("cancel")
    if go:
        return review_answer_from_form(kept, extra, typed)
    return None


def _save_form(data: dict) -> dict | None:
    """Save approval: an editable title, save or don't save."""
    with st.container(key="approval_save"):
        st.markdown(t("save.title"))
        with st.form("save_form", border=False):
            title = st.text_input(t("save.field"), value=data["title"], key="save_title")
            st.caption(t("save.where", file=safe_filename(title or data["title"])))
            with st.container(horizontal=True):
                save = st.form_submit_button(t("save.save"), type="primary",
                                             icon=":material/save:")
                skip = st.form_submit_button(t("save.skip"))

    if save or skip:
        return save_answer_from_form(data["title"], title, save=save)
    return None
