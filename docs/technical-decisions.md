# Technical decisions

[← Back to the README](../README.md)

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

**Learning from ratings with fixed tips, not with the model.** One way to
learn from feedback is to let a model read the 👎 and their comments and
rewrite the prompt. That was not done: a comment is text from a user, and
whatever reaches the prompt can steer the agent, so a comment like "ignore
your rules" would become an instruction. A rewritten prompt is also hard to
test and costs a model call. Instead, each of the six reasons maps to one
fixed sentence written in advance, and a sentence is added only when its
reason comes up in two or more of the account's last ten ratings. It is
predictable, tested, free, and forgets on its own once the complaints stop.
The comments still matter: the Admin page shows them, so the person who
owns the prompt can act on them for everyone.

The tips are per account, because "too long" from one person says nothing
about another. They come before the answer style in the prompt, so a style
chosen on the Admin page still has the last word.

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
