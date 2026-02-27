"""
Gemini Navigator — FastAPI Server
Exposes the vision agent via REST + Server-Sent Events.
"""

import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import run_agent

app = FastAPI(title="Gemini Navigator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    goal: str
    start_url: str = "https://www.google.com"


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-2.0-flash-exp"}


@app.post("/run")
async def run(req: RunRequest):
    """Stream agent progress as Server-Sent Events."""

    async def event_stream():
        async for event in run_agent(req.goal, req.start_url):
            # Omit screenshot from SSE to keep payload small; UI polls /screenshot separately
            payload = {k: v for k, v in event.items() if k != "screenshot"}
            yield f"data: {json.dumps(payload)}\n\n"
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/run/full")
async def run_full(req: RunRequest):
    """Run agent and return all steps including screenshots (for demo/testing)."""
    steps = []
    async for event in run_agent(req.goal, req.start_url):
        steps.append(event)
    return {"goal": req.goal, "steps": steps, "total_steps": len(steps)}


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=open("static/index.html").read() if os.path.exists("static/index.html") else INLINE_UI)


INLINE_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gemini Navigator — AI Web Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f172a; color: #f1f5f9; min-height: 100vh; }
  header { background: #1e293b; padding: 1rem 2rem; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 1rem; }
  header h1 { font-size: 1.4rem; font-weight: 700; }
  header span { background: #6366f1; color: white; font-size: 0.7rem; padding: 2px 8px; border-radius: 999px; }
  main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
  h2 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
  input, textarea { width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.75rem; color: #f1f5f9; font-size: 0.95rem; margin-bottom: 0.75rem; }
  input:focus, textarea:focus { outline: none; border-color: #6366f1; }
  button { background: #6366f1; color: white; border: none; border-radius: 8px; padding: 0.75rem 1.5rem; font-size: 0.95rem; font-weight: 600; cursor: pointer; width: 100%; transition: background 0.2s; }
  button:hover { background: #4f46e5; }
  button:disabled { background: #334155; cursor: not-allowed; }
  #log { background: #0f172a; border-radius: 8px; padding: 1rem; font-family: monospace; font-size: 0.8rem; height: 300px; overflow-y: auto; border: 1px solid #334155; }
  .step { margin-bottom: 0.5rem; padding: 0.4rem 0.6rem; border-radius: 6px; background: #1e293b; }
  .step.done { background: #14532d; }
  .step.error { background: #7f1d1d; }
  #screenshot { width: 100%; border-radius: 8px; border: 1px solid #334155; min-height: 200px; background: #0f172a; display: flex; align-items: center; justify-content: center; color: #475569; }
  #screenshot img { width: 100%; border-radius: 8px; }
  .badge { display: inline-block; background: #6366f1; color: white; font-size: 0.7rem; padding: 1px 6px; border-radius: 4px; margin-right: 4px; }
</style>
</head>
<body>
<header>
  <h1>Gemini Navigator</h1>
  <span>Powered by Gemini 2.0 Flash</span>
</header>
<main>
  <div>
    <div class="card">
      <h2>Run Agent</h2>
      <input id="url" type="text" placeholder="Start URL (e.g. https://google.com)" value="https://www.google.com">
      <textarea id="goal" rows="3" placeholder="Goal: e.g. Search for 'latest AI news' and summarize the first result"></textarea>
      <button id="runBtn" onclick="runAgent()">Launch Agent</button>
    </div>
    <div class="card" style="margin-top:1.5rem">
      <h2>Agent Log</h2>
      <div id="log"><div style="color:#475569">Agent output will appear here...</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Live Browser View</h2>
    <div id="screenshot"><span>No screenshot yet</span></div>
  </div>
</main>
<script>
async function runAgent() {
  const goal = document.getElementById('goal').value.trim();
  const url = document.getElementById('url').value.trim() || 'https://www.google.com';
  if (!goal) { alert('Please enter a goal'); return; }

  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  btn.textContent = 'Running...';
  document.getElementById('log').innerHTML = '';

  try {
    const res = await fetch('/run/full', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({goal, start_url: url})
    });
    const data = await res.json();

    for (const step of data.steps) {
      const div = document.createElement('div');
      div.className = 'step' + (step.action?.action === 'done' ? ' done' : '') + (step.error ? ' error' : '');
      div.innerHTML = step.error
        ? `<span class="badge">ERR</span>${step.error}`
        : `<span class="badge">S${step.step}</span><b>${step.action?.action}</b> — ${step.result}`;
      document.getElementById('log').appendChild(div);

      if (step.screenshot) {
        document.getElementById('screenshot').innerHTML =
          `<img src="data:image/jpeg;base64,${step.screenshot}" alt="Step ${step.step}">`;
      }
    }
  } catch(e) {
    document.getElementById('log').innerHTML = `<div class="step error">Error: ${e.message}</div>`;
  }

  btn.disabled = false;
  btn.textContent = 'Launch Agent';
}
</script>
</body>
</html>"""
