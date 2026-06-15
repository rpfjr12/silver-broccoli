# youtube_full_pipeline.py
# FULL AUTOMATION — Robust Trend Scraper + Viral Script + Audio + Thumbnail + Video
# Uses GitHub Models (FREE). Designed to avoid exit code 1 from transient failures.

import os
import sys
import time
import traceback
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

# Basic config
BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

NUM_VIDEOS = int(os.environ.get("NUM_VIDEOS", "1"))  # set to 3 for batch mode
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
        # defensive: ensure structure exists
        if not getattr(resp, "choices", None):
            print("[!] LLM returned no choices.")
            return ""
        content = resp.choices[0].message.content
        if not content:
            print("[!] LLM returned empty content.")
            return ""
        return content
    except Exception as e:
        print("[!] LLM call failed:", e)
        return ""

# -------------------------------
# HTTP helper with retries
# -------------------------------
from requests.exceptions import RequestException

def http_get_with_retries(url, headers=None, timeout=10, retries=3, backoff=1.5):
    headers = headers or {"User-Agent": "Mozilla/5.0 (compatible; silver-broccoli/1.0)"}
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            return r
        except RequestException as e:
            print(f"[*] HTTP request failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff ** attempt)
            else:
                return None

# -------------------------------
# TREND SCRAPERS (robust)
# -------------------------------

def scrape_google_trends():
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        feed = feedparser.parse(url)
        titles = [entry.title for entry in feed.entries[:10]]
        print(f"[*] Google Trends: found {len(titles)} items")
        return titles
    except Exception as e:
        print("[!] Google Trends scrape failed:", e)
        return []

def scrape_youtube_trending():
    try:
        url = "https://www.youtube.com/feed/trending"
        r = http_get_with_retries(url, timeout=10, retries=3)
        if not r:
            print("[*] YouTube trending fetch failed (no response).")
            return []
        if r.status_code != 200:
            print(f"[*] YouTube returned status {r.status_code}; body preview: {r.text[:200]!r}")
            return []
        # match any "text":"..." occurrences (stable-ish)
        titles = re.findall(r'"text":"(.*?)"', r.text)
        clean = [t for t in titles if 5 < len(t) < 120]
        print(f"[*] YouTube trending: found {len(clean)} candidate titles")
        return clean[:10]
    except Exception as e:
        print("[!] YouTube trending scrape failed:", e)
        return []

def scrape_reddit_hot():
    """
    Use old.reddit.com JSON endpoint with retries and safe parsing.
    Returns list of titles (max 10). On failure returns [].
    """
    try:
        url = "https://old.reddit.com/r/all/hot.json?limit=20"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; silver-broccoli/1.0)"}
        r = http_get_with_retries(url, headers=headers, timeout=10, retries=4, backoff=1.5)
        if not r:
            print("[*] Reddit request returned no response after retries.")
            return []
        if r.status_code != 200:
            print(f"[*] Reddit returned status {r.status_code}; body preview: {r.text[:200]!r}")
            return []
        try:
            data = r.json()
        except ValueError:
            print("[*] Reddit response not JSON (maybe HTML or rate-limited). Body preview:", r.text[:400])
            return []
        posts = data.get("data", {}).get("children", [])
        titles = []
        for p in posts:
            t = p.get("data", {}).get("title", "")
            if t and 5 < len(t) < 200:
                titles.append(t)
            if len(titles) >= 10:
                break
        print(f"[*] Reddit hot: found {len(titles)} titles")
        return titles
    except Exception as e:
        print("[!] scrape_reddit_hot unexpected error:", e)
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
    combined = list(dict.fromkeys(combined))  # dedupe while preserving order

    if not combined:
        print("[!] No trending topics found from sources; using fallback.")
        return "Mind-blowing psychology facts"

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
    if not scored:
        print("[*] LLM scoring failed or returned empty; picking first topic as fallback.")
        return combined[0]

    best_score = -1
    best_topic = None

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

    if not best_topic:
        best_topic = combined[0]

    print(f"[*] Selected viral topic: {best_topic} (score {best_score})")
    return best_topic

# -------------------------------
# PIPELINE FOR A SINGLE TOPIC
# -------------------------------

def run_pipeline_for_topic(TOPIC):
    try:
        print(f"[*] Starting pipeline for topic: {TOPIC}")

        # Build prompt
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

        full_text = call_llm(prompt, temp=0.8, max_tokens=2500)
        if not full_text:
            print("[!] LLM returned empty script. Skipping this topic.")
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
        description = extract("DESCRIPTION") or ""
        thumbnail_text = extract("THUMBNAIL_TEXT") or ""
        script = extract("SCRIPT") or ""
        chapters = extract("CHAPTERS") or ""

        if not script:
            print("[!] No script extracted. Skipping this topic.")
            return False

        now = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        slug = slugify(TOPIC)[:60]
        folder = OUT / f"{now}_{slug}"
        folder.mkdir(exist_ok=True)

        (folder / "title.txt").write_text(title, encoding="utf-8")
        (folder / "description.txt").write_text(description, encoding="utf-8")
        (script_path := folder / "script.md").write_text(
            f"# {title}\n\n## Description\n{description}\n\n## Script\n\n{script}\n\n## Chapters\n{chapters}",
            encoding="utf-8"
        )

        print(f"[*] Saved script to {script_path}")

        # Voiceover
        try:
            print("[*] Generating voiceover with gTTS...")
            tts = gTTS(script, lang="en")
            audio_path = folder / "voiceover.mp3"
            tts.save(str(audio_path))
            print(f"[*] Saved audio to {audio_path}")
        except Exception as e:
            print("[!] gTTS failed:", e)
            # continue without audio (skip video creation)
            return False

        # Thumbnail
        try:
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
            print(f"[*] Saved thumbnail to {thumb_path}")
        except Exception as e:
            print("[!] Thumbnail generation failed:", e)
            return False

        # Video assembly
        try:
            print("[*] Generating video (ffmpeg)...")
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
        except subprocess.CalledProcessError as e:
            print("[!] ffmpeg failed:", e)
            return False

        return True

    except Exception as e:
        print("[!] Unexpected pipeline error for topic:", TOPIC)
        traceback.print_exc()
        return False

# -------------------------------
# MAIN
# -------------------------------

def main():
    topics = []
    env_topic = os.environ.get("TOPIC", "").strip()
    if env_topic:
        topics = [env_topic]
    else:
        # generate up to NUM_VIDEOS topics
        for i in range(NUM_VIDEOS):
            t = pick_best_topic()
            if t:
                topics.append(t)
            else:
                break

    if not topics:
        print("[!] No topics to process. Exiting cleanly.")
        return 0

    print("[*] Final topic list:", topics)

    successes = 0
    for TOPIC in topics:
        ok = run_pipeline_for_topic(TOPIC)
        if ok:
            successes += 1
        else:
            print(f"[*] Topic failed: {TOPIC} — continuing to next topic.")

    print(f"[*] Completed. Successes: {successes}/{len(topics)}")
    return 0

if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(rc)
    except Exception as e:
        print("[FATAL] Unhandled exception in main:", e)
        traceback.print_exc()
        # exit non-zero only for truly fatal errors (missing env handled earlier)
        sys.exit(1)
