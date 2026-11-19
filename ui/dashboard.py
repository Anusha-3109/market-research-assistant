"""The Dashboard page: what Markavi answered, how long it took, what it
cost and which tools it used, read from the usage log (agent/usage_log.py).

Each account sees its own use. On your own computer (no accounts) every
line counts.
"""

from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from agent.feedback import UP, ratings
from agent.usage import format_cost
from agent.usage_log import ANSWERED, ERROR, TURNED_AWAY, events, per_day, summary
from ui.assets import fill, join
from ui.texts import t

RANGES = [7, 30, 90, 365]
CORAL, PEACH, DEEP, GREY, RED = "#ec8f6a", "#f6c3ae", "#c0623e", "#9aa5a8", "#d9534f"


def tokens_text(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.0f}k"
    return str(count)


def figure_cards(cards: list[tuple]) -> None:
    """A row of figure cards: (label, value, small line under it). A value
    that is words rather than a number adds a fourth item, WORDS, so it is
    drawn smaller and fits its card."""
    st.html(fill("kpis.html", cards=join(fill("kpi.html", label=card[0], value=card[1], note=card[2],
                                              size=card[3] if len(card) > 3 else "")
                                         for card in cards)))


WORDS = "gw-kpi-words"


def _chart_card(title: str, key: str, chart, table: pd.DataFrame, note: str = "") -> None:
    with st.container(border=True, key=f"card_{key}"):
        head, switch = st.columns([3, 1], vertical_alignment="center")
        head.markdown(f"**{title}**")
        as_table = switch.toggle(t("dash.show_table"), key=f"table_{key}")
        if as_table:
            st.dataframe(table, hide_index=True, width="stretch")
        else:
            st.altair_chart(chart, width="stretch", theme=None)
        if note:
            st.caption(note)


def _bars(frame: pd.DataFrame, value: str, colour_by: str | None, colours: dict, axis: str):
    chart = alt.Chart(frame).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b")),
        y=alt.Y(f"{value}:Q", title=axis, stack=True))
    if colour_by:
        chart = chart.encode(color=alt.Color(
            f"{colour_by}:N", title=None, legend=alt.Legend(orient="top"),
            scale=alt.Scale(domain=list(colours), range=list(colours.values()))))
    else:
        chart = chart.encode(color=alt.value(next(iter(colours.values()))))
    return chart.properties(height=200)


def _helpful(store, user_id: str | None, since: datetime) -> tuple[str, str, str]:
    """The share of this account's rated answers that got a thumbs up."""
    given = ratings(store, user_id, since=since)
    if not given:
        return t("dash.helpful"), "—", t("admin.no_ratings")
    ups = sum(1 for line in given if line["rating"] == UP)
    return (t("dash.helpful"), f"{ups / len(given):.0%}",
            t("dash.helpful_note", up=ups, count=len(given)))


def render_dashboard(store, user_id: str | None) -> None:
    with st.container(key="dashboard_page"):
        head, picker = st.columns([3, 2], vertical_alignment="center")
        head.title(t("dash.title"), anchor=False)
        st.caption(t("dash.subtitle"))
        days = picker.segmented_control(
            t("dash.range"), RANGES, default=30, key="dashboard_range", label_visibility="collapsed",
            format_func=lambda n: t("dash.year") if n == 365 else t("dash.days", count=n)) or 30

        now = datetime.now(timezone.utc)
        lines = events(store, user_id, since=now - timedelta(days=days))
        figures = summary(lines)
        first = events(store, user_id)
        since = datetime.fromisoformat(first[0]["at"]).date() if first else now.date()

        with st.container(border=True, key="dashboard_research"):
            st.markdown(f"**{t('dash.research')}**")
            st.markdown(t("dash.research_line", conversations=figures["conversations"],
                          reports=figures["reports"], single=figures["single"],
                          sources=figures["sources"]))
            st.caption(t("dash.since", day=since.strftime("%d %b %Y")))

        share = figures["share_answered"]
        wait = figures["median_seconds"]
        figure_cards([
            (t("dash.requests"), str(figures["requests"]), t("dash.requests_note", count=days)),
            (t("dash.answered"), f"{share:.0%}" if share is not None else "—",
             t("dash.answered_note", answered=figures["answered"], requests=figures["requests"])),
            (t("dash.wait"), f"{wait:.1f} s" if wait is not None else "—", t("dash.wait_note")),
            (t("dash.tokens"), tokens_text(figures["tokens"]), t("dash.tokens_note")),
            (t("dash.cost"), format_cost(figures["cost"]), t("dash.cost_note")),
            _helpful(store, user_id, now - timedelta(days=days)),
        ])

        rows = per_day(lines, now.date(), days)
        kinds = {t("dash.kind.answered"): CORAL, t("dash.kind.turned_away"): GREY,
                 t("dash.kind.error"): RED}
        requests = pd.DataFrame([{"day": row["day"], "kind": label, "count": row[kind]}
                                 for row in rows for kind, label in
                                 ((ANSWERED, t("dash.kind.answered")),
                                  (TURNED_AWAY, t("dash.kind.turned_away")),
                                  (ERROR, t("dash.kind.error")))])
        waits = pd.DataFrame([{"day": row["day"], "kind": label, "seconds": sum(found) / len(found)}
                              for row in rows for key, label in
                              (("waits_single", t("dash.kind.single")),
                               ("waits_report", t("dash.kind.report")))
                              if (found := sorted(row[key]))])
        tokens = pd.DataFrame([{"day": row["day"], "kind": label, "tokens": row[key]}
                               for row in rows for key, label in
                               (("input_tokens", t("dash.kind.input")),
                                ("output_tokens", t("dash.kind.output")))])
        cost = pd.DataFrame([{"day": row["day"], "cost": round(row["cost"], 6)} for row in rows])

        left, right = st.columns(2, gap="medium")
        with left:
            _chart_card(t("dash.requests_per_day"), "requests",
                        _bars(requests, "count", "kind", kinds, ""), requests)
        with right:
            if waits.empty:
                line = alt.Chart(pd.DataFrame({"day": [], "seconds": []})).mark_line()
            else:
                line = alt.Chart(waits).mark_line(point=True).encode(
                    x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b")),
                    y=alt.Y("seconds:Q", title=t("dash.seconds")),
                    color=alt.Color("kind:N", title=None, legend=alt.Legend(orient="top"),
                                    scale=alt.Scale(range=[PEACH, DEEP]))).properties(height=200)
            _chart_card(t("dash.time_to_answer"), "waits", line, waits, t("dash.answered_only"))
        left, right = st.columns(2, gap="medium")
        with left:
            _chart_card(t("dash.tokens_per_day"), "tokens",
                        _bars(tokens, "tokens", "kind",
                              {t("dash.kind.input"): PEACH, t("dash.kind.output"): DEEP}, ""), tokens)
        with right:
            _chart_card(t("dash.cost_per_day"), "cost", _bars(cost, "cost", None, {"": CORAL}, "USD"),
                        cost, t("dash.cost_note"))

        tools, guard, errors = st.columns(3, gap="medium")
        with tools.container(border=True, key="dashboard_tools"):
            st.markdown(f"**{t('dash.tool_calls')}**")
            if figures["tools"]:
                frame = pd.DataFrame([{"tool": name, "calls": count}
                                      for name, count in figures["tools"].items()])
                st.altair_chart(alt.Chart(frame).mark_bar(color=CORAL).encode(
                    x=alt.X("calls:Q", title=None, axis=alt.Axis(tickMinStep=1)),
                    y=alt.Y("tool:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)))
                    .properties(height=max(120, 26 * len(frame))), width="stretch", theme=None)
            else:
                st.caption(t("dash.none_yet"))
        with guard.container(border=True, key="dashboard_guard"):
            st.markdown(f"**{t('dash.guard')}**")
            passed = figures["requests"] - figures["turned_away"]
            st.markdown(f"### {passed} / {figures['requests']}")
            st.caption(t("dash.guard_note", turned_away=figures["turned_away"]))
        with errors.container(border=True, key="dashboard_errors"):
            st.markdown(f"**{t('dash.errors')}**")
            if figures["error_lines"]:
                for line in figures["error_lines"][-5:]:
                    day = datetime.fromisoformat(line["at"]).strftime("%d %b")
                    st.caption(f"{day} · {line['error'] or t('dash.kind.error')}")
            else:
                st.caption(t("dash.no_errors"))
