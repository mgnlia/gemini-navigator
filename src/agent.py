"""
Gemini Navigator — Core Agent Loop
Vision-driven browser automation using Gemini 2.0 Flash multimodal API.
No DOM access. Pure screenshot → vision → action loop.
"""

import asyncio
import base64
import json
import os
import re
from io import BytesIO
from typing import AsyncGenerator

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from playwright.async_api import async_playwright, Page

load_dotenv()

GEMINI_MODEL = "gemini-2.0-flash-exp"
MAX_STEPS = 20
SCREENSHOT_WIDTH = 1280
SCREENSHOT_HEIGHT = 720

SYSTEM_PROMPT = """You are a browser navigation agent. You observe screenshots and decide the next action.

Given a screenshot of the current browser state and a user goal, respond with a JSON action:

Actions available:
- {"action": "navigate", "url": "https://..."} — go to a URL
- {"action": "click", "x": 100, "y": 200} — click at pixel coordinates
- {"action": "type", "text": "hello world"} — type text at current focus
- {"action": "scroll", "direction": "down", "amount": 300} — scroll the page
- {"action": "wait", "ms": 1000} — wait milliseconds
- {"action": "done", "result": "description of what was accomplished"} — goal complete

Rules:
1. Always respond with valid JSON only — no prose, no markdown, no explanation.
2. Coordinates must be within the visible viewport (1280x720).
3. If the goal is achieved, use "done" immediately.
4. If stuck after 3 attempts at the same action, use "done" with partial result.
"""


def screenshot_to_base64(screenshot_bytes: bytes) -> str:
    img = Image.open(BytesIO(screenshot_bytes))
    img = img.resize((SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT))
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode()


async def get_next_action(client: genai.Client, goal: str, screenshot_b64: str, step: int, history: list) -> dict:
    history_text = "\n".join(f"Step {i+1}: {h}" for i, h in enumerate(history[-5:]))
    user_prompt = f"""Goal: {goal}

Step: {step}/{MAX_STEPS}
Recent actions:
{history_text if history_text else "(none yet)"}

Based on the current screenshot, what is the next action to take?
Respond with JSON only."""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/jpeg",
                            data=base64.b64decode(screenshot_b64),
                        )
                    ),
                    types.Part(text=user_prompt),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=256,
        ),
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


async def execute_action(page: Page, action: dict) -> str:
    act = action.get("action")
    if act == "navigate":
        url = action["url"]
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return f"Navigated to {url}"
    elif act == "click":
        x, y = action["x"], action["y"]
        await page.mouse.click(x, y)
        await asyncio.sleep(0.5)
        return f"Clicked at ({x}, {y})"
    elif act == "type":
        text = action["text"]
        await page.keyboard.type(text)
        return f"Typed: {text}"
    elif act == "scroll":
        direction = action.get("direction", "down")
        amount = action.get("amount", 300)
        delta = amount if direction == "down" else -amount
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(0.3)
        return f"Scrolled {direction} {amount}px"
    elif act == "wait":
        ms = action.get("ms", 1000)
        await asyncio.sleep(ms / 1000)
        return f"Waited {ms}ms"
    elif act == "done":
        return f"DONE: {action.get('result', 'Goal completed')}"
    else:
        return f"Unknown action: {act}"


async def run_agent(goal: str, start_url: str = "https://www.google.com") -> AsyncGenerator[dict, None]:
    """
    Run the vision-driven agent loop.
    Yields progress events: {"step": int, "action": dict, "result": str, "screenshot": str}
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield {"error": "GEMINI_API_KEY not set"}
        return

    client = genai.Client(api_key=api_key)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT}
        )
        page = await context.new_page()
        await page.goto(start_url, wait_until="domcontentloaded")

        history = []

        for step in range(1, MAX_STEPS + 1):
            # Take screenshot
            screenshot_bytes = await page.screenshot(type="jpeg", quality=80)
            screenshot_b64 = screenshot_to_base64(screenshot_bytes)

            # Get Gemini's next action
            try:
                action = await get_next_action(client, goal, screenshot_b64, step, history)
            except Exception as e:
                yield {"step": step, "error": f"Gemini error: {e}", "screenshot": screenshot_b64}
                break

            # Execute action
            try:
                result = await execute_action(page, action)
            except Exception as e:
                result = f"Action failed: {e}"

            history.append(f"{action.get('action')} → {result}")

            yield {
                "step": step,
                "action": action,
                "result": result,
                "screenshot": screenshot_b64,
            }

            if action.get("action") == "done":
                break

        await browser.close()
