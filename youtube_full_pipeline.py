# youtube_full_pipeline.py
# FULL AUTOMATION — High-Retention YouTube Video Generator (Batch Mode)
# Trend Scraper + Viral Script + Audio + Thumbnail + Video
# GitHub Actions friendly

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

def call_llm(prompt, model="openai/gpt-4o-mini", temp=0.75, max_tokens=2200):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temp,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
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
        return [t for t in titles if 5 < len(t) < 120][:30]
    except:
        return []

def scrape_reddit_hot():
    try:
        r = http_get("https://www.reddit.com/r/all/hot.json?limit=25")
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
        "Library", "History", "Sign in",
        "Home", "Music", "Gaming", "News",
        "Start watching videos to help us build a feed of videos you'll love.",
        "Try searching to get started",
    }

    topics = [t for t in topics if t not in blacklist]
    topics = list(dict.fromkeys(topics))

    if not topics:
        print("[WARN] No trends found, using fallback")
        return "Mind blowing psychology facts that will change how you see people"

    prompt = f"""
You are a YouTube virality and retention expert.

Rate each topic 1-10 for viral potential on a faceless channel.
Prefer:
- Emotion, conflict, secrets, psychology, money, status, relationships, tech, or shocking facts.
- Topics that can sustain 10+ minutes of storytelling and examples.

Return format ONLY:
score | topic

Topics:
{chr(10).join(topics)}
"""

    scored = call_llm(prompt, temp=0.4, max_tokens=900)

    best_score = -1
    best_topic = topics[0]

    for line in scored.splitlines():
        m = re.match(r"(\d+)\s*\|\s*(.+)", line)
        if m:
            try:
                score = int(m.group(1))
            except:
                continue
            topic = m.group(2).strip()
            if score > best_score:
                best_score = score
                best_topic = topic

    print(f"[OK] Selected topic: {best_topic} (score {best_score})")
    return best_topic

# -------------------------------
# PARSING HELPERS
# -------------------------------
def parse_section(text, label):
    pattern = rf"{label}:\s*(.*?)(?=\n[A-Z_]+:|$)"
    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else ""

# -------------------------------
# PIPELINE FOR ONE VIDEO
# -------------------------------
def run_pipeline(topic):
    print(f"\n[*] Running pipeline: {topic}")

    prompt = f"""
You are a world-class YouTube scriptwriter and growth strategist.

Write for a faceless channel with AI voiceover and simple visuals.

Topic: "{topic}"

Return EXACTLY these sections and labels:

TITLE:
- 1 clickable title (max 70 chars)
- Use a strong hook word (shocking, secret, hidden, insane, etc.)
- Make it specific, not generic clickbait.

DESCRIPTION:
- 2 short paragraphs (3-4 sentences each).
- First paragraph: hook + what they'll learn.
- Second paragraph: social proof + subtle CTA to subscribe.
- Then 3 bullet points with timestamps or key hooks.

THUMBNAIL_TEXT:
- 2 lines, max 4 words per line.
- All caps, ultra bold, curiosity-driven.
- No hashtags, no emojis.

SCRIPT:
- 900–1400 words.
- First 5 seconds: punchy hook that creates an open loop.
- Then a fast promise of value.
- Use simple language, short sentences, and 1–3 line paragraphs.
- Use pattern interrupts every 20–40 seconds (questions, surprising facts, "most people don't know this", etc.).
- Include at least 3 explicit retention prompts like:
  - "Stick with me for a second..."
  - "Don't click away yet..."
  - "And in a moment, I'll show you..."
- Use concrete examples, mini-stories, and vivid imagery.
- End with a satisfying payoff that closes the main loop, then a clear CTA to like + subscribe.

CHAPTERS:
- 5–7 chapters.
- Format: 00:00 - Hook / Big Promise
- Make chapter titles curiosity-driven, not boring.

Return ONLY those labeled sections in that order.
"""

    result = call_llm(prompt, temp=0.85, max_tokens=2600)
    if not result:
        print("[WARN] Empty LLM result")
        return False

    title = parse_section(result, "TITLE") or topic
    description = parse_section(result, "DESCRIPTION")
    thumb = parse_section(result, "THUMBNAIL_TEXT")
    script = parse_section(result, "SCRIPT")
    chapters = parse_section(result, "CHAPTERS")

    if not script or len(script.split()) < 400:
        print("[WARN] Script too short or missing")
        return False

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    folder = OUT / f"{stamp}_{slugify(topic)[:60]}"
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "title.txt").write_text(title, encoding="utf-8")
    (folder / "description.txt").write_text(description, encoding="utf-8")
    (folder / "script.txt").write_text(script, encoding="utf-8")
    (folder / "chapters.txt").write_text(chapters, encoding="utf-8")

    # ---------------- AUDIO ----------------
    try:
        audio_file = folder / "voiceover.mp3"
        # gTTS has length limits; trim if insane
        tts_text = script[:8000]
        gTTS(tts_text, lang="en").save(str(audio_file))
    except Exception as e:
        print(f"[TTS ERROR] {e}")
        return False

    # ---------------- THUMBNAIL ----------------
    try:
        img = Image.new("RGB", (1280, 720), (15, 15, 15))
        draw = ImageDraw.Draw(img)

        if thumb:
            raw_lines = [l.strip() for l in thumb.splitlines() if l.strip()]
        else:
            raw_lines = textwrap.wrap(title.upper(), width=10)[:2]

        lines = raw_lines[:2]

        try:
            font1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 110)
            font2 = ImageFont.truetype("DejaVuSans-Bold.ttf", 80)
        except:
            font1 = ImageFont.load_default()
            font2 = ImageFont.load_default()

        # Background block
        draw.rectangle([(80, 120), (1200, 600)], fill=(25, 25, 25))

        y = 200
        for i, line in enumerate(lines):
            font = font1 if i == 0 else font2
            w = draw.textlength(line, font=font)
            x = (1280 - w) // 2
            draw.text((x, y), line, fill=(255, 230, 0), font=font)
            y += 150

        # Small brand tag
        tag = "SILVER BROCCOLI"
        try:
            tag_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        except:
            tag_font = ImageFont.load_default()
        tw = draw.textlength(tag, font=tag_font)
        draw.rectangle([(80, 640 - 60), (80 + tw + 40, 640)], fill=(255, 255, 255))
        draw.text((100, 640 - 50), tag, fill=(0, 0, 0), font=tag_font)

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
