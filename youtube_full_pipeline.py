import os
import datetime
from pathlib import Path
from slugify import slugify
from gtts import gTTS
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
import subprocess
import textwrap

TOPIC = os.environ["TOPIC"]
API_KEY = os.environ["OPENAI_API_KEY"]

BASE = Path(".")
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

client = OpenAI(api_key=API_KEY)

print(f"[*] Topic: {TOPIC}")

prompt = f"""
You are a YouTube content creator.

Generate:
1. A strong YouTube title (max 70 characters)
2. A compelling description (2–3 paragraphs + bullet points)
3. A full video script (around 1200–1500 words) broken into short paragraphs.

Topic: "{TOPIC}"

Return in this exact format:

TITLE:
<one line>

DESCRIPTION:
<multi-line>

SCRIPT:
<multi-line>
"""

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.8,
)

text = resp.choices[0].message.content

def extract(label, txt):
    marker = f"{label}:\n"
    start = txt.index(marker) + len(marker)
    end = len(txt)
    for other in ["TITLE:\n", "DESCRIPTION:\n", "SCRIPT:\n"]:
        if other == marker:
            continue
        idx = txt.find(other, start)
        if idx != -1:
            end = min(end, idx)
    return txt[start:end].strip()

title = extract("TITLE", text)
description = extract("DESCRIPTION", text)
script = extract("SCRIPT", text)

now = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
slug = slugify(TOPIC)[:60]
folder = OUT / f"{now}_{slug}"
folder.mkdir(exist_ok=True)

# Save text files
(script_path := folder / "script.md").write_text(
    f"# {title}\n\n## Description\n{description}\n\n## Script\n\n{script}",
    encoding="utf-8",
)
(folder / "title.txt").write_text(title, encoding="utf-8")
(folder / "description.txt").write_text(description, encoding="utf-8")

print(f"[*] Saved script to {script_path}")

# Voiceover
print("[*] Generating voiceover...")
tts = gTTS(script, lang="en")
audio_path = folder / "voiceover.mp3"
tts.save(str(audio_path))
print(f"[*] Saved audio to {audio_path}")

# Thumbnail (simple text on background)
print("[*] Generating thumbnail...")
thumb_path = folder / "thumbnail.png"
img = Image.new("RGB", (1280, 720), color=(20, 20, 20))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
except:
    font = ImageFont.load_default()

wrapped = textwrap.fill(title, width=20)
w, h = draw.multiline_textsize(wrapped, font=font)
x = (1280 - w) // 2
y = (720 - h) // 2
draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255))
img.save(thumb_path)
print(f"[*] Saved thumbnail to {thumb_path}")

# Video: static thumbnail + audio
print("[*] Generating video...")
video_path = folder / "final_video.mp4"

subprocess.run([
    "ffmpeg",
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
    "-y",
], check=True)

print(f"[*] Final video: {video_path}")
print("[*] Done. All files in:", folder)
