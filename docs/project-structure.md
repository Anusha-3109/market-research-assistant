# Project structure

[← Back to the README](../README.md)

Every file, with what it is for. The project has three parts: the
**frontend** (what you see), the **backend** (the agent and everything it
uses) and the **Streamlit** files that start the app and connect the two.

```
MARKET-RESEARCH-ASSISTANT
│
├── FRONTEND                     ui/
│   ├── Screens
│   │   ├── start.py             start screen and example cards
│   │   ├── picker.py            the picker behind each card
│   │   ├── guide.py             the "How it works" guide
│   │   ├── research.py          the three views: Snapshot, Ask, Report
│   │   └── sign_in.py           sign in, create an account, passwords
│   ├── Pages
│   │   ├── pages.py, page_sidebar.py   the page links in the sidebar
│   │   ├── dashboard.py         the Dashboard page
│   │   ├── how_it_works.py      the How it works page and its Mermaid chart
│   │   └── admin.py             the Admin page
│   ├── On every screen
│   │   ├── sidebar.py           conversations, memory, settings, help
│   │   ├── assistant.py         the floating assistant (robot icon)
│   │   ├── account_badge.py     who is signed in, sign out
│   │   ├── language.py          the EN | DE and Light | Dark switches
│   │   └── approvals.py         the two approval forms
│   └── Look and words
│       ├── static/              styles.css, HTML templates, scripts, logo, avatar
│       ├── words/               the app's words: en.py and de.py
│       ├── texts.py             gives a text in the chosen language
│       └── styles.py, assets.py load the stylesheet and the templates
│
├── BACKEND                      agent/
│   ├── The chat agent
│   │   ├── agent.py             builds the agent and its middleware
│   │   ├── prompts.py           the system prompt
│   │   ├── tools.py             the single-question tools
│   │   ├── memory_tools.py      remember and forget
│   │   ├── side_assistant.py    the floating assistant's one model call
│   │   └── approval.py          the two approval points
│   ├── The report workflow      report/
│   │   ├── graph.py, state.py   the steps and the data they share
│   │   ├── steps.py, review.py  find, verify and review competitors
│   │   ├── research.py          figures, prices, market, news, trend
│   │   ├── writing.py, render.py  SWOT, final check, the report text
│   │   ├── snapshot.py          the key figures, kept separately
│   │   ├── formats.py           one-pager and slides
│   │   ├── localize.py          a report's wording in German
│   │   └── tool.py, deps.py     how the chat agent starts a report
│   ├── Data sources             sources/
│   │   ├── tavily.py, metasearch.py   web search
│   │   ├── google_news.py, google_trends.py   news and demand
│   │   ├── wikipedia.py, wikidata.py, yahoo.py   company and market data
│   │   ├── webpage.py, http.py  reads a page safely
│   │   └── ../fallback.py       tries the next source when one fails
│   ├── Memory and accounts
│   │   ├── memory.py            conversations, profile, saved settings
│   │   ├── app_settings.py      the Admin page's settings, for every account
│   │   ├── usage_log.py         one line per question, for the Dashboard
│   │   ├── accounts.py, mailer.py   accounts and the password email
│   │   └── session.py           questions and answers, for any interface
│   ├── What comes out
│   │   ├── citations.py         numbered sources
│   │   ├── pdf_export.py, pptx_export.py   PDF and PowerPoint
│   │   └── report_check.py      checks a finished report
│   └── Rules and helpers
│       ├── guards.py, source_check.py, answer_length.py   safety and limits
│       ├── styles.py, language.py   how and in which language to write
│       ├── usage.py, tracing.py     cost, and LangSmith tracing
│       ├── currency.py, trends.py, countries.py, names.py, formatting.py
│       └── config.py, models.py     settings and the chat model
│
├── STREAMLIT
│   ├── app.py                   the page: puts frontend and backend together
│   ├── ui/runtime.py            creates the agent once and keeps it
│   └── .streamlit/config.toml   the app's theme
│
└── AROUND THE APP
    ├── tests/                   the tests
    ├── docs/                    the longer pages this README links to
    ├── main.py                  terminal chat, for development
    ├── Dockerfile, .github/workflows/   the image, tests and deploy
    └── requirements.txt, .env.example   what to install and which keys
```

The words in capitals, and the headings under them such as "Screens", are
groups, not folders: the real folders are `ui/` and `agent/`, with
`agent/report/` and `agent/sources/` inside the backend.
