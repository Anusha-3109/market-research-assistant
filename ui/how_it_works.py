"""The "How it works" page: what happens to a question, the tools, the
report workflow and where the data comes from.

The flow is a Mermaid chart, drawn in the browser by the Mermaid library
(the same one GitHub uses). Without it, the numbered steps under the chart
say the same.
"""

import streamlit as st

from ui.texts import t

MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"

# The chart, with its words filled in from ui/words.
CHART = """flowchart LR
    Q([{question}]) --> G[{guard}]
    G -->|{turned_back}| X([{explained}])
    G --> A[{agent}]
    A -->|{single}| T[{tools}]
    A -->|{full}| W[{workflow}]
    W --> R{{{{{review}}}}}
    R --> W
    T --> A
    W --> C[{check}]
    A --> C
    C --> O([{answer}])"""

CHART_PARTS = ["question", "guard", "turned_back", "explained", "agent", "single", "tools", "full",
               "workflow", "review", "check", "answer"]

# (tool, the row's words in ui/words)
TOOLS = ["create_market_report", "web_search", "search_news", "read_webpage", "get_demand_trend",
         "get_company_financials", "save_report", "remember_preference"]
DATA = ["competitors", "prices", "figures", "demand", "news", "company", "rates"]


def _chart_html() -> str:
    words = {part: t(f"how.chart.{part}").replace('"', "'") for part in CHART_PARTS}
    source = CHART.format(**words)
    # The library is loaded first. A chart is drawn only once it can be seen:
    # in a tab that is not open, Mermaid would draw it at zero size and leave
    # a blank box. So the script looks every half second for a chart that is
    # on screen and not drawn yet, for example when the Documentation tab of
    # the Admin page is opened.
    script = ("(function () {"
              " function ready() {"
              "  mermaid.initialize({startOnLoad: false, theme: 'base', themeVariables: {"
              "   primaryColor: '#fff8f4', primaryBorderColor: '#ec8f6a', primaryTextColor: '#1f2a2e',"
              "   lineColor: '#8a979b', fontSize: '15px'}, flowchart: {curve: 'basis'}});"
              "  if (window.gwFlowTimer) { return; }"
              "  window.gwFlowTimer = setInterval(function () {"
              "   var shown = Array.prototype.filter.call("
              "    document.querySelectorAll('.gw-flow:not([data-processed])'),"
              "    function (chart) { return chart.offsetParent !== null; });"
              "   if (shown.length) { mermaid.run({nodes: shown}); }"
              "  }, 500);"
              " }"
              " if (window.mermaid) { ready(); return; }"
              " var tag = document.createElement('script');"
              f" tag.src = '{MERMAID}'; tag.onload = ready; document.head.appendChild(tag);"
              "})();")
    return f'<pre class="mermaid gw-flow">{source}</pre><script>{script}</script>'


def _table(head: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def render_how_it_works() -> None:
    st.title(t("how.title"), anchor=False)
    st.caption(t("how.subtitle"))

    with st.container(key="how_flow", border=True):
        st.markdown(f"**{t('how.flow_title')}**")
        st.html(_chart_html(), unsafe_allow_javascript=True)
        st.markdown(t("how.steps"))

    st.subheader(t("how.tools_title"), anchor=False)
    st.markdown(_table([t("how.col.tool"), t("how.col.source"), t("how.col.fallback")],
                       [[f"`{tool}`", t(f"how.tool.{tool}.source"), t(f"how.tool.{tool}.fallback")]
                        for tool in TOOLS]))

    st.subheader(t("how.workflow_title"), anchor=False)
    steps, why = st.columns(2, gap="medium")
    with steps.container(border=True):
        st.markdown(f"**{t('how.workflow_steps_title')}**\n\n{t('how.workflow_steps')}")
    with why.container(border=True):
        st.markdown(f"**{t('how.workflow_why_title')}**\n\n{t('how.workflow_why')}")

    st.subheader(t("how.data_title"), anchor=False)
    st.markdown(_table([t("how.col.data"), t("how.col.source"), t("how.col.backup")],
                       [[t(f"how.data.{row}.name"), t(f"how.data.{row}.source"),
                         t(f"how.data.{row}.backup")] for row in DATA]))

    honest, safety = st.columns(2, gap="medium")
    with honest.container(border=True):
        st.markdown(f"**{t('how.honest_title')}**\n\n{t('how.honest')}")
    with safety.container(border=True):
        st.markdown(f"**{t('how.safety_title')}**\n\n{t('how.safety')}")

    st.subheader(t("how.know_title"), anchor=False)
    st.markdown(t("how.know"))
