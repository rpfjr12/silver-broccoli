# youtube_full_pipeline.py
# Paste this file into the repo root (do NOT hardcode API keys).
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
API_KEY = os.environ["OPENAI_API_KEY"]

BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

client = OpenAI(api_key=API_KEY)

def call_openai(prompt, model="gpt-4o-mini", temp=0.7, max_tokens=2000):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"user","content":prompt}],
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
    # pick the first non-empty line as TOPIC fallback
    m = re.search(r"1\.\s*(.+)", topics_text)
    if m:
        TOPIC = m.group(1).strip()
    else:
        TOPIC = "Weird facts that blow your mind"

print(f"[*] Using topic: {TOPIC}")

# Viral-optimized prompt: hook, retention, structure, thumbnail text, SEO
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

print("[*] Requesting viral-optimized content from OpenAI...")
full_text = call_openai(prompt, temp=0.8, max_tokens=2500)

# Helper to extract labeled sections
def extract_section(label, text):
    marker = f"{label}:\n"
    if marker not in text:
        return ""
    start = text.index(marker) + len(marker)
    # find next label or end
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
(script_path := folder / "script.md").write_text(f"# {title}\n\n## Description\n{description}\n\n## Script\n\n{script}\n\n## Chapters\n{chapters}", encoding="utf-8")

print(f"[*] Saved script to {script_path}")

# Voiceover
print("[*] Generating voiceover with gTTS...")
tts = gTTS(script, lang="en")
audio_path = folder / "voiceover.mp3"
tts.save(str(audio_path))
print(f"[*] Saved audio to {audio_path}")

# Thumbnail generation: two-line bold text on high-contrast background
print("[*] Generating thumbnail...")
thumb_path = folder / "thumbnail.png"
img = Image.new("RGB", (1280, 720), color=(18,18,18))
draw = ImageDraw.Draw(img)

# Prepare thumbnail text lines
lines = [l.strip() for l in thumbnail_text.splitlines() if l.strip()]
if not lines:
    # fallback: use title split
    lines = textwrap.wrap(title, width=18)[:2]

try:
    font_large = ImageFont.truetype("DejaVuSans-Bold.ttf", 88)
    font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
except:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

# draw a subtle rectangle for contrast
draw.rectangle([(40, 40), (1240, 680)], fill=(28,28,28))
y = 120
for i, line in enumerate(lines[:2]):
    f = font_large if i == 0 else font_small
    w, h = draw.textsize(line, font=f)
    x = (1280 - w) // 2
    draw.text((x, y), line, font=f, fill=(255, 230, 0))
    y += h + 10

# small channel tag
tag = "silver-broccoli"
tw, th = draw.textsize(tag, font=font_small)
draw.rectangle([(40, 680-th-20), (40+tw+20, 680)], fill=(255,255,255))
draw.text((50, 680-th-10), tag, font=font_small, fill=(0,0,0))

img.save(thumb_path)
print(f"[*] Saved thumbnail to {thumb_path}")

# Video: static thumbnail + audio
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
print("[*] Done. All files in:", folder)
