# youtube_full_pipeline.py
# FULL AUTOMATION — Trend Scraper + Viral Script + Audio + Thumbnail + Video (Batch Mode)
# Uses GitHub Models (FREE)

import os
import sys
import time
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
from requests.exceptions import RequestException

BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

NUM_VIDEOS = int(os.environ.get("NUM_VIDEOS", "3"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("[!] Missing GITHUB_TOKEN environment variable. Exiting.")
    sys.exit(1)

# -------------------------------
# FREE GITHUB MODELS CLIENT
# -------------------------------
client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=GITHUB_TOKEN,
)

def call_llm(prompt, model="openai/gpt-4o-mini", temp=0.7, max_tokens=2000):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temp,
            max_tokens=max_tokens,
        )
        if not getattr(resp, "choices", None):
            return ""
        return resp.choices[0].message.content or ""
    except Exception:
        return ""

# -------------------------------
# HTTP helper with retries
# -------------------------------
def http_get_with_retries(url, headers=None, timeout=10, retries=3, backoff=1.5):
    headers = headers or {"User-Agent": "Mozilla/5.0 (compatible; silver-broccoli/1.0)"}
    for attempt in range(1, retries + 1):
        try:
            return requests.get(url, headers=headers, timeout=timeout)
        except RequestException:
            if attempt < retries:
                time.sleep(backoff ** attempt)
    return None

# -------------------------------
# TREND SCRAPERS
# -------------------------------
def scrape_google_trends():
    try:
        feed = feedparser.parse("https://trends.google.com/trends/trendingsearches/daily/rss?geo=US")
        return [e.title for e in feed.entries[:10]]
    except Exception:
        return []

def scrape_youtube_trending():
    try:
        r = http_get_with_retries("https://www.youtube.com/feed/trending")
        if not r or r.status_code != 200:
            return []
        titles = re.findall(r'"text":"(.*?)"', r.text)
        return [t for t in titles if 5 < len(t) < 120][:20]
    except Exception:
        return []

def scrape_reddit_hot():
    try:
        r = http_get_with_retries("https://old.reddit.com/r/all/hot.json?limit=20")
        if not r or r.status_code != 200:
            return []
        data = r.json()
        posts = data.get("data", {}).get("children", [])
        out = []
        for p in posts:
            t = p.get("data", {}).get("title", "")
            if 5 < len(t) < 200:
                out.append(t)
        return out[:20]
    except Exception:
        return []

# -------------------------------
# VIRAL TOPIC SELECTION
# -------------------------------
def pick_best_topic():
    print("[*] Scraping trending topics...")

    google = scrape_google_trends()
    youtube = scrape_youtube_trending()
    reddit = scrape_reddit_hot()

    combined = google + youtube + reddit
    combined = [c.strip() for c in combined if c and len(c.strip()) > 5]

    banned = {
        "Try searching to get started",
        "Trending", "Shorts", "Home", "Explore",
        "Subscriptions", "Library", "History",
        "Sign in", "Music", "Gaming", "News"
    }
    combined = [c for c in combined if c not in banned]

    if not combined:
        print("[!] No valid trending topics found. Using fallback.")
        return "Mind-blowing psychology facts"

    combined = list(dict.fromkeys(combined))

    scoring_prompt = f"""
Score each topic 1–10 for viral potential on a faceless YouTube channel.

Return ONLY:
score | topic

Topics:
{chr(10).join(combined)}
"""

    scored = call_llm(scoring_prompt, temp=0.4, max_tokens=800)
    if not scored:
        return combined[0]

    best_score = -1
    best_topic = combined[0]

    for line in scored.splitlines():
        m = re.match(r"(\d+)\s*\|\s*(.+)", line)
        if m:
            score = int(m.group(1))
            topic = m.group(2).strip()
            if score > best_score:
                best_score = score
                best_topic = topic

    print(f"[*] Selected viral topic: {best_topic}")
    return best_topic

# -------------------------------
# PIPELINE FOR ONE TOPIC
# -------------------------------
def run_pipeline_for_topic(TOPIC):
    print(f"[*] Starting pipeline for topic: {TOPIC}")

    prompt = f"""
You are a top YouTube writer. For the topic "{TOPIC}", produce:

TITLE:
DESCRIPTION:
THUMBNAIL_TEXT:
SCRIPT:
CHAPTERS:
"""

    full_text = call_llm(prompt, temp=0.8, max_tokens=2500)
    if not full_text:
        return False

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

    title = extract("TITLE") or TOPIC
    description = extract("DESCRIPTION")
    thumbnail_text = extract("THUMBNAIL_TEXT")
    script = extract("SCRIPT")
    chapters = extract("CHAPTERS")

    if not script:
        return False

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    slug = slugify(TOPIC)[:60]
    folder = OUT / f"{now}_{slug}"
    folder.mkdir(exist_ok=True)

    (folder / "title.txt").write_text(title)
    (folder / "description.txt").write_text(description)
    (folder / "script.md").write_text(
        f"# {title}\n\n## Description\n{description}\n\n## Script\n\n{script}\n\n## Chapters\n{chapters}"
    )

    # Voiceover
    try:
        tts = gTTS(script, lang="en")
        audio_path = folder / "voiceover.mp3"
        tts.save(str(audio_path))
    except Exception:
        return False

    # Thumbnail
    try:
        thumb_path = folder / "thumbnail.png"
        img = Image.new("RGB", (1280, 720), color=(18,18,18))
        draw = ImageDraw.Draw(img)

        lines = [l.strip() for l in thumbnail_text.splitlines() if l.strip()] or textwrap.wrap(title, 18)[:2]

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

        img.save(thumb_path)
    except Exception:
        return False

    # Video
    try:
        video_path = folder / "final_video.mp4"
        subprocess.run([
            "ffmpeg", "-y",
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
    except Exception:
        return False

    return True

# -------------------------------
# MAIN
# -------------------------------
def main():
    topics = []
    for _ in range(NUM_VIDEOS):
        topics.append(pick_best_topic())

    successes = 0
    for t in topics:
        if run_pipeline_for_topic(t):
            successes += 1

    print(f"[*] Completed. Successes: {successes}/{len(topics)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
