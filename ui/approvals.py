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


def render_pause(pause: Pause) -> dict | None:
    """Show the form for a pause. Returns the user's answer once they have
    submitted it, otherwise None."""
    if pause.kind == SAVE_KIND:
        return _save_form(pause.data)
    return _review_form(pause.data)


def _review_form(data: dict) -> dict | None:
    """Competitor review: tick boxes, add companies, continue or cancel."""
    with st.container(key="approval_review"):
        st.markdown(f"**Review the competitors** for {data['product']} in {data['country']}")
        st.caption("Untick any that do not belong, add any that are missing, "
                   "then continue. The detailed research starts after this.")

        # A form sends all its inputs together when a button is pressed, so
        # ticking a box does not rerun the page each time.
        with st.form("review_form", border=False):
            kept = {}
            for index, competitor in enumerate(data["competitors"]):
                website = competitor["website"] or "no website found yet"
                kept[competitor["name"]] = st.checkbox(
                    f"**{competitor['name']}** :gray[{website}]",
                    value=True, key=f"keep_{index}")

            extra = {}
            if data["left_out"]:
                st.caption("Also verified, but left out to keep the list short")
                for index, name in enumerate(data["left_out"]):
                    extra[name] = st.checkbox(name, value=False, key=f"extra_{index}")

            typed = st.text_input(
                "Add a company", key="review_add",
                placeholder="For example Marley Spoon, EatFitter")

            if data["dropped"]:
                with st.expander(f"{len(data['dropped'])} dropped, see why", type="compact"):
                    for dropped in data["dropped"]:
                        st.caption(f"**{dropped['name']}**: {dropped['reason']}")

            with st.container(horizontal=True):
                go = st.form_submit_button("Continue", type="primary",
                                           icon=":material/arrow_forward:")
                cancel = st.form_submit_button("Cancel report")

    if cancel:
        return review_answer("cancel")
    if go:
        return review_answer_from_form(kept, extra, typed)
    return None


def _save_form(data: dict) -> dict | None:
    """Save approval: an editable title, save or don't save."""
    with st.container(key="approval_save"):
        st.markdown("**Save this report to a file?**")
        with st.form("save_form", border=False):
            title = st.text_input("Title", value=data["title"], key="save_title")
            st.caption(f"It will be saved in the reports folder as "
                       f"`{safe_filename(title or data['title'])}`. Changing the "
                       f"title changes the file name.")
            with st.container(horizontal=True):
                save = st.form_submit_button("Save", type="primary",
                                             icon=":material/save:")
                skip = st.form_submit_button("Don't save")

    if save or skip:
        return save_answer_from_form(data["title"], title, save=save)
    return None
