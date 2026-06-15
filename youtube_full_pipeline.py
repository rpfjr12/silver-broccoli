# youtube_full_pipeline.py
# FREE VERSION — uses GitHub Models instead of OpenAI

import os
import datetime
from pathlib import Path
from slugify import slugify
from gtts import gTTS
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
import subprocess
import textwrap
import re

TOPIC = os.environ.get("TOPIC", "").strip()

BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# -------------------------------
# FREE GITHUB MODELS CLIENT
# -------------------------------
client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.environ["GITHUB_TOKEN"],   # GitHub Actions provides this automatically
)

def call_openai(prompt, model="openai/gpt-4o-mini", temp=0.7, max_tokens=2000):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content

# If no topic provided, generate 3 high-demand topic ideas and pick the top one
if not TOPIC:
    print("[*] No topic provided. Generating high-demand topic ideas...")
    topic_prompt = (
        "You are an expert YouTube strategist. Propose 3 high-demand, high-virality video topics "
        "for a faceless channel about general interest (money, psychology, life hacks, weird facts). "
        "Return as numbered list with 1-line rationale each. Do not include anything else."
    )
    topics_text = call_openai(topic_prompt, temp=0.8, max_tokens=400)
    print("[*] Topic ideas:\n", topics_text)
    m = re.search(r\"1\\.\\s*(.+)\", topics_text)
    if m:
        TOPIC = m.group(1).strip()
    else:
        TOPIC = "Weird facts that blow your mind"

print(f"[*] Using topic: {TOPIC}")

# Viral-optimized prompt
prompt = f"""
You are a top YouTube writer and growth strategist. For the topic: "{TOPIC}" produce the following sections
in this exact labeled format. Be concise, punchy, and optimized for retention and clicks.

TITLE:
A clickable SEO title (<=70 chars) that includes a strong hook word.

DESCRIPTION:
2 short paragraphs (3-4 sentences each) + 3 bullet points with timestamps or highlights.

THUMBNAIL_TEXT:
Two short lines of bold thumbnail text (max 6 words per line). Keep it urgent/curiosity-driven.

SCRIPT:
A full spoken script ~900-1400 words, broken into short paragraphs. Requirements:
- Start with a 3-second hook line (very short, high curiosity).
- Use curiosity loops every 20-40 seconds (tease, then promise payoff).
- Keep sentences short; paragraphs 1-3 lines max.
- Include 3 explicit "retention prompts" (phrases that encourage watching to the end).
- End with a clear payoff and a call-to-action (subscribe/watch next).

Also return a short "CHAPTERS" section: 5 timestamps with short labels that map to script structure.
Return nothing else.
"""

print("[*] Requesting viral-optimized content from GitHub Models...")
full_text = call_openai(prompt, temp=0.8, max_tokens=2500)

# Helper to extract labeled sections
def extract_section(label, text):
    marker = f"{label}:\n"
    if marker not in text:
        return ""
    start = text.index(marker) + len(marker)
    next_labels = ["TITLE:\n","DESCRIPTION:\n","THUMBNAIL_TEXT:\n","SCRIPT:\n","CHAPTERS:\n"]
    end = len(text)
    for nl in next_labels:
        if nl == marker: continue
        idx = text.find(nl, start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end].strip()

title = extract_section("TITLE", full_text)
description = extract_section("DESCRIPTION", full_text)
thumbnail_text = extract_section("THUMBNAIL_TEXT", full_text)
script = extract_section("SCRIPT", full_text)
chapters = extract_section("CHAPTERS", full_text)

now = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
slug = slugify(TOPIC)[:60]
folder = OUT / f"{now}_{slug}"
folder.mkdir(exist_ok=True)

# Save text files
(folder / "title.txt").write_text(title, encoding="utf-8")
(folder / "description.txt").write_text(description, encoding="utf-8")
(script_path := folder / "script.md").write_text(
    f"# {title}\n\n## Description\n{description}\n\n## Script\n\n{script}\n\n## Chapters\n{chapters}",
    encoding="utf-8"
)

print(f"[*] Saved script to {script_path}")

# Voiceover
print("[*] Generating voiceover with gTTS...")
tts = gTTS(script, lang="en")
audio_path
