# How to use Markavi

[← Back to the README](../README.md)

## The start screen

Nine example cards float around the headline. Click one to open its picker,
or type your own question in the box at the bottom.

## The pickers

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

## Ask for a report

Type, or click "Write a report":

```
I want to launch a healthy meal delivery business in Germany.
Give me a market research report.
```

The agent needs a product and one country. If you name no country and none
is saved for you, it asks. While it works, a progress box lists each step
as it finishes.

## Review the competitors

Before the detailed research, the agent stops and shows a form:

- a tick box for each competitor it found, with its website;
- companies it verified but left out, which you can tick to include;
- an "Add a company" field for any it missed;
- the companies it dropped, with the reason for each;
- **Continue** and **Cancel report** buttons.

Untick what does not belong, add what is missing, and continue. Cancelling
stops the report with no further research.

## The three views of a conversation

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

## Report formats

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

## Download and save

| Button | What it does |
|---|---|
| Markdown | Sends the answer to your own computer as a Markdown file |
| PDF | The same as a PDF, with working links and tables |
| Save to reports folder | Asks the agent to save a report in the app's `reports/` folder |

Saving shows a form on the page with an editable title, and
**Save** and **Don't save** buttons. Nothing is written until you press
Save. The competitor review form appears in the same place.

## Ask follow-up questions

```
Go deeper on pricing for the cheapest competitor you found.
```

Type it in the box at the bottom of the Ask view, or click one of the
suggestions. It is added to the chat under the earlier questions, and the
report stays one click away in the sidebar.

## The assistant

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

## Conversations

Open the sidebar with the arrow at the top left.

- **New conversation** starts a fresh one.
- Earlier conversations are listed by their first question. Click one to
  reopen it.

Conversations are saved in `data/memory.db`. The conversation id is in the
page address, so refreshing the page, or closing and reopening it, shows
the same chat. A form that was waiting for your decision is still there.

## Memory

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

## Pages, settings and help

The links at the top of the sidebar open the pages:

| Page | What it shows |
|---|---|
| Research | The app itself: the start screen and your conversations |
| Dashboard | Requests, answered share, typical wait, tokens and cost, with a chart per day for each, the tool calls, the guard and errors. A range of 7, 30 or 90 days, or a year. Each account sees its own use |
| Admin | Developer settings for the whole app, the system prompt, a switch for each tool, and what the app cost. Its **Documentation** tab explains how it works: the flow from question to answer as a Mermaid chart, the tools and their fallbacks, the report workflow, where the data comes from, and the safety checks. Only admins see it: everyone on your own computer, and the accounts named in `ADMIN_USERNAMES` on a deployed copy |

At the top right, **EN / DE** changes the language and **Light / Dark** the
look. Both are kept with your account.

On a deployed copy, the round badge with your initial is at the bottom of
the sidebar, under Help. Click it to see who is signed in and to **Sign out**.

The settings below are on the **Admin** page and apply to every account.
Help is in the sidebar.

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

## Terminal chat (for development)

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
