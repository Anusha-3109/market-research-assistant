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
| Assistant | A small chat at the bottom right of every view for a quick question in between, answered from the open report |
| Stop | A run can be stopped; what was found so far is kept and the conversation continues |
| Resilience | Every data source has a free backup, so one outage does not stop a report. If the model leaves out a required field, the question is asked again instead of losing the report |
| Accounts | On a deployed copy each person signs in to their own account, with their own conversations, remembered profile, settings and saved reports |
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
sign-in screen of the deployed copy, and as the icon of the browser tab.

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

### The three views of a conversation

The front page shows the example cards. Once a conversation is open, the
sidebar shows a picker with your conversations and links to its views. A
conversation has **Ask**; one that holds a report also has **Report**, and
**Snapshot** if the report's key figures were kept with it.

| View | What it shows |
|---|---|
| Snapshot | The report's key figures at a glance, in five tabs (see below), under a line that says how many sources the report cites. A conversation whose newest answer is a report opens here |
| Ask | The conversation as one chat. Every question is a bubble on the right, followed by the steps taken and the full answer with its numbered sources. Under each answer are its cost, its sources (folded away) and the downloads. A report is one line here, with an "Open report" button. Three suggestions for a next question sit under the chat, and the question box stays at the bottom of the window |
| Report | Each section of the report as a card with a status counted from its own text: how many values were "not found", or how many sources it cites. Beside the cards a box lists the contents, says what the report cost, and holds the downloads and "Save to reports folder" |

The Snapshot's tabs:

| Tab | What it shows |
|---|---|
| Overview | The key figures as cards, each with where and when it applies and a link to its source, and how many competitors were confirmed |
| Competitors | A table of the confirmed competitors: what they offer and their size or financials |
| Pricing | One price for each competitor, or "not found" |
| Trends | The search interest as a bar chart, with its direction |
| SWOT | Strengths, weaknesses, opportunities and risks, one box each |

A tab with nothing to show says so in one sentence.

While the agent is working, the chat shows the new question with each step
as it happens, a placeholder where the answer will be, the pages found so
far, and a **Stop** button that ends the run. What was found up to that
point is kept and the conversation can continue.

A figure in a foreign currency, such as a market size in US dollars for a
report on Germany, keeps its value exactly as the source wrote it. Under it
the Snapshot shows the same amount in the country's own currency, worded as
"about EUR 274 million, converted at the ECB rate of 18 Nov 2026".

### Report formats

In the Report view, the **Format** picker in the side box changes how a
report is laid out. It appears for a report whose key figures were kept
(the same reports that have a Snapshot).

| Format | What it shows | Downloads |
|---|---|---|
| Full market report | The report as written, section by section | Markdown, PDF |
| Investor one-pager | One page: key figures, competitors, demand, opportunities, risks and sources | Markdown, PDF |
| Pitch deck slides | Up to seven slides: title, the market, competitors, prices, demand with its bar chart, opportunities and risks, sources | PowerPoint |

The one-pager and the slides are put together by code from the figures
kept with the report. No model is asked, so switching format costs nothing
and adds nothing the report did not find. A part with nothing to show is
left out, and a price that was not found says "not found".

### Download and save

| Button | What it does |
|---|---|
| Markdown | Sends the answer to your own computer as a Markdown file |
| PDF | The same as a PDF, with working links and tables |
| Save to reports folder | Asks the agent to save a report in the app's `reports/` folder |

Saving shows a form on the page with an editable title, and
**Save** and **Don't save** buttons. Nothing is written until you press
Save. The competitor review form appears in the same place.

### Ask follow-up questions

```
Go deeper on pricing for the cheapest competitor you found.
```

Type it in the box at the bottom of the Ask view, or click one of the
suggestions. It is added to the chat under the earlier questions, and the
report stays one click away in the sidebar.

### The assistant

A round robot icon sits at the bottom right of every view. Clicking it
opens the assistant, a small chat of its own, for a quick question in between: what a term in the
report means, what the report says about a competitor, what to check next.

- It is given the newest report of the open conversation (or the newest
  answer, if there is no report) and answers from that.
- It searches nothing and starts no report. One question is one call to
  the model; the panel shows what the chat has cost. For new research it
  points to the Ask view.
- What is asked there is not added to the conversation.
- It stays open from one view to the next. Each conversation has its own
  chat; **New chat** empties it and the button with the line closes the
  panel.

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

**Accounts, without a new service.** A deployed copy asks each visitor to
sign in. Accounts are kept in the same store as the agent's long-term
memory, so they are saved and copied to the bucket with it; no database or
sign-in service was added.

| Rule | How it is kept |
|---|---|
| A password is never stored | Only a salted hash is stored, made with scrypt from Python's standard library. Two people with the same password have different hashes |
| Strangers cannot create accounts | Creating one needs an invite code, which is the `APP_PASSWORD` setting. Without it anyone with the link could spend the API credit |
| Guessing is slow | After five wrong tries in a row on a username, or on the invite code, further tries must wait a minute. The count is kept in the store, so a new browser window does not reset it |
| The screen does not reveal who has an account | An unknown username and a wrong password give the same message and take the same time |
| The address of a conversation is not a key to it | Each conversation records the account that asked its first question. Another account that opens its address gets an empty conversation |
| Nothing is created before sign-in | The agent, and with it the API keys, is only reached after someone has signed in |
| A password or email address is changed only by its owner | Both are changed on the sign-in page, with the username and the current password. Nothing inside the app can change them, so someone at a browser left open cannot take the account |
| A forgotten password is reset by a link sent by email | The link holds a long random token, of which only a hash is stored. It works once, for 30 minutes; asking again cancels the earlier link; at most three are given out per account per hour |
| The reset form does not reveal who has an account | It says the same thing whether or not an email went out, and the email is sent in the background so the answer takes the same time |

Each account has its own conversations, remembered profile, settings and
folder of saved reports. The first account to open the app takes over what
was saved before there were accounts; this happens once.

Without `APP_PASSWORD`, as on your own computer, there are no accounts: the
app opens directly for one user, as before. The rules are in
`agent/accounts.py` (accounts) and `agent/session.py` (whose conversation
is whose).

The email is sent through an ordinary mail account with Python's own mail
library (`agent/mailer.py`); no mail service was added. The message is
plain text, so a name someone typed can never become markup. Without the
three email settings the app shows no "Forgot password?" link.

**The cost shown is the cost charged.** The model service, OpenRouter,
returns with every call the tokens it read and wrote and what the call cost
in US dollars. The app adds those up and shows them; it does not multiply
tokens by a price list, which would be wrong as soon as a price changed. If
the service gives no cost for a call, the app says "LLM cost not reported" and
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
and the sign-in screen all read it from there.

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
- **A deployed copy**: a sign-in screen comes before anything else,
  passwords are stored only as salted hashes, each account sees only its
  own conversations and profile, the keys live in Secret Manager and never
  in the image, and the app runs as a service account that can reach only
  its own secrets and bucket.
- **Boundaries**: investment advice and off-topic requests are declined.

## Tests

```bash
pytest
```

882 tests, none of which use the internet or cost anything: outside
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
| `test_deploy.py` | A deployed copy: where data is stored, the copy of the memory file and its restore |
| `test_accounts.py` | Accounts: creating one, signing in, what is stored, what is refused, the wait after five wrong tries, the invite code |
| `test_sign_in.py` | The sign-in screen: nothing is shown or created before sign-in, wrong passwords and invite codes, a new account is signed in and copied at once |
| `test_ownership.py` | Whose conversation is whose: claiming, the list, opening by address, the first account taking over earlier data, the reports folder |
| `test_two_accounts.py` | Two accounts on one copy: neither sees the other's conversations or profile, and the agent is told only the asking account's profile |
| `test_account_changes.py` | Changing the password and the email address, and the link for a forgotten password: one use, 30 minutes, three per hour, never stored as it is |
| `test_mailer.py` | The email: whether it can be sent, the link, the message, an encrypted connection before the password, a mail server that fails |
| `test_password_pages.py` | The screens: asking for a link, the page the link opens, the email field of a new account, changing the password or the email address from the sign-in page |
| `test_assistant.py` | The assistant: what the model is sent, the panel in every view, that its questions stay out of the conversation, the cost, and a failure explained |
| `test_ask_view.py` | The Ask view: every question and answer in the chat, folding sources, a report as one line, the suggestions, the short reply and the steps |
| `test_report_view.py` | The Report view: splitting a report into sections, the status of a section, the cards, the contents box |
| `test_formats.py` | The Format picker and the investor one-pager: what it holds, what it leaves out, and its downloads |
| `test_slides.py` | The pitch deck: which slides, in which order, the PowerPoint file reopened and checked, and the page |
| `test_snapshot_tabs.py` | The Snapshot's tabs: their order, what each one holds and leaves out, the sources line, and what an empty tab says |
| `test_snapshot.py` | The Snapshot view: which figures are kept with a report, the competitor rows, the chart's bars, and the page |
| `test_views.py` | The sidebar of an open conversation: the conversation picker, the links to the views, and conversations that share a title |
| `test_currency.py` | Converting a figure to the country's currency: reading amounts in English and German number styles, the rounding, the wording, a rate service that fails |
| `test_conversation_bar.py` | The bar at the top of the chat: its title, the number of questions, and the two buttons that leave it |
| `test_account_settings.py` | Settings kept per account, the greeting by name, signing out, and that the next person on the same browser gets nothing from the one before |
| `test_usage.py` | Token usage and cost: a chat answer, a report across its review pause, a cancelled report, a repeated call, the background call, a call with no reported cost, the wording, the page |
| `test_answer_length.py` | The maximum answer length: the limit reaches the model, a cut-off answer says so, a cut-off step is repeated, reports are never cut, the slider on the page |
| `test_source_check.py` | The source check: a missing link is put back, an answer that has one is left alone, and addresses inside web text are never used |
| `test_styles.py` | The answer styles, checked by what the model is told: in a chat turn, while a report is written, and from the setting on the page; and that every style keeps the facts and their sources |
| `test_picker.py` | The pickers: which question the chips build, and clicking through one on the page |
| `test_app.py` | The page itself, run without a browser: cards, the research view, guide, sidebar, approval form, a stopped run, missing key |
| `test_agent.py` | How the agent is assembled; model fallback |

`test_app.py` uses Streamlit's `AppTest` with a fake agent, so it checks what
the page shows and what a click does. How the page looks was checked by
hand in a browser: the start screen at several window sizes, a full report
through both forms, a refresh while a form was open, reopening earlier
conversations, and the sidebar panels.

## Deployment

Markavi runs on **Google Cloud Run**:
<https://markavi-1037824678664.europe-west1.run.app>. It asks you to
sign in before anything else is shown. Creating an account needs an invite
code, so that a stranger with the link cannot spend the API credit. Ask
the author for the code.

Each account has its own conversations, remembered profile and settings.

### How it is set up

| Part | Setting |
|---|---|
| Project | Its own Google Cloud project, `markavi-research`, with nothing shared with other apps |
| Service | Cloud Run `markavi` in `europe-west1`: 1 CPU, 1 GiB, at most 1 running copy, shuts down when unused, session affinity for Streamlit's connection |
| Image | Built from the `Dockerfile` and kept in Artifact Registry. It holds only the app: no keys, no local data, no tests. It runs as a non-root user |
| Keys | `OPENROUTER_API_KEY`, `TAVILY_API_KEY` and `APP_PASSWORD` are in Secret Manager and passed in as environment variables. They are never in the image or the repository |
| Saved data | A private Cloud Storage bucket mounted at `/mnt/data` (`DATA_DIR`) |
| Identity | The app runs as its own service account, which can read only those three secrets and use only that bucket |

### The settings a deployed copy uses

All are empty on your own computer, where nothing changes.

| Setting | What it does |
|---|---|
| `APP_PASSWORD` | Turns accounts on: the sign-in screen comes before the app, and this value is the invite code needed to create an account |
| `SMTP_USER`, `SMTP_PASSWORD`, `APP_URL` | Switch on the "Forgot password?" link: the address email is sent from, the app password of that mail account, and the public address of the app for the link. Gmail is the default mail server; `SMTP_HOST` and `SMTP_PORT` change it |
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

Each deploy restarts the service, so visitors sign in again.
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
│   ├── research.py          the three views: Snapshot, Ask, Report, and live progress
│   ├── approvals.py         the two approval forms
│   ├── sidebar.py           conversations, memory, settings, help
│   ├── sign_in.py           the sign-in screen: sign in, create an account, change or reset a password
│   ├── account_badge.py     the round badge at the top right: who is signed in, sign out
│   ├── assistant.py         the assistant: a floating chat at the bottom right
│   └── runtime.py           creates the agent once
├── agent/
│   ├── agent.py             builds the chat agent and its middleware
│   ├── prompts.py           the system prompt
│   ├── side_assistant.py    the assistant's one model call, without tools
│   ├── tools.py             the single-question tools
│   ├── memory.py            checkpointer, store, user profile, saved settings
│   ├── accounts.py          user accounts: creating one, signing in, password and email
│   ├── mailer.py            the email with a link for a forgotten password
│   ├── memory_tools.py      remember and forget tools
│   ├── approval.py          the two approval points
│   ├── guards.py            input check and plain-language errors
│   ├── styles.py            the answer styles: formal, friendly, concise
│   ├── source_check.py      puts back the link to a source if an answer left it out
│   ├── answer_length.py     the limit on the length of a chat answer
│   ├── usage.py             token usage and cost of the model calls
│   ├── currency.py          a figure in the country's own currency, beside the original
│   ├── session.py           conversations, questions and answers, for any interface
│   ├── citations.py         numbered citations and the source list
│   ├── pdf_export.py        a report as a PDF file
│   ├── pptx_export.py       pitch deck slides as a PowerPoint file
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
│   │   ├── snapshot.py      a report's key figures, kept as separate values
│   │   ├── formats.py       other layouts of a report: one-pager and slides
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

- Signing in lasts for one browser session. A refresh of the page signs
  you out.
- An account cannot be deleted from the app.
- An email address is not verified. A mistyped one means the link for a
  forgotten password never arrives; it can be corrected on the sign-in
  page by someone who still knows the password.
- An account made before email was added has no address until its owner
  adds one, and cannot reset a forgotten password until then.
- Changing a password does not sign out other browsers where the account
  is open; they stay in until closed or refreshed.
- Email sent from a personal mail account can land in the spam folder.
- Email addresses are personal data. They are stored with the accounts in
  the bucket, readable by the author of the app.
- Everyone who has the invite code can create any number of accounts, and
  all accounts spend the same API credit. There is no limit per account.
- The author of the app, who can read the bucket, can read every
  account's conversations. They are separated from each other, not
  encrypted.
- Wrong tries are counted per username, so someone who knows a username
  can make its owner wait a minute by guessing five times.
- The first visit after a quiet period takes several seconds, while the
  service starts.
- A deploy, or the service shutting down while idle, signs everyone out.
- If the service stops in the middle of an answer, that answer is lost.

**The three views and the converted figures**

- A report written before the Snapshot view existed has no saved figures,
  so it has no Snapshot. The figures cannot be rebuilt afterwards.
- A Snapshot saved before all four parts of the SWOT were kept shows only
  the parts it has, usually the opportunities alone.
- There is no tab about customers: the report does no customer research.
- The Snapshot shows what the research found, without correcting it. A
  competitor matched to the wrong company, or a price for the wrong
  product, stands out more there than in the report text.
- Figure labels are the source's own wording and can be long sentences.
  Values are copied as written, also in another language.
- The status on a report card is a count of words and source numbers in
  the section. It says nothing about whether the section is right.
- A converted amount is a number no source published. It uses the latest
  exchange rate, also for a figure about another year, so it is a rough
  guide. Ranges and texts with several numbers are not converted. About
  thirty countries have a currency in the table.
- The converted amount is on the Snapshot, the one-pager and the slides.
  The full report text and its downloads keep the original figures alone.
- The one-pager and the slides repeat what the research found, mistakes
  included, and are not rewritten for an investor: the wording is the
  report's own. A slide line longer than 180 characters is cut.
- The slides have a fixed layout and order. Very long reports can still
  make a crowded slide; the PowerPoint file can be edited afterwards.
- The three suggestions under the chat are the same for every
  conversation.
- The heading font is fetched from Google Fonts by the visitor's browser.

**The assistant**

- Its chat is kept in the browser session only. It is gone after a
  refresh, after signing out, or when the tab is closed.
- It has no web search, so it cannot check or add to a report, and it
  repeats a mistake that is in the report.
- A report longer than 24,000 characters is cut before it is sent, and
  only the last ten messages of a chat are sent with a question.
- It is told not to state figures from memory. That is an instruction to
  the model, not a check in code.

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
- Without an invite code set there is one user: everything is stored
  under one profile, and anyone who opens the app sees the same
  conversations.
- Conversations are never shortened, so a very long one costs more per
  turn.
- The address check for the page reader does not defend against a domain
  whose address changes between the check and the download.
- The prompt rule against injected instructions reduces that risk; it does
  not remove it.

## What I would improve

1. Switch on tracing with LangSmith.
2. Let a person delete their account, and verify email addresses.
3. Measure report quality with an evaluation set, so changes can be judged
   by numbers and not by reading reports.
4. Read prices from pages that need JavaScript, with a headless browser.
5. Add a second model provider key to remove the OpenRouter dependency.
6. Give the single-question path the same competitor verification as the
   workflow.
7. Keep a person signed in across a refresh, with a signed cookie.
8. Summarise long conversations to control cost.
