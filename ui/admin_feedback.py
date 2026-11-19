"""The Feedback tab of the Admin page: how the answers were rated.

Everything here covers the last seven days and every account. The switch
"Learn from feedback" turns the tips from ratings in the prompt on or off
for the whole app (agent/feedback.py, agent/app_settings.py).

Questions and comments were typed by users: they are shown through fill(),
which shows them as text.
"""

from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from agent import memory
from agent.app_settings import load_app_settings, save_app_settings
from agent.config import MODEL_CHOICES, STYLE_CHOICES
from agent.feedback import feedback_summary, ratings
from agent.memory import DEFAULT_USER
from agent.usage_log import ANSWERED, events
from ui.assets import Html, fill, join
from ui.dashboard import CORAL, PEACH, WORDS, figure_cards
from ui.texts import counted, current_language, t

DAYS = 7


def week_figures(store) -> dict:
    """The feedback figures of the last seven days, for every account."""
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    answered = sum(1 for line in events(store, None, since=since) if line["kind"] == ANSWERED)
    return feedback_summary(ratings(store, None, since=since), answered=answered)


def helpful_card(figures: dict) -> tuple[str, str, str]:
    """The "Helpful" card, shown on both tabs."""
    if not figures["ratings"]:
        return t("admin.helpful"), "—", t("admin.no_ratings")
    return (t("admin.helpful"), f"{round(figures['helpful'] * 100)}%",
            t("admin.helpful_note", up=figures["up"], count=figures["ratings"]))


def _reason(name: str) -> str:
    return t(f"feedback.reason.{name}")


def _save_learn(store) -> None:
    save_app_settings(store, {"learn": bool(st.session_state.get("admin_learn"))})
    memory.backup_memory()


def _day(at: str) -> str:
    when = datetime.fromisoformat(at)
    return f"{when.day}.{when.month}." if current_language() == "de" else f"{when.day} {when:%b}"


def _reasons_chart(reasons: dict) -> None:
    top = max(reasons.values())
    frame = pd.DataFrame([{"reason": _reason(name), "count": count,
                           "colour": CORAL if count == top else PEACH}
                          for name, count in reasons.items()])
    base = alt.Chart(frame).encode(y=alt.Y("reason:N", sort=list(frame["reason"]), title=None,
                                           axis=alt.Axis(labelLimit=180)))
    bars = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=16).encode(
        # Room on the right for the number after the longest bar.
        x=alt.X("count:Q", title=None, axis=None, scale=alt.Scale(domain=[0, top * 1.15])),
        color=alt.Color("colour:N", scale=None))
    labels = base.mark_text(align="left", dx=6, fontSize=11, color="#56656a").encode(
        x="count:Q", text="count:Q")
    st.altair_chart((bars + labels).properties(height=34 * len(frame) + 10),
                    width="stretch", theme=None)


def _by_setting(rows: list[dict]) -> None:
    table = pd.DataFrame([{
        t("admin.col_model"): MODEL_CHOICES.get(row["model"], row["model"]),
        t("admin.col_style"): t(f"style.{row['style']}") if row["style"] in STYLE_CHOICES
        else row["style"],
        t("admin.col_ratings"): row["ratings"],
        t("admin.col_helpful"): f"{round(row['helpful'] * 100)}%",
    } for row in rows])
    st.dataframe(table, hide_index=True, width="stretch")


def _latest(lines: list[dict]) -> Html:
    return join(fill(
        "feedback_down.html", question=line["question"],
        who=t("admin.local_user") if line["user"] == DEFAULT_USER else line["user"].removeprefix("u-"),
        when=_day(line["at"]),
        pills=join(fill("feedback_pill.html", text=_reason(name)) for name in line.get("reasons", [])),
        comment=fill("feedback_comment.html", text=line["comment"]) if line.get("comment") else Html(""),
    ) for line in lines)


def render_feedback_tab(store) -> None:
    figures = week_figures(store)
    top = figures["top_reason"]
    figure_cards([
        helpful_card(figures),
        (t("admin.down"), str(figures["down"]), t("admin.down_note", count=figures["with_comment"])),
        (t("admin.top_reason"), _reason(top) if top else "—",
         counted("admin.top_reason_note", figures["reasons"][top]) if top else t("admin.none_yet"),
         WORDS if top else ""),
        (t("admin.rated"),
         f"{round(figures['rated_share'] * 100)}%" if figures["rated_share"] is not None else "—",
         t("admin.rated_note", count=figures["ratings"], answered=figures["answered"])),
    ])
    st.caption(t("admin.feedback_note"))

    with st.container(border=True, key="admin_learn_card"):
        st.session_state.setdefault("admin_learn", load_app_settings(store)["learn"])
        st.toggle(t("admin.learn"), key="admin_learn", help=t("admin.learn_help"),
                  on_change=_save_learn, args=(store,))
        st.caption(t("admin.learn_note"))

    left, right = st.columns(2, gap="medium")
    with left.container(border=True, key="admin_reasons"):
        st.markdown(f"**{t('admin.reasons')}**")
        if figures["reasons"]:
            _reasons_chart(figures["reasons"])
        else:
            st.caption(t("admin.no_reasons") if figures["down"] else t("admin.no_downs"))
    with right.container(border=True, key="admin_by_setting"):
        st.markdown(f"**{t('admin.by_setting')}**")
        if figures["by_setting"]:
            _by_setting(figures["by_setting"])
        else:
            st.caption(t("admin.no_ratings"))

    with st.container(border=True, key="admin_latest_down"):
        st.markdown(f"**{t('admin.latest_down')}**")
        if figures["latest_down"]:
            st.html(_latest(figures["latest_down"]))
        else:
            st.caption(t("admin.no_downs"))
