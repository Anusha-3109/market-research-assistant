# <img src="ui/static/logo.svg" alt="" height="34"> Markavi

**Your AI market research assistant: verified competitors, first-hand prices, every fact linked to its source.**

[![Tests](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/tests.yml) [![Deploy](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/deploy.yml/badge.svg)](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/deploy.yml)

Markavi researches a market for a first-time founder: it finds the real competitors in a country, reads their prices from their own websites, collects market figures, news and demand trends, and writes a six-section report in which every fact links to its source. It pauses so you can review the competitor list, and asks before it saves a file. It is built with LangChain, LangGraph, OpenRouter (GPT-4.1 mini by default) and Streamlit, and combines a ReAct agent with a fixed report workflow, memory and human-in-the-loop approval.

The Sprint 3 task description is in [`135.md`](135.md).

![The start screen: example cards around the headline "Research any market."](docs/screenshots/start.png)

## Contents

- [Purpose](#purpose)
- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [How to use it](#how-to-use-it)
- [Example use cases](#example-use-cases)
- [How it works](#how-it-works)
- [Technical decisions](#technical-decisions)
- [Observability](#observability)
- [Error handling and safety](#error-handling-and-safety)
- [Tests](#tests)
- [Deployment](#deployment)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [What I would improve](#what-i-would-improve)

## Purpose

### Target user

First-time founders who want to test a business idea before launch and
cannot afford an analyst or paid research reports. Also useful for small
business owners who are considering a new product or a new region.

### Problem

Before launching, a founder needs to understand competitors, pricing,
customer needs and market trends. Today this means searching many
websites by hand, copying notes into a document, and trying to make sense
of them. It takes days, the result is unstructured, and it is often
unclear where each number came from.

### Solution

An AI agent that takes a product and a target country, searches live web
and news sources, verifies which companies really compete in that country,
reads their prices first-hand, and produces a structured report in which
every fact has a reference. The SWOT is analysis built on those facts and
is labelled as such. The user can then ask follow-up questions.

### Why an agent

- The research needs current data, which a language model alone does not
  have.
- The data comes from several sources: web search, news, company websites,
  company financials and search-interest data.
- Each step depends on the previous one: the competitors have to be found
  before anything can be looked up about each of them.

A single prompt cannot do this because it has no live data. Plain RAG
cannot do it because there is no fixed set of documents to search. An
agent with tools can decide what to look up next.

## What it does

| Capability | Detail |
|---|---|
| Web app | Example cards to start from, then three views of a conversation: Snapshot (a report's key figures at a glance), Ask (the chat) and Report (the report as cards) |
| Market research report | Six fixed sections: market overview, competitors, pricing, trends, SWOT analysis, references |
| Verified competitors | Each candidate is checked: does it sell this product, in this country? Others are dropped with the reason |
| First-hand prices | Read only from the competitor's own website; the source link is set by code |
| Follow-up questions | Answered with single tools: search, news, page reader, demand trend, company figures |
| Your review | The agent pauses so you can approve, remove or add competitors, or cancel |
| Save with approval | A report is written to a file only after you approve, and you can change the title |
| Memory | Remembers the conversation across restarts, and your country, industry and idea across conversations |
| Numbered sources | Every link in an answer becomes a number such as [1]; the source list shows each page's title and site, and marks a company's own site as Official |
| Download | Any answer as a Markdown file or a PDF |
| Report formats | A report as the full text, as an investor one-pager, or as pitch deck slides with a PowerPoint download |
| Language | An EN / DE switch at the top right, saved with the account. In German the views, the answers and the reports (also as one-pager, slides, Markdown and PDF) are in German |
| Assistant | A small chat at the bottom right of every view for a quick question in between, answered from the open report |
| Stop | A run can be stopped; what was found so far is kept and the conversation continues |
| Resilience | Every data source has a free backup, so one outage does not stop a report. If the model leaves out a required field, the question is asked again instead of losing the report |
| Accounts | On a deployed copy each person signs in to their own account, with their own conversations, remembered profile, settings and saved reports |
| Cost shown | Every answer and report shows what its model calls cost, as reported by the model service |
| Tracing | With a LangSmith key, every run is recorded step by step for debugging |
| Feedback loop | 👍 / 👎 under every answer; a 👎 asks what could be better (six reasons and a comment). A reason an account gives again and again becomes a tip in that account's system prompt, and every rating is added to the answer's LangSmith trace |
| Pages | Links at the top of the sidebar to Research, a **Dashboard** (requests, wait, tokens, cost, tool calls and the share rated helpful) and **Admin** |
| Admin page | Developer settings for the whole app: model, temperature, answer length and style, competitor review, the system prompt, and a switch for each tool. A Feedback tab shows how answers were rated and why, which settings did best, and the latest 👎, with a switch for learning from feedback. Its Documentation tab explains how it works (the flow as a Mermaid chart, the tools and data sources). Only admins see it |
| Light and dark | A Light / Dark choice on the Admin page, for the whole app |
| Deployed | Runs on Google Cloud Run behind a sign-in screen, and redeploys itself after the tests pass |

The assistant does **not** give investment or financial advice, invent or
estimate numbers, use paid databases, or answer questions unrelated to
market research.

## Quick start

Requirements: Python 3.10 or newer, and two API keys.

| Key | Used for | Where to get it |
|---|---|---|
| `OPENROUTER_API_KEY` | The language model | https://openrouter.ai/keys |
| `TAVILY_API_KEY` | Web search, news and page reading | https://tavily.com (free tier) |

```bash
git clone <this repository>
cd market-research-assistant

python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS and Linux

pip install -r requirements.txt

copy .env.example .env              # then open .env and paste your two keys
```

Start the app:

```bash
streamlit run app.py
```

It opens in your browser at `http://localhost:8501`. If a key is missing,
the page shows setup instructions.

A report costs about three cents of OpenRouter credit (measured: $0.03 for
23 model calls) and about 20 Tavily searches. A single question costs a
fraction of a cent. The app shows the exact figure next to every answer.

## How to use it

1. **Ask.** Click an example card on the start screen, or type a question
   that names a product and a country: *healthy meal delivery in Germany*.
2. **Review.** A report pauses once so you can approve or edit the list of
   competitors it found.
3. **Read.** A finished report has three views: **Snapshot** (the key
   figures in tabs), **Ask** (the chat) and **Report** (each section as a
   card, also as an investor one-pager or pitch deck slides).
4. **Take it with you.** Download as Markdown, PDF or PowerPoint, or save
   it to the reports folder after you approve.
5. **Ask in between.** The robot icon at the bottom right opens a small
   assistant for quick questions about the open report. The **EN | DE**
   switch at the top right changes the language.

The full guide, with every screen and setting, is in
[`docs/how-to-use.md`](docs/how-to-use.md).

## Example use cases

Markavi handles a full report, single questions, and the cases where it
should not answer:

- *"Give me a market research report for healthy meal delivery in
  Germany."* It runs the report workflow and pauses for your review.
- *"Is there a market for vegan protein snacks?"* No country was given, so
  it asks which one you mean.
- *"Should I invest my savings in this business?"* It declines to give
  investment advice and offers market facts instead.

All seven examples are in
[`docs/example-use-cases.md`](docs/example-use-cases.md).

## How it works

Markavi has three parts. A **chat agent** (a ReAct agent built with
LangChain) answers single questions with tools for prices, competitors,
news, demand and company figures. A **report workflow** (a fixed LangGraph
graph) writes the six-section report: code decides the order of the steps
and checks every result, and the model does one small job at a time. The
**web app** (Streamlit) shows the work as it happens and holds the two
points where a person approves: the competitor list and saving a file.
Conversations, the remembered profile and accounts are kept in a memory
file, and every source has a fallback.

Answers improve from people's ratings. A 👎 asks what could be better; a
reason that comes up in two or more of an account's last ten ratings adds a
fixed tip to that account's system prompt, such as "Keep answers short".
Only these fixed sentences reach the prompt, never a typed comment. The
Admin page shows what was rated down, to guide changes for everyone.

The parts in detail, with the data sources, middleware, approval steps and
the feedback loop, are in [`docs/how-it-works.md`](docs/how-it-works.md).

## Technical decisions

The main decision is a fixed workflow for reports and a free agent for
conversation. The first version let one agent do everything; it skipped
steps, listed US companies as German competitors and took prices from an
old article, and each prompt fix produced a new error. Moving the report
into a workflow where code controls the order and checks every result
fixed that, and the free agent is kept for what it is good at. The other
decisions follow the same idea: let code do what must be exact (numbers,
sources, the report text) and let the model do what needs judgment.

Every decision, with what was tried first and why it changed, is in
[`docs/technical-decisions.md`](docs/technical-decisions.md).

## Observability

Every run can be sent to [LangSmith](https://smith.langchain.com) as a
trace: each call to the model, each tool call and each step of the report
workflow, with how long it took, its tokens and cost, and any error. A
trace answers "why did the agent do that?" after the fact.

| | |
|---|---|
| Switching it on | Set `LANGSMITH_API_KEY` in `.env`. Without a key nothing is sent. `LANGSMITH_TRACING=false` switches it off with the key in place |
| EU accounts | Also set `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` |
| Projects | A copy on your own computer traces to `markavi-local`, the deployed copy to `markavi-live`, so experiments and visitors' runs are not mixed. `LANGSMITH_PROJECT` names another |
| Names | A chat turn is the run "Markavi chat"; a report's steps appear inside the turn that asked for it. The assistant's calls are "Markavi assistant" |
| Labels | The conversation id (LangSmith groups a conversation by it), the account's internal id, the model and the language |
| Ratings | A 👍 or 👎 is added to the answer's trace as feedback `user_rating` (1 or 0), with the reasons and the comment, so traces can be filtered by it. Rating again replaces it |
| In the app | The Help panel says whether runs are traced |
| Tests | Never trace: `tests/conftest.py` switches tracing off before anything is loaded |

A trace holds the questions people typed and the answers. It is labelled
with the account's internal id only, never a name or an email address. The
code is in `agent/tracing.py`.

## Error handling and safety

- **Failures are explained, not shown raw.** A missing key, a rate limit,
  a timeout or a failed source each get a plain message; a source that
  fails is replaced by the next one, and what cannot be found is reported
  as "not found".
- **Web content is treated as information, never as instructions.** Only
  `http` and `https` pages are opened, and private network addresses are
  blocked.
- **Nothing is written without approval,** and only into `reports/`.
- **A deployed copy** asks for a sign-in first, stores passwords only as
  salted hashes, and gives each account only its own conversations.
- **Boundaries.** Investment advice and off-topic requests are declined.

The full list is in
[`docs/error-handling-and-safety.md`](docs/error-handling-and-safety.md).

## Tests

```bash
pytest
```

1040 tests, none of which use the internet or cost anything: the
model and the outside services are replaced with fakes. They run on every
push, and the app is deployed only when they pass.

What each test file covers is in [`docs/tests.md`](docs/tests.md).

## Deployment

Markavi runs on **Google Cloud Run**: <https://markavi-1037824678664.europe-west1.run.app>. It asks you to sign in
first, and creating an account needs an invite code, so that a stranger
with the link cannot spend the API credit. A push to `main` runs the tests
and then deploys by itself; the keys live in Secret Manager, never in the
image.

How it is set up, its settings, and how to deploy it yourself are in
[`docs/deployment.md`](docs/deployment.md).

## Project structure

```
MARKET-RESEARCH-ASSISTANT
│
├── FRONTEND             ui/
│   ├── screens          start, pickers, guide, the three views, sign-in
│   ├── on every screen  sidebar, assistant, account badge, language switch
│   └── look and words   static/ (CSS, HTML, scripts) and words/ (English, German)
│
├── BACKEND              agent/
│   ├── chat agent       the agent, its prompt, tools and approval points
│   ├── report/          the report workflow (LangGraph)
│   ├── sources/         one file per outside service, with fallbacks
│   ├── memory           conversations, profile, accounts
│   ├── feedback         ratings, tips from ratings, ratings to LangSmith
│   └── outputs          citations, PDF, PowerPoint, report check
│
├── STREAMLIT            app.py, .streamlit/
│
└── tests/ · docs/ · Dockerfile · .github/workflows/
```

The words in capitals are groups; the real folders are `ui/` and `agent/`.

How the parts work together:

```mermaid
flowchart TD
    visitor([Visitor]) --> app["STREAMLIT<br/>app.py"]
    app --> ui["FRONTEND · ui/<br/>screens, sidebar, assistant"]
    ui --> chat["BACKEND · agent/agent.py<br/>chat agent"]
    ui --> helper["agent/side_assistant.py<br/>quick assistant"]
    chat --> tools["agent/tools.py<br/>single-question tools"]
    chat --> report["agent/report/<br/>report workflow"]
    tools --> sources["agent/sources/<br/>web, news, trends, company data"]
    report --> sources
    report --> layouts["snapshot, one-pager, slides"]
    chat --> memory[("agent/memory.py<br/>conversations, profile, accounts")]
    ui --> feedback["agent/feedback.py<br/>👍 👎 ratings"]
    feedback -- "tips in the prompt" --> chat
    chat -.-> tracing["agent/tracing.py<br/>LangSmith"]
    helper -.-> tracing
    feedback -.-> tracing
```

Every file, with what it is for, is in
[`docs/project-structure.md`](docs/project-structure.md).

## Known limitations

1. **Prices come only from a company's own website.** A price is never
   taken from an article or a comparison site. Brands sold in supermarkets
   rarely show prices on their own site, and some sites load prices with
   JavaScript, so those prices show as "not found", with the reason.
2. **Reports differ between runs.** The competitors chosen and the wording
   vary, market sizes come from public summaries of paid reports, and small
   private companies publish no figures.
3. **Single questions are not checked like reports.** An answer outside the
   report workflow does not get its competitor verification; in testing,
   one named a US company as a competitor in Germany.
4. **Some rules are instructions to the model, not checks in code:** the
   answer style, writing in German, the tips learned from ratings, and not
   quoting figures from memory. Whether they make answers better is not
   measured yet.
5. **It depends on outside services.** All models are reached through
   OpenRouter, and searches use Tavily, which runs on credits. When either
   is unavailable, free backups take over with thinner results.

## What I would improve

1. Measure report quality with an evaluation set (Ragas or DeepEval), so
   changes, and the effect of the ratings, are judged by numbers.
2. Read prices from pages that need JavaScript with a headless browser,
   including supermarket pages for brands that do not sell on their own
   site.
3. Give single questions the same competitor verification as the report
   workflow.
4. Add a second model provider, so the app does not depend on OpenRouter
   alone.
5. Keep people signed in across a refresh, let them delete their account,
   verify email addresses, and set a usage limit per account.
6. Summarise long conversations, so a long one does not cost more per turn.
