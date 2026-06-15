# youtube_full_pipeline.py
# FULL AUTOMATION — Robust Trend Scraper + Viral Script + Audio + Thumbnail + Video (Batch Mode)
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

NUM_VIDEOS = int(os.environ.get("NUM_VIDEOS", "3"))  # batch mode: 3 videos per run
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
        titles = re.findall(r'"text":"(.*?)"', r.text)
        clean = [t for t in titles if 5 < len(t) < 120]
        print(f"[*] YouTube trending: found {len(clean)} candidate titles")
        return clean[:20]
    except Exception as e:
        print("[!] YouTube trending scrape failed:", e)
        return []

def scrape_reddit_hot():
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
            if len(titles) >= 20:
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
    print("[*] Scraping trending
