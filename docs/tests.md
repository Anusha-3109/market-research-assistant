# Tests

[← Back to the README](../README.md)

```bash
pytest
```

1040 tests, none of which use the internet or cost anything: outside
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
| `test_language.py` | The language switch: both word lists are complete, the choice is saved with the account, and the account menu follows it |
| `test_language_frame.py` | German in the sidebar, the settings, the Snapshot and the assistant panel; settings keep their saved values |
| `test_language_views.py` | German in the Ask and Report views; a report format keeps its value |
| `test_language_agent.py` | What the models are told with German chosen, a report's fixed wording in German, and the German one-pager and slides |
| `test_tracing.py` | Tracing: on only with a key, a project per copy, what a trace is labelled with, and that tests never trace |
| `test_pages.py` | The page links, and How it works in the Admin page's Documentation tab, also in German |
| `test_usage_log.py` | The usage log, its figures per day, what the app writes to it, and the Dashboard page |
| `test_admin.py` | The Admin page: app-wide settings, the system prompt, the tool switches, and who may open it |
| `test_theme.py` | Light / Dark on the Admin page, for every account |
| `test_feedback.py` | Rating an answer: saving, changing and taking back a rating, the thumbs in the chat and the Report view, the reasons and comment after a 👎, German, and the Dashboard's Helpful card |
| `test_feedback_tips.py` | Learning from ratings: which reasons become tips, the last-ten window, each account apart, and that a typed comment never reaches the prompt |
| `test_feedback_admin.py` | The Admin page's Feedback tab: its figures, the settings compared, the latest 👎 shown as text, and the Learn from feedback switch |
| `test_trace_feedback.py` | Ratings sent to LangSmith: the run id given to each run, one rating per trace, nothing sent with tracing off, a failure kept from the user |
| `test_language_start.py` | German on the start screen, pickers, guide, approval forms and sign-in; German country names |
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
