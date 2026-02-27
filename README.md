# Gemini Navigator

**Universal web navigation agent powered by Gemini 2.0 Flash multimodal vision.**

No DOM access. No browser extensions. Pure vision → reasoning → action loop.

Built for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/) — UI Navigator track.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│              (FastAPI + HTML/JS — Cloud Run)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │  goal + start_url
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop (Python)                       │
│                                                             │
│  ┌──────────┐    screenshot    ┌─────────────────────────┐  │
│  │Playwright│ ──────────────► │  Gemini 2.0 Flash       │  │
│  │ Browser  │                 │  (vision + reasoning)   │  │
│  │(headless)│ ◄────────────── │                         │  │
│  └──────────┘    next action  └─────────────────────────┘  │
│       │                                                      │
│       │  click / type / scroll / navigate                   │
│       ▼                                                      │
│  ┌──────────┐                                               │
│  │  Web     │  Any website — no DOM access needed           │
│  │  Page    │                                               │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Google Cloud Infrastructure                     │
│  • Cloud Run — containerized agent hosting                   │
│  • Artifact Registry — Docker image storage                  │
│  • Cloud Storage — screenshot artifacts                      │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

1. **User submits a goal** (e.g. "Search for latest AI news and summarize the top result")
2. **Agent takes a screenshot** of the current browser state via Playwright (headless Chromium)
3. **Screenshot → Gemini 2.0 Flash** — the model sees the page visually and decides the next action
4. **Action is executed**: click at coordinates, type text, scroll, navigate to URL
5. **Loop repeats** until goal is achieved or max steps reached
6. **Results streamed** back to the UI with screenshots at each step

No DOM parsing. No CSS selectors. No brittle XPaths. Just vision.

---

## Setup

### Prerequisites
- Python 3.11+
- `uv` package manager
- Google Gemini API key ([get one here](https://aistudio.google.com/))

### Local development

```bash
git clone https://github.com/mgnlia/gemini-navigator
cd gemini-navigator

# Install deps
uv sync

# Install Playwright browser
uv run playwright install chromium

# Set env vars
echo "GEMINI_API_KEY=your_key_here" > .env

# Run the server
uv run uvicorn src.main:app --reload --port 8080
```

Open http://localhost:8080

### Deploy to Google Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT/gemini-navigator

# Deploy
gcloud run deploy gemini-navigator \
  --image gcr.io/YOUR_PROJECT/gemini-navigator \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key_here \
  --memory 2Gi \
  --cpu 2
```

---

## API Reference

### `POST /run` — Streaming (SSE)
```json
{"goal": "Search for AI news", "start_url": "https://google.com"}
```
Returns Server-Sent Events with step-by-step progress.

### `POST /run/full` — Full response with screenshots
```json
{"goal": "Find the price of iPhone 16", "start_url": "https://apple.com"}
```
Returns all steps including base64 screenshots.

### `GET /health`
Returns `{"status": "ok", "model": "gemini-2.0-flash-exp"}`

---

## Example Goals

- `"Search for 'Gemini 2.0' on Google and tell me the top 3 results"`
- `"Go to Wikipedia and find the population of Tokyo"`
- `"Navigate to Hacker News and list the top 5 headlines"`
- `"Go to GitHub trending and find the most starred Python repo today"`

---

## Tech Stack

| Component | Technology |
|---|---|
| Vision Model | Gemini 2.0 Flash (`gemini-2.0-flash-exp`) |
| Browser Automation | Playwright (headless Chromium) |
| API Server | FastAPI + Uvicorn |
| Hosting | Google Cloud Run |
| Container | Docker |
| Package Manager | uv |

---

## Hackathon

Built for the **Gemini Live Agent Challenge** by Google — UI Navigator track.
Prize pool: $80,000 | Deadline: March 16, 2026
