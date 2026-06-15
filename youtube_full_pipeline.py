# youtube_full_pipeline.py
# FULL AUTOMATION — Trend Scraper + Viral Script + Audio + Thumbnail + Video (Batch Mode)
# GitHub Actions friendly + hardened pipeline

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

# -------------------------------
# CONFIG
# -------------------------------
BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

NUM_VIDEOS = int(os.environ.get("NUM_VIDEOS", "3"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("[FATAL] Missing GITHUB_TOKEN")
    sys.exit(1)

# -------------------------------
# GitHub Models Client
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
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return ""

# -------------------------------
# HTTP helper
# -------------------------------
def http_get(url, timeout=10, retries=3):
    headers = {"User-Agent": "Mozilla/5.0 (GitHub Actions Bot)"}
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
        except RequestException:
            time.sleep(2 ** i)
    return None

# -------------------------------
# TREND SOURCES
# -------------------------------
def scrape_google_trends():
    try:
        feed = feedparser.parse(
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        )
        return [e.title for e in feed.entries[:10]]
    except:
        return []

def scrape_youtube_trending():
    try:
        r = http_get("https://www.youtube.com/feed/trending")
        if not r:
            return []
        titles = re.findall(r'"text":"(.*?)"', r.text)
        return titles[:20]
    except:
        return []

def scrape_reddit_hot():
    try:
        r = http_get("https://www.reddit.com/r/all/hot.json?limit=20")
        if not r:
            return []
        data = r.json()
        return [
            p["data"]["title"]
            for p in data.get("data", {}).get("children", [])
            if "title" in p.get("data", {})
        ]
    except:
        return []

# -------------------------------
# TOPIC SELECTION
# -------------------------------
def pick_best_topic():
    print("[*] Collecting trends...")

    topics = (
        scrape_google_trends()
        + scrape_youtube_trending()
        + scrape_reddit_hot()
    )

    topics = [t.strip() for t in topics if t and len(t.strip()) > 5]

    blacklist = {
        "Trending", "Shorts", "Explore", "Subscriptions",
        "Library", "History", "Sign in"
    }

    topics = list(dict.fromkeys([t for t in topics if t not in blacklist]))

    if not topics:
        print("[WARN] No trends found, using fallback")
        return "Mind blowing psychology facts"

    prompt = f"""
Rate each topic 1-10 for viral YouTube potential.

Return format:
score | topic

Topics:
{chr(10).join(topics)}
"""

    scored = call_llm(prompt, temp=0.4, max_tokens=800)

    best_score = -1
    best_topic = topics[0]

    for line in scored.splitlines():
        m = re.match(r"(\d+)\s*\|\s*(.+)", line)
        if m:
            score = int(m.group(1))
            topic = m.group(2).strip()
            if score > best_score:
                best_score = score
                best_topic = topic

    print(f"[OK] Selected topic: {best_topic}")
    return best_topic

# -------------------------------
# PIPELINE
# -------------------------------
def parse_section(text, label):
    pattern = rf"{label}:\s*(.*?)(?=\n[A-Z]+:|$)"
    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else ""

def run_pipeline(topic):
    print(f"\n[*] Running pipeline: {topic}")

    prompt = f"""
You are a viral YouTube script generator.

Topic: {topic}

Return EXACT format:

TITLE:
DESCRIPTION:
THUMBNAIL_TEXT:
SCRIPT:
CHAPTERS:
"""

    result = call_llm(prompt, temp=0.8, max_tokens=2500)
    if not result:
        return False

    title = parse_section(result, "TITLE") or topic
    description = parse_section(result, "DESCRIPTION")
    thumb = parse_section(result, "THUMBNAIL_TEXT")
    script = parse_section(result, "SCRIPT")
    chapters = parse_section(result, "CHAPTERS")

    if not script:
        print("[WARN] No script generated")
        return False

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    folder = OUT / f"{stamp}_{slugify(topic)[:60]}"
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "title.txt").write_text(title, encoding="utf-8")
    (folder / "description.txt").write_text(description, encoding="utf-8")
    (folder / "script.txt").write_text(script, encoding="utf-8")

    # ---------------- AUDIO ----------------
    try:
        audio_file = folder / "voiceover.mp3"
        gTTS(script[:4500], lang="en").save(str(audio_file))
    except Exception as e:
        print(f"[TTS ERROR] {e}")
        return False

    # ---------------- THUMBNAIL ----------------
    try:
        img = Image.new("RGB", (1280, 720), (20, 20, 20))
        draw = ImageDraw.Draw(img)

        text_lines = thumb.split("\n") if thumb else [title]

        try:
            font1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 80)
            font2 = ImageFont.truetype("DejaVuSans-Bold.ttf", 50)
        except:
            font1 = ImageFont.load_default()
            font2 = ImageFont.load_default()

        y = 180
        for i, line in enumerate(text_lines[:2]):
            font = font1 if i == 0 else font2
            w = draw.textlength(line, font=font)
            x = (1280 - w) // 2
            draw.text((x, y), line, fill=(255, 220, 0), font=font)
            y += 120

        thumb_path = folder / "thumbnail.png"
        img.save(thumb_path)
    except Exception as e:
        print(f"[THUMB ERROR] {e}")
        return False

    # ---------------- VIDEO ----------------
    try:
        video_path = folder / "final.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(thumb_path),
            "-i", str(folder / "voiceover.mp3"),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(video_path)
        ], check=True)
    except Exception as e:
        print(f"[FFMPEG ERROR] {e}")
        return False

    print(f"[DONE] {topic}")
    return True

# -------------------------------
# MAIN
# -------------------------------
def main():
    print("=== PIPELINE START ===")

    topics = [pick_best_topic() for _ in range(NUM_VIDEOS)]

    success = 0
    for t in topics:
        if run_pipeline(t):
            success += 1

    print(f"\n=== COMPLETE: {success}/{len(topics)} videos ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
