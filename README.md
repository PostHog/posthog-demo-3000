# HogFlix Demo 3000

This repository allows you to spin up a demo app which has been instrumented with PostHog, and seed PostHog historic data and artifacts to provide a full-featured demo environment showcasing all features.

## Prerequisites

If you choose to run the demo entirely in your browser using GitHub Code Spaces, skip the requirements and go straight to Option 3.

To run the demo locally, you need:

1. **Python 3.9+** — check with `python3 --version`. macOS often includes Python 3 already; if not, install it with [Homebrew](https://brew.sh/) (`brew install python`) or your preferred package manager.
2. **[uv](https://docs.astral.sh/uv/)** — check with `uv --version`. If missing, install with Homebrew (`brew install uv`) or follow the [uv install guide](https://docs.astral.sh/uv/getting-started/installation/).
3. **PostHog credentials** — you'll add these to a `.env` file before running the app (see Option 1).

From the root of this repository, install dependencies:

```bash
make install
```

This uses `uv` to create a project virtual environment and install packages from `pyproject.toml`.

## Running the app

There are three ways to run the app: locally using Python, via Docker, or using GitHub Codespaces.

### Option 1 - Run Locally with Python

**Quick start:**

```bash
make env          # creates .env from .env.example if needed
make install      # install dependencies (first time only)
make run          # verify .env, init DB, seed PostHog, create artifacts, start app
```

Before running `make run`, open `.env` and replace the placeholder values for at least:

- `PH_HOST`
- `PH_PROJECT_KEY`
- `PH_PERSONAL_API_KEY`
- `PH_PROJECT_ID`

If you open a browser and head to `http://127.0.0.1:5000/`, you'll see the HogFlix app running. Use `Ctrl + C` in your terminal to stop the app.

**Manual steps (optional):** If you prefer to run commands individually instead of `make run`:

```bash
make env
make install
make db           # initialize and seed the local SQLite database
make seed         # seed historical events to PostHog
make artifacts    # create demo artifacts in PostHog
uv run python app.py
```

You can also export PostHog variables in your shell instead of using `.env`:

```bash
export PH_HOST='https://<eu or us>.i.posthog.com'
export PH_PROJECT_KEY='<Project API key>'
```

### Option 2 - Run as a Container with Docker

The container hasn't been pushed to a registry yet, so you'll need to build and run it yourself. Make sure you have [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/) installed.

In the root of the repository, first build the container:

```bash
docker build --no-cache --tag posthog-hogflix-demo .
```

Then run the container in detached mode (background):

```bash
docker run -d -p 5000:5000 -e PH_PROJECT_KEY=<Project API key> -e PH_HOST='https://<eu or us>.i.posthog.com' posthog-hogflix-demo
```

You can then access the app on `localhost:5000`.

### Optional: Enable the built-in Chat (LLM) demo

If you set an OpenAI API key, the app will enable a simple chat interface that is instrumented with PostHog LLM Analytics (Generations and Traces). This lets you explore the LLM Analytics features alongside the seeded demo data.

1. Add the following to your `.env`:

```
OPENAI_API_KEY='<OpenAI API key>'
```

2. Ensure your PostHog environment variables are set as above. The chat will appear in the navbar as “Chat” when `OPENAI_API_KEY` is present.

Notes:
- The app will attempt to use the PostHog-instrumented OpenAI client automatically. If unavailable, it will fall back to the standard OpenAI client while still capturing a `$ai_generation` event per message.
- Models: defaults to `gpt-4o-mini`. You can change this in `app.py`.

### Option 3 - Run in GitHub Codespaces

For a seamless setup, you can run the demo entirely in your browser using **GitHub Codespaces**. This avoids needing to manage Python or Docker on your local machine.

To get started:

1. Go to the repository in GitHub.
2. Click on the **Code** button.
3. Navigate to the **Codespaces** tab and click **Create Codespace on Main**.

This will create a virtual environment in your browser where you can run the app and make changes. It may take a few minutes for the environment to configure, but once done, everything will be set up automatically.

On creation, the devcontainer will:

- Install dependencies
- Create `.env` from `.env.example`

Next steps (one-time):
1) Open `.env` and replace the placeholder values for:
   - `PH_HOST`
   - `PH_PROJECT_KEY`
   - `PH_PERSONAL_API_KEY`
   - `PH_PROJECT_ID`
2) Run the app and bootstrap everything in one step:
```bash
make run
```
This will verify your `.env` is updated, initialize the local DB, seed historical data into PostHog, create demo artifacts in your project, and then start the app.

## Seed Historic Usage Data

To generate valuable insights in your PostHog project, you'll need to add some historic event data. The `seed_demo_data.py` script creates pseudo-random data that mimics real usage of the HogFlix app. You'll need the `500_names_and_emails.csv` in your `scripts` folder (see below on how to generate this), and then run:

```bash
make seed DAYS=30 ITER=100
```

The seeding script will read `PH_PROJECT_KEY` and `PH_HOST` from either your environment or your `.env`. You can still pass `-k` and `-p` flags explicitly if you prefer.

Parameters:
- `-d`: Number of previous days to generate (default 30)
- `-i`: Number of iterations (default 100)

After a few minutes, you'll see newly created events and people in your PostHog project.

## Create Demo Artifacts

Once historic data has been generated, you'll need some PostHog artifacts to view as part of the demo. The `create_posthog_artifacts.py` script adds in:

- Actions looking at pageviews and custom events.
- Cohorts based on behavior and user properties.
- Insights using the above actions.
- A Feature Flag for the action mode feature integrated into the app.

You'll need a **Personal API Key** (available in `/settings/user-api-keys` in the PostHog UI) to run this script:

```bash
make artifacts
```
This script now reads `PH_PERSONAL_API_KEY`, `PH_HOST`, and `PH_PROJECT_ID` from your `.env`.
Optional flags (overrides env when provided):
- `-k`: Personal API key
- `-p`: API base URL (e.g. `https://us.posthog.com/api/projects/<project id>`) 
- `--project_id`: Project ID (used to derive API URL when `-p` not provided)

## Recreate the Seed Data

The `500_names_and_emails.csv` file in the `scripts/` folder contains dummy data for 500 users, which includes group (Family) information. If needed, you can recreate this file by running:

```bash
uv run python scripts/generate_fake_names_and_emails.py
```

Then copy the generated file back to the `scripts/` folder to generate more demo data.

## Makefile Shortcuts

Common tasks are wrapped in a `Makefile`:

- `make install`: Install dependencies
- `make env`: Create `.env` from example
- `make check-env`: Verify `.env` placeholders have been replaced
- `make db`: Initialize and seed local DB
- `make run`: Verify env, init DB, seed data, create artifacts, run app
- `make seed`: Seed historical events to PostHog (reads `PH_*` from `.env`; flags optional)
- `make artifacts`: Create PostHog demo artifacts (reads `PH_*` from `.env`; idempotent)
- `make test`: Run tests

---

Now you're ready to demo the full power of PostHog with **HogFlix Demo 3000**!
