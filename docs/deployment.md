# Deployment

[← Back to the README](../README.md)

Markavi runs on **Google Cloud Run**:
<https://markavi-1037824678664.europe-west1.run.app>. It asks you to
sign in before anything else is shown. Creating an account needs an invite
code, so that a stranger with the link cannot spend the API credit. Ask
the author for the code.

Each account has its own conversations, remembered profile and settings.

## How it is set up

| Part | Setting |
|---|---|
| Project | Its own Google Cloud project, `markavi-research`, with nothing shared with other apps |
| Service | Cloud Run `markavi` in `europe-west1`: 1 CPU, 1 GiB, at most 1 running copy, shuts down when unused, session affinity for Streamlit's connection |
| Image | Built from the `Dockerfile` and kept in Artifact Registry. It holds only the app: no keys, no local data, no tests. It runs as a non-root user |
| Keys | `OPENROUTER_API_KEY`, `TAVILY_API_KEY` and `APP_PASSWORD` are in Secret Manager and passed in as environment variables. They are never in the image or the repository |
| Saved data | A private Cloud Storage bucket mounted at `/mnt/data` (`DATA_DIR`) |
| Identity | The app runs as its own service account, which can read only those three secrets and use only that bucket |

## The settings a deployed copy uses

All are empty on your own computer, where nothing changes.

| Setting | What it does |
|---|---|
| `APP_PASSWORD` | Turns accounts on: the sign-in screen comes before the app, and this value is the invite code needed to create an account |
| `SMTP_USER`, `SMTP_PASSWORD`, `APP_URL` | Switch on the "Forgot password?" link: the address email is sent from, the app password of that mail account, and the public address of the app for the link. Gmail is the default mail server; `SMTP_HOST` and `SMTP_PORT` change it |
| `DATA_DIR` | The folder that survives restarts. Saved reports are written straight into it. The memory file is handled differently, see below |

## Why the memory file is copied instead of stored in the bucket

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

## Automatic deploys

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

## Run the image yourself

```bash
docker build -t markavi .
```

```bash
docker run -p 8080:8080 -e OPENROUTER_API_KEY=... -e TAVILY_API_KEY=... -e APP_PASSWORD=choose-one markavi
```

Then open <http://localhost:8080>.

## Deploy by hand

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
