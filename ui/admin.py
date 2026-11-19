"""The Admin page: developer settings for the whole app, and what it cost.

Only an admin opens it (ui/pages.py). What is chosen here is saved for
every account at once (agent/app_settings.py).
"""

from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from agent import memory
from agent.app_settings import SHARED, load_app_settings, save_app_settings, tool_names
from agent.config import LENGTH_CHOICES, MODEL_CHOICES, STYLE_CHOICES, THEME_CHOICES
from agent.prompts import SYSTEM_PROMPT
from agent.usage import format_cost
from agent.usage_log import ANSWERED, events
from ui.admin_feedback import helpful_card, render_feedback_tab, week_figures
from ui.dashboard import CORAL, PEACH, figure_cards
from ui.how_it_works import render_how_it_works
from ui.texts import current_language, t


def _save_settings(store) -> None:
    """Runs when a setting is changed, before the page is drawn again."""
    values = {name: st.session_state[f"set_{name}"] for name in SHARED}
    if values.get("theme") is None:
        # The chosen Light or Dark was clicked again, which unmarks it: keep it.
        values["theme"] = load_app_settings(store)["theme"]
        st.session_state["set_theme"] = values["theme"]
    save_app_settings(store, values)
    memory.backup_memory()


def _save_prompt(store) -> None:
    text = st.session_state.get("admin_prompt", "")
    save_app_settings(store, {"prompt": "" if text.strip() == SYSTEM_PROMPT.strip() else text})
    memory.backup_memory()
    st.session_state["admin_notice"] = t("admin.prompt_saved")


def _restore_prompt(store) -> None:
    save_app_settings(store, {"prompt": ""})
    memory.backup_memory()
    st.session_state["admin_prompt"] = SYSTEM_PROMPT
    st.session_state["admin_notice"] = t("admin.prompt_restored")


def _save_tools(store) -> None:
    disabled = [name for name in tool_names() if not st.session_state.get(f"tool_{name}", True)]
    save_app_settings(store, {"disabled_tools": disabled})
    memory.backup_memory()


def render_settings(store) -> None:
    """The model settings. A choice is shown by its name in the chosen
    language; what is saved is the choice itself."""
    language = current_language()
    save = {"on_change": _save_settings, "args": (store,)}
    st.selectbox(t("settings.model"), list(MODEL_CHOICES), key="set_model",
                 format_func=lambda name: MODEL_CHOICES[name], help=t("settings.model_help"), **save)
    st.slider(t("settings.temperature"), 0.0, 1.0, step=0.1, key="set_temperature",
              help=t("settings.temperature_help"), **save)
    st.select_slider(t("settings.length"), list(LENGTH_CHOICES), key="set_length",
                     format_func=lambda name: t(f"length.{name}", language=language),
                     help=t("settings.length_help"), **save)
    styles = list(STYLE_CHOICES)
    all_styles = "\n\n".join(f"**{t(f'style.{name}')}**: {t(f'style.about.{name}')}" for name in styles)
    chosen = st.selectbox(t("settings.style"), styles, key="set_style",
                          format_func=lambda name: t(f"style.{name}", language=language),
                          help=f"{t('settings.style_help')}\n\n{all_styles}", **save)
    st.caption(t(f"style.about.{chosen}"))
    st.toggle(t("settings.review"), key="set_review", help=t("settings.review_help"), **save)
    st.segmented_control(t("theme.label"), list(THEME_CHOICES), key="set_theme",
                         format_func=lambda name: t(f"theme.{name}"), help=t("theme.help"), **save)


def _cost_chart(lines: list[dict], today) -> None:
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    totals = {day: 0.0 for day in days}
    for line in lines:
        day = datetime.fromisoformat(line["at"]).date()
        if day in totals:
            totals[day] += line["cost"]
    frame = pd.DataFrame([{"day": day.strftime("%a"), "order": index, "cost": round(totals[day], 4),
                           "label": format_cost(totals[day]) if totals[day] else "$0"}
                          for index, day in enumerate(days)])
    top = max(frame["cost"]) or 1
    frame["colour"] = [CORAL if value == top and value > 0 else PEACH for value in frame["cost"]]
    base = alt.Chart(frame).encode(x=alt.X("day:N", sort=list(frame["day"]), title=None,
                                           axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=38).encode(
        y=alt.Y("cost:Q", title=None, axis=None), color=alt.Color("colour:N", scale=None))
    labels = base.mark_text(dy=-8, fontSize=11, color="#56656a").encode(y="cost:Q", text="label:N")
    st.altair_chart((bars + labels).properties(height=210), width="stretch", theme=None)


def render_admin(store) -> None:
    with st.container(key="admin_page"):
        head, badge = st.columns([4, 1], vertical_alignment="center")
        head.title(t("admin.title"), anchor=False)
        badge.html(f'<div class="gw-admin-pill">{t("admin.only")}</div>')
        st.caption(t("admin.subtitle"))
        settings_tab, feedback_tab, docs_tab = st.tabs(
            [t("admin.tab_settings"), t("admin.tab_feedback"), t("admin.tab_docs")])

        with settings_tab:
            now = datetime.now(timezone.utc)
            week = events(store, None, since=now - timedelta(days=7))
            today = [line for line in week if datetime.fromisoformat(line["at"]).date() == now.date()]
            answered_today = [line for line in today if line["kind"] == ANSWERED]
            tokens = [line["input_tokens"] + line["output_tokens"] for line in answered_today]
            accounts = len(list(store.search(("accounts",), limit=100_000))) if store is not None else 0
            active = len({line["user"] for line in week})
            figure_cards([
                (t("admin.cost_today"), format_cost(sum(line["cost"] for line in today)),
                 t("admin.cost_week", cost=format_cost(sum(line["cost"] for line in week)))),
                (t("admin.answers_today"), str(len(answered_today)),
                 t("admin.avg_tokens", count=f"{sum(tokens) // len(tokens):,}") if tokens
                 else t("admin.no_answers")),
                helpful_card(week_figures(store)),
                (t("admin.active"), str(active),
                 t("admin.active_note", count=accounts) if accounts else t("admin.active_local")),
            ])
            with st.container(border=True, key="admin_cost"):
                left, right = st.columns([2, 1])
                left.markdown(f"**{t('dash.cost_per_day')}**")
                right.caption(t("admin.cost_total", cost=format_cost(sum(line["cost"] for line in week))))
                _cost_chart(week, now.date())

            notice = st.session_state.pop("admin_notice", None)
            if notice:
                st.success(notice)
            models, prompt = st.columns(2, gap="medium")
            with models.container(border=True, key="admin_models"):
                st.markdown(f"**{t('admin.models')}**")
                render_settings(store)
                st.caption(t("admin.fallbacks"))
            with prompt.container(border=True, key="admin_prompt_card"):
                st.markdown(f"**{t('admin.prompt')}**")
                saved = load_app_settings(store)["prompt"]
                st.session_state.setdefault("admin_prompt", saved or SYSTEM_PROMPT)
                st.text_area(t("admin.prompt"), key="admin_prompt", height=300,
                             label_visibility="collapsed")
                st.caption(t("admin.prompt_note"))
                with st.container(horizontal=True):
                    st.button(t("admin.save_prompt"), key="admin_prompt_save", type="primary",
                              icon=":material/check:", on_click=_save_prompt, args=(store,))
                    st.button(t("admin.restore_prompt"), key="admin_prompt_restore", type="tertiary",
                              on_click=_restore_prompt, args=(store,))
                st.caption(t("admin.prompt_in_use_custom") if saved else t("admin.prompt_in_use_builtin"))

            with st.container(border=True, key="admin_tools"):
                st.markdown(f"**{t('admin.tools')}**")
                disabled = set(load_app_settings(store)["disabled_tools"])
                for name in tool_names():
                    st.session_state.setdefault(f"tool_{name}", name not in disabled)
                    left, right = st.columns([5, 1], vertical_alignment="center")
                    left.markdown(f"`{name}`  \n:gray[{t(f'admin.tool.{name}')}]")
                    right.toggle(name, key=f"tool_{name}", label_visibility="collapsed",
                                 on_change=_save_tools, args=(store,))

        with feedback_tab:
            render_feedback_tab(store)

        with docs_tab:
            render_how_it_works()
