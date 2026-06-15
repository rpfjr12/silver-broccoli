# youtube_full_pipeline.py
# FULL AUTOMATION — Trend Scraper + Viral Script + Audio + Thumbnail + Video
# Uses GitHub Models (FREE)

import os
import datetime
import feedparser
import requests
from pathlib import Path
from slugify import slugify
from gtts import gTTS
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
import subprocess
import textwrap
import re

BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# -------------------------------
# FREE GITHUB MODELS CLIENT
# -------------------------------
client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.environ["GITHUB_TOKEN"],
)

def call_llm(prompt, model="openai/gpt-4o-mini", temp=0.7, max_tokens=2000):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content

# -------------------------------
# TREND SCRAPERS
# -------------------------------

def scrape_google_trends():
    url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:10]]

def scrape_youtube_trending():
    url = "https://www.youtube.com/feed/trending"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    titles = re.findall(r'"title":{"runs":

\[{"text":"(.*?)"}', r.text)
    return titles[:10]

def scrape_reddit_hot():
    url = "https://www.reddit.com/r/all/hot.json?limit=10"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    data = r.json()
    return [p["data"]["title"] for p in data["data"]["children"]]

# -------------------------------
# VIRAL TOPIC SELECTION
# -------------------------------

def pick_best_topic():
    print("[*] Scraping trending topics...")

    google = scrape_google_trends()
    youtube = scrape_youtube_trending()
    reddit = scrape_reddit_hot()

    combined = google + youtube + reddit
    combined = list(dict.fromkeys(combined))  # dedupe

    print(f"[*] Found {len(combined)} raw trending topics.")

    scoring_prompt = f"""
You are a YouTube virality expert.
Score each topic below from 1-10 for viral potential on a faceless channel.

Return ONLY this format:
score | topic

Topics:
{chr(10).join(combined)}
"""

    scored = call_llm(scoring_prompt, temp=0.4, max_tokens=800)

    best_score = -1
    best_topic = None

    for line in scored.splitlines():
        m = re.match(r"(\d+)\s*\|\s*(.+)", line)
        if m:
            score = int(m.group(1))
            topic = m.group(2).strip()
            if score > best_score:
                best_score = score
                best_topic = topic

    if not best_topic:
        best_topic = "Mind-blowing psychology facts"

    print(f"[*] Selected viral topic: {best_topic}")
    return best_topic

# -------------------------------
# MAIN TOPIC LOGIC
# -------------------------------

TOPIC = os.environ.get("TOPIC", "").strip()

if not TOPIC:
    TOPIC = pick_best_topic()

print(f"[*] Using topic: {TOPIC}")

# -------------------------------
# VIRAL SCRIPT GENERATION
# -------------------------------

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
- Include 3 explicit "retention prompts".
- End with a clear payoff and a call-to-action.

CHAPTERS:
5 timestamps with short labels.
"""

print("[*] Generating viral script...")
full_text = call_llm(prompt, temp=0.8, max_tokens=2500)

def extract(label):
    marker = f"{label}:\n"
    if marker not in full_text:
        return ""
    start = full_text.index(marker) + len(marker)
    next_labels = ["TITLE:\n","DESCRIPTION:\n","THUMBNAIL_TEXT:\n","SCRIPT:\n","CHAPTERS:\n"]
    end = len(full_text)
    for nl in next_labels:
        if nl == marker: continue
        idx = full_text.find(nl, start)
        if idx != -1:
            end = min(end, idx)
    return full_text[start:end].strip()

title = extract("TITLE")
description = extract("DESCRIPTION")
thumbnail_text = extract("THUMBNAIL_TEXT")
script = extract("SCRIPT")
chapters = extract("CHAPTERS")

now = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
slug = slugify(TOPIC)[:60]
folder = OUT / f"{now}_{slug}"
folder.mkdir(exist_ok=True)

(folder / "title.txt").write_text(title)
(folder / "description.txt").write_text(description)
(script_path := folder / "script.md").write_text(
    f"# {title}\n\n## Description\n{description}\n\n## Script\n\n{script}\n\n## Chapters\n{chapters}"
)

print(f"[*] Saved script to {script_path}")

# -------------------------------
# VOICEOVER
# -------------------------------

print("[*] Generating voiceover...")
tts = gTTS(script, lang="en")
audio_path = folder / "voiceover.mp3"
tts.save(str(audio_path))

# -------------------------------
# THUMBNAIL
# -------------------------------

print("[*] Generating thumbnail...")
thumb_path = folder / "thumbnail.png"
img = Image.new("RGB", (1280, 720), color=(18,18,18))
draw = ImageDraw.Draw(img)

lines = [l.strip() for l in thumbnail_text.splitlines() if l.strip()]
if not lines:
    lines = textwrap.wrap(title, width=18)[:2]

try:
    font_large = ImageFont.truetype("DejaVuSans-Bold.ttf", 88)
    font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
except:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

draw.rectangle([(40, 40), (1240, 680)], fill=(28,28,28))
y = 120
for i, line in enumerate(lines[:2]):
    f = font_large if i == 0 else font_small
    w, h = draw.textsize(line, font=f)
    x = (1280 - w) // 2
    draw.text((x, y), line, font=f, fill=(255, 230, 0))
    y += h + 10

tag = "silver-broccoli"
tw, th = draw.textsize(tag, font=font_small)
draw.rectangle([(40, 680-th-20), (40+tw+20, 680)], fill=(255,255,255))
draw.text((50, 680-th-10), tag, font=font_small, fill=(0,0,0))

img.save(thumb_path)

# -------------------------------
# VIDEO
# -------------------------------

print("[*] Generating video...")
video_path = folder / "final_video.mp4"

subprocess.run([
    "ffmpeg",
    "-y",
    "-loop", "1",
    "-i", str(thumb_path),
    "-i", str(audio_path),
    "-c:v", "libx264",
    "-tune", "stillimage",
    "-c:a", "aac",
    "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-shortest",
    str(video_path),
], check=True)

print(f"[*] Final video: {video_path}")
print("[*] DONE — Full automation complete.")
