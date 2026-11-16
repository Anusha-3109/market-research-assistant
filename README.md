# AI Market Research Assistant

An AI agent that researches a market for a first-time founder: it finds the
real competitors in a country, reads their prices from their own websites,
collects market figures, news and demand trends, and writes a six-section
report in which every fact links to its source.

> **Status.** The agent, the report workflow, memory and the approval steps
> are complete and tested (300 automated tests). It currently runs as a
> terminal chat. The Streamlit web app is the next piece of work and is not
> in this repository yet.

## Contents

- [Purpose](#purpose)
- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [How to use it](#how-to-use-it)
- [Example use cases](#example-use-cases)
- [How it works](#how-it-works)
- [Technical decisions](#technical-decisions)
- [Error handling and safety](#error-handling-and-safety)
- [Tests](#tests)
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
| Market research report | Six fixed sections: market overview, competitors, pricing, trends, SWOT analysis, references |
| Verified competitors | Each candidate is checked: does it sell this product, in this country? Others are dropped with the reason |
| First-hand prices | Read only from the competitor's own website; the source link is set by code |
| Follow-up questions | Answered with single tools: search, news, page reader, demand trend, company figures |
| Your review | The agent pauses so you can approve, remove or add competitors, or cancel |
| Save with approval | A report is written to a file only after you approve, and you can change the title |
| Memory | Remembers the conversation across restarts, and your country, industry and idea across conversations |
| Resilience | Every data source has a free backup, so one outage does not stop a report |

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

Start the chat:

```bash
python main.py
```

A report costs a few cents of OpenRouter credit and about 20 Tavily
searches.

## How to use it

### Start or continue a conversation

```bash
python main.py                      # new conversation
python main.py --thread a1b2c3d4    # continue an earlier one
```

Each conversation has an id, printed when it starts. Conversations are
saved in `data/memory.db`, so you can close the program and come back.

### Ask for a report

```
You: I want to launch a healthy meal delivery business in Germany.
     Give me a market research report.
```

The agent needs a product and one country. If you name no country and none
is saved for you, it asks.

### Review the competitors

Before the detailed research, the agent stops and shows what it found:

```
[approval needed] Competitors found for healthy meal delivery in Germany:
  1. HelloFresh  (https://www.hellofresh.com)
  2. Factor  (https://www.factormeals.de)
  3. EASY MEAL  (https://www.easymeal.de/so-gehts)
  4. Prepmymeal  (https://prepmymeal.com)
  5. Every Foods  (no website found)
  Verified but left out: EatFitter, Tellerglück
  Dropped: ChefCoco (different product ...)
  Type: approve | remove 2,4 | add <company> | remove 4; add <company> | cancel
Your decision: remove 5; add Marley Spoon
```

| You type | Result |
|---|---|
| `approve` | Research continues with this list |
| `remove 2,4` or `remove Factor` | Those companies are dropped |
| `add Marley Spoon` | The company joins the list and is researched like the others |
| `remove 5; add Marley Spoon` | Both at once |
| `cancel` | The report stops; no more research is done |

### Ask follow-up questions

```
You: Go deeper on pricing for the cheapest competitor you found.
```

### Save the report

```
You: Save this report.
[approval needed] Save this report as reports/2026-11-16-healthy-meal-delivery-germany.md?
  Type: approve | reject | title <new title>
Your decision: title Germany meal delivery
```

Reports are saved as Markdown files in the `reports/` folder.

### Memory

Say something about yourself once, and later conversations know it:

```
You: I am opening a vegan bakery in the Netherlands.
(a new conversation, later)
You: Is demand for vegan cakes rising?
     -> the agent checks the Netherlands without asking
```

To clear it: `Please forget my saved preferences.`

### Run only the report workflow

To see each step of the workflow without the chat:

```bash
python -m agent.report.demo "healthy meal delivery" Germany
python -m agent.report.demo "healthy meal delivery" Germany --facts
```

## Example use cases

| # | You ask | What the agent does |
|---|---|---|
| 1 | "I want to launch a healthy meal delivery business in Germany. Give me a market research report." | Runs the report workflow, pauses for your competitor review, returns the six-section report |
| 2 | "Go deeper on pricing for the top three competitors you found." | Opens the competitors' own pages and lists current prices with links |
| 3 | "Is there a market for vegan protein snacks?" | No country given, so it asks which country you mean |
| 4 | "Should I invest my savings in this business?" | Declines to give investment advice and offers market facts instead |
| 5 | "Save this report." | Asks for your approval, then writes the file |
| 6 | "Is demand for meal kits rising in Germany?" | Reads Google Trends and reports the direction, with a reliability warning if searches are few |
| 7 | "Please forget my saved preferences." | Deletes your saved profile |

## How it works

There are two parts, and they are deliberately different.

### 1. The chat agent

A ReAct agent built with LangChain's `create_agent`. The model reads the
conversation, decides whether to call a tool, reads the result, and repeats
until it can answer. It handles the conversation: clarifying questions,
follow-ups, refusals and saving.

Its nine tools:

| Tool | Purpose |
|---|---|
| `create_market_report` | Runs the report workflow (below) |
| `web_search` | Market size, competitors, products, prices |
| `search_news` | News from the last month |
| `read_webpage` | Opens one page and reads all of it |
| `get_demand_trend` | Whether search interest is rising or falling |
| `get_company_financials` | Revenue, employees, founding year |
| `save_report` | Writes the latest report to a file |
| `remember_preference` | Saves a preference when you ask |
| `forget_preferences` | Deletes your saved profile |

### 2. The report workflow

A LangGraph graph with a fixed order of steps. The chat agent calls it as
one tool.

```
understand_request                     turn the request into local-language search words
        |
find_candidates                        search; list the companies the results name
        |
verify_competitor   (in parallel)      does it sell this product, in this country?
        |
select_competitors                     rank by mentions, keep the top five
        |
review_competitors                     PAUSE: you approve, edit or cancel
        |
        +-- research_competitor (in parallel)   figures; prices from the company's own site
        +-- research_market                     figures with the area and year they cover
        +-- research_news                       recent, relevant news
        +-- research_trend                      demand trend from a specific search word
        |
collect_facts
        |
write_swot    (retried once if incomplete)
        |
assemble_report                        build the text in code, then check it
```

Every step follows one pattern: **code gathers the material, the model does
one narrow job on it and answers in a fixed shape, and code checks the
answer before accepting it.**

Examples of those checks:

- A competitor's web address is accepted only if it was really in the
  search results and belongs to that company.
- A price is kept only if its number appears on the page that was read.
- A market figure is dropped if its number is not in the source it cites.
- Company figures are used only if the listed company's name starts with
  the brand name ("Factor" must not match "The Cheesecake Factory").

Sections 1 to 4 and 6 of the report are built by code from the checked
facts. Only the SWOT is written by the model, from those sections.

### Data sources and fallbacks

Each job has a list of sources, tried in order. The first that answers
wins, and the result says which one it was.

| Job | 1st | 2nd | 3rd |
|---|---|---|---|
| Web search | Tavily | Free metasearch (Bing, Yahoo, Google, DuckDuckGo) | Wikipedia |
| News | Tavily news | Google News | Metasearch news |
| Reading a page | Tavily Extract | Direct fetch | |
| Company figures | Yahoo Finance | Wikidata | |
| Demand trend | Google Trends | Wikipedia page views | |

All backups are free and need no key.

### Memory

| | Short-term | Long-term |
|---|---|---|
| Holds | The conversation, including reports | Your region, industry, business idea, report style |
| Scope | One conversation | All your conversations |
| LangGraph piece | Checkpointer | Store |
| Saved in | `data/memory.db` (SQLite) | `data/memory.db` (SQLite) |

### Middleware

Middleware is code that runs around the agent's model and tool calls.

| Middleware | What it does |
|---|---|
| `capture_profile` | Before answering, extracts lasting facts from your message and saves them |
| `prompt_with_profile` | Adds your saved profile to the system prompt on every call |
| `require_country_from_user` | Blocks a market tool call for a country you never named |
| `ModelFallbackMiddleware` | Repeats a failed call with a backup model (off by default) |
| `HumanInTheLoopMiddleware` | Pauses for approval before a report is saved |

### Human-in-the-loop

Two approval points use the same LangGraph mechanism, an interrupt, set up
in two ways:

| | Competitor review | Save approval |
|---|---|---|
| Purpose | Quality: your judgement on the list | Safety: nothing is written without consent |
| How | An `interrupt()` call placed in the workflow | LangChain's ready-made middleware |

While waiting, the state is saved, so you can close the program and answer
later.

## Technical decisions

**A fixed workflow for reports, a free agent for conversation.** The first
version let one agent do everything. With seven things to remember it
skipped steps, listed US companies as German competitors, and took prices
from a 2021 article. Each prompt fix corrected one error and another
appeared. Moving the report into a workflow where code controls the order
and checks every result fixed those errors. The free agent is kept for
what it is good at: open conversation.

**When to use prompt engineering, RAG or agents.** Prompt engineering is
enough when the model already knows the answer and only the form matters.
RAG fits when answers live in a fixed set of documents. An agent fits when
the information must be fetched live from several places and each step
depends on the last, which is this project's case.

**The report text is built by code.** When the model wrote the whole
report it dropped sources and misattributed prices. Building tables and
bullets directly from checked facts makes those errors impossible. The
cost is plainer wording.

**The report is returned directly, not retyped.** The report tool uses
`return_direct`, so the chat model does not rewrite it. Retyping a long
report was slow and once corrupted every € sign and umlaut.

**What must always happen is done in code, not asked of the model.** Three
examples, each found by testing: the model did not call its "remember"
tool, so facts are now extracted and saved by middleware; it assumed the
United States when no country was given, so a middleware check now blocks
that tool call; it chose "Mahlzeit" (meal) as a trend word, so each word
is now checked by a separate yes-or-no question.

**Fallbacks for every source.** A research tool that fails when one
service is down is not usable. Each tool has free backups from different
companies.

**One model, with fallback support built in.** The agent uses
`openai/gpt-4.1-mini` through OpenRouter. Backup models from other
companies can be switched on with one line in `agent/config.py`.

**SQLite for memory.** It survives restarts, needs no server, and is one
file.

**Dependencies are passed in.** The workflow receives its model and data
sources as plain functions, so the tests replace them with fakes.

## Error handling and safety

- **Missing API key**: a clear setup message, no crash.
- **A failed source**: the next source is tried; if all fail, the tool
  returns a readable message and the report says "not found".
- **A failed step in the workflow**: the user gets a readable message.
- **A runaway loop**: tool rounds are limited to 12 per question.
- **Opening web pages**: only `http` and `https`; local and private network
  addresses are blocked, also after redirects; downloads are capped at 2 MB.
- **Prompt injection**: text from tools is treated as information, never
  instructions; values saved to memory are cut to one short line.
- **Saving files**: only into `reports/`; a title can never contain a path;
  nothing is written without approval.
- **Privacy**: only four fixed kinds of fact can be remembered; names,
  contact details and finances are not saved; `data/` and `.env` are
  excluded from Git.
- **Boundaries**: investment advice and off-topic requests are declined.

## Tests

```bash
pytest
```

300 tests, none of which use the internet or cost anything: outside
services and the model are replaced with fakes.

| Test file | Covers |
|---|---|
| `test_tools.py`, `test_sources.py`, `test_wikidata.py` | The tools and data sources |
| `test_fallback.py` | Trying sources in order, timeouts |
| `test_webpage.py` | The page reader and blocked addresses |
| `test_trends.py` | The rising, falling or stable calculation |
| `test_names.py` | Matching company names |
| `test_report_workflow.py`, `test_report_research.py`, `test_report_writing.py` | The report workflow, step by step |
| `test_report_check.py` | The report checker |
| `test_memory.py` | Both kinds of memory and the country check |
| `test_approval.py` | Every decision at both approval points |
| `test_agent.py` | How the agent is assembled; model fallback |

## Project structure

```
market-research-assistant/
├── main.py                  terminal chat
├── agent/
│   ├── agent.py             builds the chat agent and its middleware
│   ├── prompts.py           the system prompt
│   ├── tools.py             the single-question tools
│   ├── memory.py            checkpointer, store, user profile
│   ├── memory_tools.py      remember and forget tools
│   ├── approval.py          the two approval points
│   ├── fallback.py          try sources in order
│   ├── report_check.py      checks a finished report
│   ├── trends.py            rising, falling or stable
│   ├── countries.py         country names and codes
│   ├── names.py             comparing company names
│   ├── models.py            creates the chat model
│   ├── config.py            settings
│   ├── report/              the report workflow (LangGraph)
│   │   ├── graph.py         nodes and edges
│   │   ├── state.py         the workflow's data
│   │   ├── steps.py         find and verify competitors
│   │   ├── review.py        the human review step
│   │   ├── research.py      figures, prices, market, news, trend
│   │   ├── writing.py       SWOT and final check
│   │   ├── render.py        builds the report text
│   │   ├── tool.py          the tool the chat agent calls
│   │   └── demo.py          runs the workflow from the terminal
│   └── sources/             one file per outside service
├── tests/
├── reports/                 saved reports (not in Git)
├── data/                    memory file (not in Git)
├── requirements.txt
└── .env.example
```

## Known limitations

**Not built yet**

- There is no web interface yet. The Streamlit app is the next step.
- Token usage and cost are not shown.
- Tracing with LangSmith is prepared in `.env.example` but not switched on.

**Report quality**

- Reports are accurate but sometimes sparse. A price that cannot be read
  from the company's own site is reported as "not found"; an older
  third-party figure is not substituted. HelloFresh's prices, for example,
  load with JavaScript and cannot be read.
- Small private companies have no public figures.
- A demand trend is found in some runs and not others, because the search
  words the model proposes vary.
- A price can be real and correctly sourced, yet for a different product
  than the one asked about.
- A product name can occasionally be mistaken for a company. The competitor
  review exists partly to catch this.
- Reports differ between runs: the competitors chosen and the wording vary.
- Reports are in English only, so some local-language sources are missed.
- Market-size figures come from public summaries of paid reports. They are
  estimates published by others, not verified statistics.

**The chat outside a report**

- A direct question answered without the workflow does not get the
  workflow's verification. In testing, such an answer once named a US
  company as a competitor in Germany.

**Technical**

- All models are reached through OpenRouter, which is a single point of
  failure: if it is down, or the credit runs out, no model answers.
- Backup sources give thinner results than the main ones.
- There is one user. Everything is stored under one profile.
- Conversations are never shortened, so a very long one costs more per
  turn.
- The address check for the page reader does not defend against a domain
  whose address changes between the check and the download.
- The prompt rule against injected instructions reduces that risk; it does
  not remove it.

## What I would improve

1. Build the Streamlit app, with the competitor review as checkboxes and
   the report rendered as a document.
2. Measure report quality with an evaluation set, so changes can be judged
   by numbers and not by reading reports.
3. Read prices from pages that need JavaScript, with a headless browser.
4. Add a second model provider key to remove the OpenRouter dependency.
5. Give the single-question path the same competitor verification as the
   workflow.
6. Summarise long conversations to control cost.
7. Add user accounts so several people can use one installation.
