# <img src="ui/static/logo.svg" alt="" height="34"> Markavi

**Your AI market research assistant: verified competitors, first-hand prices, every fact linked to its source.**

[![Tests](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/tests.yml) [![Deploy](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/deploy.yml/badge.svg)](https://github.com/Anusha-3109/market-research-assistant/actions/workflows/deploy.yml)

Markavi researches a market for a first-time founder: it finds the real competitors in a country, reads their prices from their own websites, collects market figures, news and demand trends, and writes a six-section report in which every fact links to its source. It pauses so you can review the competitor list, and asks before it saves a file. It is built with LangChain, LangGraph, OpenRouter (GPT-4.1 mini by default) and Streamlit, and combines a ReAct agent with a fixed report workflow, memory and human-in-the-loop approval.

The Sprint 3 task description is in [`135.md`](135.md).

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
| Web app | Example cards to start from, then a research view: the answer on the left, live steps and numbered sources on the right, one tab per question |
| Market research report | Six fixed sections: market overview, competitors, pricing, trends, SWOT analysis, references |
| Verified competitors | Each candidate is checked: does it sell this product, in this country? Others are dropped with the reason |
| First-hand prices | Read only from the competitor's own website; the source link is set by code |
| Follow-up questions | Answered with single tools: search, news, page reader, demand trend, company figures |
| Your review | The agent pauses so you can approve, remove or add competitors, or cancel |
| Save with approval | A report is written to a file only after you approve, and you can change the title |
| Memory | Remembers the conversation across restarts, and your country, industry and idea across conversations |
| Numbered sources | Every link in an answer becomes a number such as [1]; the source list shows each page's title and site, and marks a company's own site as Official |
| Download | Any answer as a Markdown file or a PDF |
| Stop | A run can be stopped; what was found so far is kept and the conversation continues |
| Resilience | Every data source has a free backup, so one outage does not stop a report. If the model leaves out a required field, the question is asked again instead of losing the report |
| Deployed | Runs on Google Cloud Run behind a password, and redeploys itself after the tests pass |

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
fraction of a cent. The app shows the exact figure under every answer.

## How to use it

### The start screen

Nine example cards float around the headline. Click one to open its picker,
or type your own question in the box at the bottom.

### The pickers

Each card opens a picker screen: a box in the middle of the page and rows of
chips underneath. Clicking chips fills the box with a complete question, and
you can change it or type your own before pressing **Research**. Nothing is
sent to the assistant until you press the button, so opening a picker and
trying chips costs nothing.

| Card | Chips | What the box reads, for example |
|---|---|---|
| Write a report | Product, country | Give me a market research report for oat milk in Germany. |
| Check demand | Product, country | Is interest in oat milk rising in Germany? |
| Follow the news | Product, country | What has changed recently in the organic baby food market in France? |
| Find competitors | Product, country | Who are the main companies selling vegan snacks in the United Kingdom? |
| Size a market | Product, country | How big is the pet food market in the Netherlands? |
| Research a company | Company | How big is HelloFresh? Give me its revenue and number of employees. |
| Compare prices | Company | What does Prepmymeal charge? |
| Test my idea | Business idea, country | I want to open a vegan bakery in the Netherlands. Give me a market research report. |
| Set your market | Country, industry | I am based in Germany and I work in meal delivery. (the button reads **Save**) |

Products, companies and business ideas are grouped by industry. The first
row of a picker chooses the industry (food and drink, beauty and skincare,
pet care, health and fitness, baby and kids, fashion, home and living), and
the rows below show that industry's chips: ten products, eight to ten
companies and four business ideas each. The twelve countries are the same
for every industry.

One chip can be chosen per row; clicking it again takes it back. A company
chip shows the company's own icon, or its first letter where the site has
none. **Back to start** returns to the cards.

The wider card, **"Learn how Markavi works"**, opens a guide in the chat:
five numbered step cards, a written explanation, and follow-up chips
("Where do the prices come from?", "Why check the competitors?"). The guide
is fixed text, so it appears instantly and costs nothing.

On a narrow window the cards sit in rows of three.

The Markavi logo, a dark tile with a rising line, appears next to the
name in the sidebar, on the "Learn how Markavi works" card, on the
password screen of the deployed copy, and as the icon of the browser tab.

### Ask for a report

Type, or click "Write a report":

```
I want to launch a healthy meal delivery business in Germany.
Give me a market research report.
```

The agent needs a product and one country. If you name no country and none
is saved for you, it asks. While it works, a progress box lists each step
as it finishes.

### Review the competitors

Before the detailed research, the agent stops and shows a form:

- a tick box for each competitor it found, with its website;
- companies it verified but left out, which you can tick to include;
- an "Add a company" field for any it missed;
- the companies it dropped, with the reason for each;
- **Continue** and **Cancel report** buttons.

Untick what does not belong, add what is missing, and continue. Cancelling
stops the report with no further research.

### The research view

Every answer, whether a full report or a single question, opens in the
same two-column view:

| Where | What it shows |
|---|---|
| Left | The answer. Each fact carries a small number such as [1] that links to its source |
| Right, top | "Researching" with a timer and each step as it happens, then "Done" with the full list and what the answer cost, for example "4,367 tokens · $0.00076" |
| Right, below | "Sources": the numbered pages the answer cites, with their site. A company's own site is marked **Official** |
| Top | One tab per question in the conversation. The newest opens first |

While the agent is working, the answer panel shows a placeholder and a
**Stop** button ends the run. What was found up to that point is kept and
the conversation can continue.

A report also shows its "Report check" result above the text.

### Download and save

| Button | What it does |
|---|---|
| Markdown | Sends the answer to your own computer as a Markdown file |
| PDF | The same as a PDF, with working links and tables |
| Save to reports folder | Asks the agent to save a report in the app's `reports/` folder |
| Research another market | Opens a new, empty conversation |

Saving shows a form in the answer panel with an editable title, and
**Save** and **Don't save** buttons. Nothing is written until you press
Save. The competitor review form appears in the same place.

### Ask follow-up questions

```
Go deeper on pricing for the cheapest competitor you found.
```

Type it in the box at the bottom. It becomes a new tab next to the earlier
ones, so the report stays one click away.

### Conversations

Open the sidebar with the arrow at the top left.

- **New conversation** starts a fresh one.
- Earlier conversations are listed by their first question. Click one to
  reopen it.

Conversations are saved in `data/memory.db`. The conversation id is in the
page address, so refreshing the page, or closing and reopening it, shows
the same chat. A form that was waiting for your decision is still there.

### Memory

The sidebar has a **What I remember** panel showing your saved region,
industry, business idea and report style. **Forget me** deletes them; your
conversations are kept.

Say something about yourself once, and later conversations know it:

```
I am opening a vegan bakery in the Netherlands.
(a new conversation, later)
Is demand for vegan cakes rising?
     -> the agent checks the Netherlands without asking
```

To clear it, press **Forget me**, or type `Please forget my saved preferences.`

### Settings and help

Both are in the sidebar, closed by default so they stay out of the way.

| Setting | What it does |
|---|---|
| Model | Chooses between three models from different companies, all reached through OpenRouter |
| Temperature | Lower gives more factual, repeatable answers; higher gives more varied wording |
| Maximum answer length | A hard limit on one chat answer: Short, Medium, Long or No limit |
| Answer style | How answers are worded: Balanced, Formal, Friendly or Concise |
| Review competitors before a report | Turn off for a quicker report with no pause |

**Answer style** changes the wording only, never what is true:

| Style | How the assistant writes |
|---|---|
| Balanced | Its normal way; the default |
| Formal | Complete sentences and professional wording, for a document you hand to a bank or a partner |
| Friendly | Warm and plain, with business terms explained in everyday words |
| Concise | The shortest useful answer, without introductions or closing remarks |

It applies to answers to single questions and to the SWOT section of a
report. A report's six sections, its tables, numbers, prices and source
links are the same in every style. If you once told the assistant how you
like answers written, the style chosen here wins where the two disagree.

**Maximum answer length** is the model service's own limit, known there as
"max tokens". A token is about three quarters of a word:

| Position | Limit | Roughly |
|---|---|---|
| Short | 250 tokens | 180 words |
| Medium | 600 tokens | 450 words |
| Long | 1,200 tokens | 900 words |
| No limit | none | the default |

It is not the same as the Concise style. Concise asks the model to write
briefly and the model decides how. The limit is enforced: an answer that
reaches it stops there, and a line under it says it was cut off. A report is
never cut; the limit applies to chat answers only.

The model, the temperature, the answer style and the competitor review
apply to the chat and to the report workflow. They are locked
while the assistant is waiting for your decision, because changing them
would change how a paused report continues.

**Help** summarises what the assistant can and cannot do, and opens the
"How it works" guide.

### Terminal chat (for development)

The same agent also runs in the terminal, printing every step:

```bash
python main.py                      # new conversation
python main.py --thread a1b2c3d4    # continue an earlier one
```

Approvals are typed: `approve`, `remove 2,4`, `add Marley Spoon`, `cancel`
for the competitor review; `approve`, `reject`, `title <new title>` for
saving.

To run only the report workflow, without the chat:

```bash
python -m agent.report.demo "healthy meal delivery" Germany
```

## Example use cases

| # | You ask | What the agent does |
|---|---|---|
| 1 | "I want to launch a healthy meal delivery business in Germany. Give me a market research report." | Runs the report workflow, pauses for your competitor review, returns the six-section report |
| 2 | "Go deeper on pricing for the top three competitors you found." | Opens the competitors' own pages and lists current prices with links |
| 3 | "Is there a market for vegan protein snacks?" | No country given, so it asks which country you mean |
| 4 | "Should I invest my savings in this business?" | Declines to give investment advice and offers market facts instead |
| 5 | "Save this report." | Shows the save form, then writes the file if you approve |
| 6 | "Is demand for meal kits rising in Germany?" | Reads Google Trends and reports the direction, with a reliability warning if searches are few |
| 7 | "Please forget my saved preferences." | Deletes your saved profile |

## How it works

There are three parts.

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

### 3. The web app

A Streamlit app, kept as a thin layer over the agent. It calls four
functions and contains no agent logic:

| Function | Used when |
|---|---|
| `stream_steps` | The user asks a question |
| `resume_steps` | The user submits an approval form |
| `pending_pause` | The page loads, to see if a form should be shown |
| `settle_stopped_turn` | The page loads, to tidy a run that was stopped half-way |

Streamlit reruns the page script on every click, so nothing important is
kept in the page. The conversation is read from the agent's saved state on
each run, and the conversation id lives in the page address. That is why a
refresh loses nothing.

Progress appears live because the report tool sends each step's line
through LangGraph's stream writer while it is still running.

**Numbered citations** are made by code, not by the model. The model
writes ordinary links; `agent/citations.py` replaces each with a number,
gives a page cited twice the same number, and builds the source list. Page
titles come from the search results that found them. A site is marked
Official when the report workflow confirmed it as a competitor's own, or,
for a single question, when the question names it.

**Stop** works because Streamlit ends the running script when any button
is pressed. A run cut off while a tool was working leaves the saved
conversation ending in a tool request with no result, which a model
refuses to continue from. `settle_stopped_turn` gives each open request
the result "stopped" the next time the page loads.

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
| In the app | A form with tick boxes | A form with an editable title |

While waiting, the state is saved, so you can close the page and answer
later. The workflow runs as a sub-graph that saves its own progress, so
continuing does not repeat the searches done before the pause.

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

**The web app holds no state of its own.** Everything shown is read from
the agent's checkpointer. This is what lets a refresh, a restart or a
second browser tab show the same conversation and the same waiting form,
and it kept the app small: the forms only collect input and hand it over.

**Logic for the app lives outside Streamlit.** Turning saved messages into
questions and answers, numbering citations, building the PDF, listing
conversations and turning form input into the agent's answer are plain
functions in `agent/session.py`, `agent/citations.py`,
`agent/pdf_export.py` and `agent/approval.py`, tested without a browser.

**HTML, CSS and JavaScript are real files.** Streamlit draws most of the
page from Python, but the look (`styles.css`), the source list, the guide's
step cards and two small scripts are written in their own languages and
kept in `ui/static/`. Python loads them and fills in the blanks. Every
value put into a template is escaped by `fill()` in `ui/assets.py`, so a
page title from the web is always shown as text and can never act as
markup.

**A style is one instruction, added last.** Each answer style is a short
instruction in `agent/styles.py`, appended to the system prompt after all
the rules. "Balanced" adds nothing, so the default behaviour is exactly
what it was. The list of styles and the default are settings in
`agent/config.py`, with the other settings.

Because it comes last, the added section says what it overrides and what it
leaves alone, so the model does not have to guess:

- it replaces the standing line that asks for concise bullet points, which
  would otherwise contradict the Formal style;
- it wins over a style the assistant remembers from an earlier message,
  which still applies wherever it does not contradict;
- a table stays a table, and a refusal is still a refusal;
- the facts, numbers and source links stay the same.

The report workflow passes the style only to its SWOT step, the one part
the model words freely.

The last point is an instruction, and an instruction can be forgotten: in
test runs the Friendly style left out the source link in about one answer in
thirty. So it is also checked by code, see the next decision.

**The cost shown is the cost charged.** The model service, OpenRouter,
returns with every call the tokens it read and wrote and what the call cost
in US dollars. The app adds those up and shows them; it does not multiply
tokens by a price list, which would be wrong as soon as a price changed. If
the service gives no cost for a call, the app says "cost not reported" and
never invents one.

The app calls a model in three places, and each needed its own way of
counting:

| Where | How it is counted |
|---|---|
| The chat agent | Each reply is a message in the saved conversation and carries its own figures, so they are simply read back |
| The report workflow, about 20 calls per report | Its replies are not messages. Each step runs inside a collector, and what was collected is stored in the report's own state. It therefore survives the pause for the competitor review, adds up across the steps that run in parallel, and includes a call that had to be repeated |
| A background call that reads each message for facts to remember | Its figures are kept with the user's message and shown with the answer to it |

A report that was cancelled at the review, or that failed, still shows what
it cost up to that point. All the arithmetic and wording is in
`agent/usage.py`.

It was checked against the service itself: for one question and one report
the app counted 26 calls and $0.030615, and the account at OpenRouter showed
$0.030615 spent in the same period.

**A length limit that cannot break the research.** The limit is set on each
model call of the chat agent by one piece of middleware,
`limit_answer_length`. The model service says why it stopped writing, and
the middleware uses that:

- an answer that was cut keeps what was written and gets a note, so a
  sentence that stops half-way does not look like a fault of the app;
- a step that was cut, such as a half-written request for a tool, is useless,
  so the model is asked for that step again without the limit.

The report workflow has its own model calls and never receives the limit: a
report is built from several structured answers, and a cut-off one would
fail. The source check runs outside the limit, so an answer that was cut off
still ends with its source.

**The source check: code puts a missing link back.** `agent/source_check.py`
wraps every model call. When the model has finished an answer, it looks at
the tools used for that question. If they reported where their information
came from and the answer links to nothing, the links are added on a last
line, "Sources: ...", at most five. An answer that already has a link, or
that used no tool, is left exactly as written. The corrected answer is the
only one saved, so the conversation never holds two versions.

This is the same idea as the report workflow: the model writes, code checks.

The check only trusts addresses this app wrote itself. A tool result mixes
the app's own lines ("URL:", "Source:") with text copied from the web, and a
web page could contain a line that looks like one of them. So each tool has
its own reader that knows where the app's lines are in that tool's result,
and a tool without a reader adds nothing. Search titles are kept on one line
for the same reason. Two tests failed on exactly this before the fix.

**The pickers are data.** What each start card offers (its headline, its
chip rows and the question they build) is one entry in `PICKERS` in
`ui/picker.py`, and the chip lists are plain lists above it. Adding a
product, a country or a whole new card is a change to that data, with no
new drawing code. The question is built by plain functions that are tested
without a browser.

**One logo file.** The logo is a single SVG, `ui/static/logo.svg`. The
app, the browser tab and this README all use that one file. Streamlit does
not serve files from `ui/static/`, so inside the app the picture is passed
to the stylesheet as a CSS variable and drawn from there.

**The name is set once.** `APP_NAME` in `agent/config.py` is the only
place the app's name is written; the page title, the sidebar, the guide
and the password screen all read it from there.

**Download and save are separate.** A download goes to the user's own
computer and needs no approval. Saving writes on the machine running the
app, so it goes through the agent and its approval step.

**Fallbacks for every source.** A research tool that fails when one
service is down is not usable. Each tool has free backups from different
companies.

**One default model, a choice of three, and fallback support.** The agent
uses `openai/gpt-4.1-mini` through OpenRouter by default. The settings
offer two more, from Anthropic and Google. The choice travels with each
request in a context object, so the report workflow, which runs inside a
tool, follows it too. Automatic fallback to a backup model can be switched
on with one line in `agent/config.py`.

**Developer settings are kept apart from the everyday experience.** Model,
temperature and the review switch sit in a closed section of the sidebar.
A first-time user never needs to open it.

**SQLite for memory.** It survives restarts, needs no server, and is one
file.

**Dependencies are passed in.** The workflow receives its model and data
sources as plain functions, so the tests replace them with fakes.

## Error handling and safety

- **Missing API key**: the app shows setup instructions, no crash.
- **Unusable input**: an empty message, or one over 2,000 characters, is
  turned back before it reaches the model.
- **Failures explained in plain words**: a rejected key, an empty account,
  a rate limit, a timeout or a lost connection each get their own message
  saying what to do.
- **A failed source**: the next source is tried; if all fail, the tool
  returns a readable message and the report says "not found".
- **An answer from the model in the wrong shape**: in the report workflow
  the question is asked again, up to three times, with the problem named.
- **A run stopped half-way**: the conversation is tidied the next time the
  page loads, so it can continue.
- **A failed step in the workflow or the model**: the app shows a readable
  error and keeps it on screen.
- **A runaway loop**: tool rounds are limited to 12 per question.
- **Opening web pages**: only `http` and `https`; local and private network
  addresses are blocked, also after redirects; downloads are capped at 2 MB.
- **Prompt injection**: text from tools is treated as information, never
  instructions; values saved to memory are cut to one short line.
- **An answer without its source**: if the tools reported a source and the
  answer links to nothing, code adds the link. Only addresses the app wrote
  itself are used, so text on a web page cannot add a link of its own.
- **Saving files**: only into `reports/`; a title can never contain a path;
  nothing is written without approval.
- **Privacy**: only four fixed kinds of fact can be remembered; names,
  contact details and finances are not saved; `data/` and `.env` are
  excluded from Git.
- **A deployed copy**: a password screen comes before anything else, the
  keys live in Secret Manager and never in the image, and the app runs as
  an account that can reach only its own secrets and bucket.
- **Boundaries**: investment advice and off-topic requests are declined.

## Tests

```bash
pytest
```

585 tests, none of which use the internet or cost anything: outside
services and the model are replaced with fakes.

| Test file | Covers |
|---|---|
| `test_tools.py`, `test_sources.py`, `test_wikidata.py` | The tools and data sources |
| `test_fallback.py` | Trying sources in order, timeouts |
| `test_webpage.py` | The page reader and blocked addresses |
| `test_trends.py` | The rising, falling or stable calculation |
| `test_names.py` | Matching company names |
| `test_report_workflow.py`, `test_report_research.py`, `test_report_writing.py` | The report workflow, step by step |
| `test_report_deps.py` | Asking the model again when its answer is missing a required field |
| `test_report_check.py` | The report checker |
| `test_memory.py` | Both kinds of memory and the country check |
| `test_approval.py` | Every decision at both approval points, live progress, form answers |
| `test_session.py` | Chat bubbles from saved messages; listing conversations |
| `test_guide.py` | The "How it works" guide content |
| `test_guards.py` | The input guard and the plain-language error messages |
| `test_citations.py` | Numbered citations, the source list, the Official mark, questions paired with answers |
| `test_pdf_export.py` | The PDF: valid file, working links, safe handling of text from the web |
| `test_assets.py` | Loading the HTML, CSS and JavaScript files; escaping of values put into templates |
| `test_deploy.py` | A deployed copy: where data is stored, the copy of the memory file and its restore, the password screen |
| `test_usage.py` | Token usage and cost: a chat answer, a report across its review pause, a cancelled report, a repeated call, the background call, a call with no reported cost, the wording, the page |
| `test_answer_length.py` | The maximum answer length: the limit reaches the model, a cut-off answer says so, a cut-off step is repeated, reports are never cut, the slider on the page |
| `test_source_check.py` | The source check: a missing link is put back, an answer that has one is left alone, and addresses inside web text are never used |
| `test_styles.py` | The answer styles, checked by what the model is told: in a chat turn, while a report is written, and from the setting on the page; and that every style keeps the facts and their sources |
| `test_picker.py` | The pickers: which question the chips build, and clicking through one on the page |
| `test_app.py` | The page itself, run without a browser: cards, the research view and its tabs, guide, sidebar, approval form, a stopped run, missing key |
| `test_agent.py` | How the agent is assembled; model fallback |

`test_app.py` uses Streamlit's `AppTest` with a fake agent, so it checks what
the page shows and what a click does. How the page looks was checked by
hand in a browser: the start screen at several window sizes, a full report
through both forms, a refresh while a form was open, reopening earlier
conversations, and the sidebar panels.

## Deployment

Markavi runs on **Google Cloud Run**:
<https://markavi-1037824678664.europe-west1.run.app>. It asks for a
password before anything else is shown, so that a stranger with the link
cannot spend the API credit. Ask the author for the password.

Everyone who signs in shares one memory and one list of conversations: the
app has a single user (see [Known limitations](#known-limitations)).

### How it is set up

| Part | Setting |
|---|---|
| Project | Its own Google Cloud project, `markavi-research`, with nothing shared with other apps |
| Service | Cloud Run `markavi` in `europe-west1`: 1 CPU, 1 GiB, at most 1 running copy, shuts down when unused, session affinity for Streamlit's connection |
| Image | Built from the `Dockerfile` and kept in Artifact Registry. It holds only the app: no keys, no local data, no tests. It runs as a non-root user |
| Keys | `OPENROUTER_API_KEY`, `TAVILY_API_KEY` and `APP_PASSWORD` are in Secret Manager and passed in as environment variables. They are never in the image or the repository |
| Saved data | A private Cloud Storage bucket mounted at `/mnt/data` (`DATA_DIR`) |
| Identity | The app runs as its own service account, which can read only those three secrets and use only that bucket |

### The two settings a deployed copy uses

Both are empty on your own computer, where nothing changes.

| Setting | What it does |
|---|---|
| `APP_PASSWORD` | Puts the password screen in front of the app |
| `DATA_DIR` | The folder that survives restarts. Saved reports are written straight into it. The memory file is handled differently, see below |

### Why the memory file is copied instead of stored in the bucket

Cloud Run wipes the machine's own disk whenever the service restarts, so
data has to live in the bucket. But the memory file is a database that is
written after every step of the agent and needs file locking, which a
mounted bucket does not offer. A mounted bucket also uploads the whole file
again on every save.

So the database works on the machine's own disk, and
`backup_memory()` in `agent/memory.py` writes a complete, consistent copy to
the bucket after every answer, approval, stopped run and "Forget me". On
start, `restore_memory()` brings the copy back. This was checked on the live
service: a conversation was still there after a restart.

It relies on at most one running copy, which is why the service is limited
to one. If the service stops in the middle of an answer, that one answer is
lost; everything before it is kept.

### Automatic deploys

Two GitHub workflows in `.github/workflows/`:

| Workflow | When | What |
|---|---|---|
| Tests | Every push to `main`, and pull requests | Runs the test suite. It needs no keys |
| Deploy | After Tests pass on `main` | Builds the image, pushes it, and updates the service with it |

A deploy changes only the image. The secrets, the bucket and the limits
stay as they are. If the tests fail, nothing is deployed.

GitHub signs in to Google Cloud with Workload Identity Federation: no key
file is stored anywhere, and Google Cloud accepts only this repository's
`main` branch. A separate deployer account can upload images, update this
one service and nothing else. Copies of the repository, such as the course
submission, run the tests but skip the deploy.

Each deploy restarts the service, so visitors enter the password again.
Their conversations come back from the bucket.

### Run the image yourself

```bash
docker build -t markavi .
```

```bash
docker run -p 8080:8080 -e OPENROUTER_API_KEY=... -e TAVILY_API_KEY=... -e APP_PASSWORD=choose-one markavi
```

Then open <http://localhost:8080>.

### Deploy by hand

Normally a push to `main` does this. To do it yourself, from PowerShell
(Git Bash rewrites paths such as `/mnt/data`):

```bash
docker build -t europe-west1-docker.pkg.dev/markavi-research/markavi/app:manual .
```

```bash
docker push europe-west1-docker.pkg.dev/markavi-research/markavi/app:manual
```

```bash
gcloud run deploy markavi --image europe-west1-docker.pkg.dev/markavi-research/markavi/app:manual --region europe-west1 --project markavi-research
```

## Project structure

```
market-research-assistant/
├── app.py                   the web app
├── main.py                  terminal chat, for development
├── ui/                      the Streamlit interface
│   ├── styles.py            adds the stylesheet to the page
│   ├── assets.py            loads the HTML, CSS and JavaScript files
│   ├── static/              the interface's own HTML, CSS and JavaScript
│   │   ├── styles.css       the look: sky background, frosted panels
│   │   ├── *.html           templates: source list, guide steps, placeholder
│   │   ├── *.js             two small scripts that hold the scroll position
│   │   └── logo.svg         the Markavi logo
│   ├── start.py             start screen and example cards
│   ├── picker.py            the picker screen behind each card: box and chips
│   ├── guide.py             the "How it works" guide
│   ├── research.py          the research view: answer, steps, sources, live progress
│   ├── approvals.py         the two approval forms
│   ├── sidebar.py           conversations, memory, settings, help
│   ├── password.py          the password screen of a deployed copy
│   └── runtime.py           creates the agent once
├── agent/
│   ├── agent.py             builds the chat agent and its middleware
│   ├── prompts.py           the system prompt
│   ├── tools.py             the single-question tools
│   ├── memory.py            checkpointer, store, user profile
│   ├── memory_tools.py      remember and forget tools
│   ├── approval.py          the two approval points
│   ├── guards.py            input check and plain-language errors
│   ├── styles.py            the answer styles: formal, friendly, concise
│   ├── source_check.py      puts back the link to a source if an answer left it out
│   ├── answer_length.py     the limit on the length of a chat answer
│   ├── usage.py             token usage and cost of the model calls
│   ├── session.py           conversations, questions and answers, for any interface
│   ├── citations.py         numbered citations and the source list
│   ├── pdf_export.py        a report as a PDF file
│   ├── fallback.py          try sources in order
│   ├── report_check.py      checks a finished report
│   ├── trends.py            rising, falling or stable
│   ├── countries.py         country names and codes
│   ├── names.py             comparing company names
│   ├── models.py            creates the chat model
│   ├── config.py            settings, including the app name
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
├── Dockerfile               the image for Google Cloud Run
├── .dockerignore            what stays out of the image
├── .github/workflows/       tests on every push; deploy when they pass
├── .streamlit/config.toml   the app's theme
├── reports/                 saved reports (not in Git)
├── data/                    memory file (not in Git)
├── requirements.txt
└── .env.example
```

## Known limitations

**Not built yet**

- Tracing with LangSmith is prepared in `.env.example` but not switched on.

**Token usage and cost**

- Only model calls are counted. Web searches and page reading are billed by
  Tavily in its own credits; a report uses about 20 searches.
- A report written before this feature shows the chat part only, and says
  so. The workflow's calls were not recorded then.
- A run that was stopped shows what had been saved up to the stop. A model
  call that was in progress at that moment may be missing.
- The elapsed time of an answer is not saved, but its cost is.

**Maximum answer length**

- The limit counts tokens, so the word counts next to each position are
  approximate and differ between languages and models.
- An answer that reaches the limit stops in the middle of a sentence. It is
  marked as cut off, not completed.
- The limit was tried with the default model. The two other models in the
  settings are reached through the same service and should behave the same,
  but that was not checked.

**Answer styles**

- A style's wording is followed by the model, not enforced by code. Only
  one part is enforced: a missing source link is put back by the source
  check.
- The source check adds the pages the tools reported, not the exact page
  behind each sentence. After a search that is up to five pages, and the
  answer may rest on only one of them.
- It checks whether an answer has any link at all. An answer with one link
  and one unsourced figure passes.
- Whether an answer "sounds formal" is not tested automatically; it was
  judged by reading real answers.
- The styles were tried with the default model. The other two models in the
  settings may follow them more or less closely.

**The deployed copy**

- There is one user. Everyone who knows the password shares the same
  conversations and the same remembered profile.
- The first visit after a quiet period takes several seconds, while the
  service starts.
- A deploy, or the service shutting down while idle, signs everyone out.
- If the service stops in the middle of an answer, that answer is lost.

**The web app**

- A report takes 30 to 60 seconds after the competitor review, and the
  page cannot be used for another question meanwhile.
- The floating cards need a main area at least about 700 pixels wide and a
  window at least about 620 pixels tall. Below that they sit in rows.
- The look depends on Streamlit's internal page structure in a few places
  (the page background, the bottom bar, leftovers hidden during a live run), so a Streamlit
  upgrade may need small styling fixes.
- The time a run took is shown only in the browser session that ran it.
- The PDF uses built-in fonts that cover Western European text. Other
  scripts are replaced with "?".
- Styling and other changes to files in `ui/` and `ui/static/` only take effect after the
  app is restarted.
- Settings last for the browser session. They return to the defaults when
  the page is opened again.
- At the competitor review, some companies show "no website found yet".
  Their sites are usually found later, during the price research.

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
- There is one user. Everything is stored under one profile, and anyone
  who opens the app sees the same conversations.
- Conversations are never shortened, so a very long one costs more per
  turn.
- The address check for the page reader does not defend against a domain
  whose address changes between the check and the download.
- The prompt rule against injected instructions reduces that risk; it does
  not remove it.

## What I would improve

1. Switch on tracing with LangSmith.
2. Remember settings between visits.
3. Measure report quality with an evaluation set, so changes can be judged
   by numbers and not by reading reports.
4. Read prices from pages that need JavaScript, with a headless browser.
5. Add a second model provider key to remove the OpenRouter dependency.
6. Give the single-question path the same competitor verification as the
   workflow.
7. Add user accounts, so several people can use one installation with
   separate conversations and profiles.
8. Summarise long conversations to control cost.
