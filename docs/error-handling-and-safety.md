# Error handling and safety

[← Back to the README](../README.md)

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
