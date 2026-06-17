#!/usr/bin/env python3
"""Generate daily weird-facts vertical short videos with free local tooling.

The generator is deterministic by date, uses no API keys, and produces a daily
1080x1920 slideshow MP4 plus the source slide PNGs and metadata. It prefers
ImageMagick when available and falls back to a tiny pure-Python Motion-JPEG MP4
writer so GitHub Actions does not fail because of a missing video delegate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import struct
import subprocess
import wave
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1080
HEIGHT = 1920
SLIDE_SECONDS = 3
OUTPUT_DIR = Path("output")
FACT_COUNT_MIN = 5
FACT_COUNT_MAX = 10

WEIRD_FACTS = [
    "Octopuses have three hearts, and two of them stop beating when they swim.",
    "Bananas are berries, but strawberries are not berries in botanical terms.",
    "A day on Venus is longer than a year on Venus.",
    "Wombat poop is cube-shaped, which helps it stay in place.",
    "Sharks existed before trees appeared on Earth.",
    "The Eiffel Tower can grow over six inches taller during hot weather.",
    "Honey never truly spoils when stored correctly.",
    "A group of flamingos is called a flamboyance.",
    "Some turtles can breathe through their butts during hibernation.",
    "There are more possible chess games than atoms in the observable universe.",
    "The fingerprints of koalas are so similar to humans that they can confuse investigators.",
    "A cloud can weigh more than a million pounds.",
    "Sloths can hold their breath longer than dolphins can.",
    "The first oranges were not orange; many were green.",
    "Scotland's national animal is the unicorn.",
    "A shrimp's heart is located in its head.",
    "Some metals are so reactive that they explode when they touch water.",
    "The longest hiccuping spell on record lasted for decades.",
    "Ravens can mimic human speech and remember faces.",
    "The moon has moonquakes.",
    "A single strand of spaghetti is technically called a spaghetto.",
    "Sea otters hold hands while sleeping so they do not drift apart.",
    "The smell of freshly cut grass is a plant distress signal.",
    "Butterflies can taste with their feet.",
    "A bolt of lightning is about five times hotter than the surface of the sun.",
    "Cows have best friends and can become stressed when separated.",
    "The dot over a lowercase i or j is called a tittle.",
    "Some frogs can freeze solid and come back to life when they thaw.",
    "A blue whale's heart can weigh as much as a small car.",
    "The inventor of the microwave appliance was inspired by a melted candy bar.",
]

PALETTES = [
    ((11, 19, 43), (255, 196, 61), (255, 255, 255)),
    ((22, 33, 62), (233, 69, 96), (255, 255, 255)),
    ((7, 59, 76), (6, 214, 160), (255, 255, 255)),
    ((36, 0, 70), (255, 158, 0), (255, 255, 255)),
    ((0, 48, 73), (252, 191, 73), (255, 255, 255)),
]


@dataclass(frozen=True)
class VideoPackage:
    run_date: str
    title: str
    video_path: str
    slides: list[str]
    facts: list[str]
    renderer: str
    audio_path: str | None = None
    caption_path: str | None = None
    width: int = WIDTH
    height: int = HEIGHT
    slide_seconds: int = SLIDE_SECONDS


def stable_seed(run_date: date) -> int:
    return int(run_date.strftime("%Y%m%d"))


def select_facts(run_date: date, requested_count: int | None) -> list[str]:
    rng = random.Random(stable_seed(run_date))
    count = requested_count or rng.randint(FACT_COUNT_MIN, FACT_COUNT_MAX)
    count = max(FACT_COUNT_MIN, min(FACT_COUNT_MAX, count))
    return rng.sample(WEIRD_FACTS, count)


def find_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=16)
    return right - left, bottom - top


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        width, _ = text_size(draw, trial, font)
        if width <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def gradient_background(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), top)
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / max(HEIGHT - 1, 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = color
    return image.filter(ImageFilter.GaussianBlur(radius=0.3))


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    center_y: int,
    fill: tuple[int, int, int],
    stroke_fill: tuple[int, int, int],
    stroke_width: int = 4,
) -> None:
    width, height = text_size(draw, text, font)
    x = (WIDTH - width) // 2
    y = center_y - height // 2
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill,
        spacing=16,
        align="center",
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def render_slide(fact: str, index: int, total: int, out_path: Path, rng: random.Random) -> None:
    bg_top, accent, text_color = PALETTES[index % len(PALETTES)]
    bg_bottom = tuple(max(0, channel - 45) for channel in bg_top)
    image = gradient_background(bg_top, bg_bottom)
    draw = ImageDraw.Draw(image)

    for _ in range(42):
        radius = rng.randint(4, 28)
        x = rng.randint(-radius, WIDTH + radius)
        y = rng.randint(-radius, HEIGHT + radius)
        alpha_color = tuple(min(255, c + rng.randint(10, 70)) for c in accent)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=alpha_color)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    card_margin = 72
    card_top = 360
    card_bottom = 1510
    overlay_draw.rounded_rectangle(
        (card_margin, card_top, WIDTH - card_margin, card_bottom),
        radius=54,
        fill=(0, 0, 0, 150),
        outline=accent + (255,),
        width=6,
    )
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    title_font = find_font(72)
    number_font = find_font(58)
    fact_font = find_font(66)
    footer_font = find_font(38, bold=False)

    draw_centered_text(draw, "WEIRD FACT", title_font, 210, accent, (0, 0, 0), 3)
    draw_centered_text(draw, f"#{index + 1} / {total}", number_font, 315, text_color, (0, 0, 0), 3)

    wrapped = wrap_text(draw, fact, fact_font, WIDTH - 190)
    while text_size(draw, wrapped, fact_font)[1] > 760 and getattr(fact_font, "size", 66) > 44:
        fact_font = find_font(getattr(fact_font, "size", 66) - 4)
        wrapped = wrap_text(draw, fact, fact_font, WIDTH - 190)
    draw_centered_text(draw, wrapped, fact_font, HEIGHT // 2 + 60, text_color, (0, 0, 0), 5)

    footer = "Follow for daily weird facts"
    footer_width, footer_height = text_size(draw, footer, footer_font)
    draw.rounded_rectangle(
        ((WIDTH - footer_width) // 2 - 34, 1660, (WIDTH + footer_width) // 2 + 34, 1660 + footer_height + 34),
        radius=26,
        fill=accent,
    )
    draw.text(((WIDTH - footer_width) // 2, 1677), footer, font=footer_font, fill=(0, 0, 0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "PNG", optimize=True)


def box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", len(payload) + 8, kind) + payload


def full_box(kind: bytes, version: int, flags: int, payload: bytes = b"") -> bytes:
    return box(kind, bytes([version]) + flags.to_bytes(3, "big") + payload)


def make_mvhd(timescale: int, duration: int) -> bytes:
    matrix = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00"
    payload = struct.pack(">IIIIIIHH", 0, 0, timescale, duration, 0x00010000, 0x0100, 0, 0)
    payload += b"\x00" * 8 + matrix + b"\x00" * 24 + struct.pack(">I", 2)
    return full_box(b"mvhd", 0, 0, payload)


def make_tkhd(track_id: int, duration: int) -> bytes:
    matrix = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00"
    payload = struct.pack(">IIIIIIIIHHHH", 0, 0, track_id, 0, duration, 0, 0, 0, 0, 0, 0, 0)
    payload += matrix + struct.pack(">II", WIDTH << 16, HEIGHT << 16)
    return full_box(b"tkhd", 0, 0x000007, payload)


def make_mdhd(timescale: int, duration: int) -> bytes:
    return full_box(b"mdhd", 0, 0, struct.pack(">IIIIHH", 0, 0, timescale, duration, 0x55C4, 0))


def make_hdlr() -> bytes:
    return full_box(b"hdlr", 0, 0, b"\x00" * 4 + b"vide" + b"\x00" * 12 + b"VideoHandler\x00")


def make_stsd() -> bytes:
    visual_sample_entry = b"\x00" * 6 + struct.pack(">H", 1) + b"\x00" * 16
    visual_sample_entry += struct.pack(">HH", WIDTH, HEIGHT)
    visual_sample_entry += struct.pack(">II", 0x00480000, 0x00480000) + b"\x00" * 4 + struct.pack(">H", 1)
    visual_sample_entry += b"Python MJPEG".ljust(32, b"\x00") + struct.pack(">Hh", 24, -1)
    jpeg_entry = box(b"jpeg", visual_sample_entry)
    return full_box(b"stsd", 0, 0, struct.pack(">I", 1) + jpeg_entry)


def make_stts(sample_count: int, sample_delta: int) -> bytes:
    return full_box(b"stts", 0, 0, struct.pack(">II", 1, sample_count) + struct.pack(">I", sample_delta))


def make_stsc(sample_count: int) -> bytes:
    return full_box(b"stsc", 0, 0, struct.pack(">IIII", 1, 1, sample_count, 1))


def make_stsz(sizes: Sequence[int]) -> bytes:
    return full_box(b"stsz", 0, 0, struct.pack(">II", 0, len(sizes)) + b"".join(struct.pack(">I", size) for size in sizes))


def make_stco(offset: int) -> bytes:
    return full_box(b"stco", 0, 0, struct.pack(">II", 1, offset))


def make_moov(sample_sizes: Sequence[int], mdat_data_offset: int, timescale: int, sample_delta: int) -> bytes:
    duration = sample_delta * len(sample_sizes)
    stbl = box(b"stbl", make_stsd() + make_stts(len(sample_sizes), sample_delta) + full_box(b"stss", 0, 0, struct.pack(">I", len(sample_sizes)) + b"".join(struct.pack(">I", i + 1) for i in range(len(sample_sizes)))) + make_stsc(len(sample_sizes)) + make_stsz(sample_sizes) + make_stco(mdat_data_offset))
    dinf = box(b"dinf", full_box(b"dref", 0, 0, struct.pack(">I", 1) + full_box(b"url ", 0, 1)))
    minf = box(b"minf", full_box(b"vmhd", 0, 1, struct.pack(">HHHH", 0, 0, 0, 0)) + dinf + stbl)
    mdia = box(b"mdia", make_mdhd(timescale, duration) + make_hdlr() + minf)
    trak = box(b"trak", make_tkhd(1, duration) + mdia)
    return box(b"moov", make_mvhd(timescale, duration) + trak)


def write_python_mjpeg_mp4(slides: Sequence[Path], output_path: Path) -> None:
    jpeg_frames: list[bytes] = []
    for slide in slides:
        with Image.open(slide) as image:
            frame = image.convert("RGB")
            temp = output_path.with_suffix(f".{slide.stem}.jpg")
            frame.save(temp, "JPEG", quality=92, optimize=True)
            jpeg_frames.append(temp.read_bytes())
            temp.unlink(missing_ok=True)

    ftyp = box(b"ftyp", b"qt  \x00\x00\x02\x00qt  ")
    mdat_payload = b"".join(jpeg_frames)
    mdat_header_size = 8
    mdat_data_offset = len(ftyp) + mdat_header_size
    mdat = box(b"mdat", mdat_payload)
    moov = make_moov([len(frame) for frame in jpeg_frames], mdat_data_offset, 1000, SLIDE_SECONDS * 1000)
    output_path.write_bytes(ftyp + mdat + moov)



def ffmpeg_command() -> str | None:
    return shutil.which("ffmpeg")


def espeak_command() -> str | None:
    return shutil.which("espeak-ng") or shutil.which("espeak")


def shell_escape_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", r"'\''")


def write_slide_concat(slides: Sequence[Path], concat_path: Path) -> None:
    lines: list[str] = []
    for slide in slides:
        lines.append(f"file '{shell_escape_concat_path(slide)}'\n")
        lines.append(f"duration {SLIDE_SECONDS}\n")
    lines.append(f"file '{shell_escape_concat_path(slides[-1])}'\n")
    concat_path.write_text("".join(lines), encoding="utf-8")


def make_narration_text(facts: Sequence[str]) -> str:
    lines = ["Weird facts that sound fake, but are real."]
    for index, fact in enumerate(facts, start=1):
        lines.append(f"Fact {index}. {fact}")
    lines.append("Follow for more weird facts tomorrow.")
    return " ".join(lines)


def seconds_to_srt_time(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


def write_captions(facts: Sequence[str], caption_path: Path) -> None:
    blocks: list[str] = []
    cursor = 0
    for index, fact in enumerate(facts, start=1):
        start = seconds_to_srt_time(cursor)
        cursor += SLIDE_SECONDS
        end = seconds_to_srt_time(cursor)
        blocks.append(f"{index}\n{start} --> {end}\nFact {index}: {fact}\n")
    caption_path.write_text("\n".join(blocks), encoding="utf-8")


def write_music_bed(path: Path, duration_seconds: int, seed: int) -> None:
    rng = random.Random(seed)
    sample_rate = 44100
    notes = [196.0, 220.0, 246.94, 261.63, 293.66, 329.63, 392.0]
    total_samples = duration_seconds * sample_rate
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        progression = [notes[(index + rng.randint(0, 2)) % len(notes)] for index in range(max(1, duration_seconds * 2))]
        for sample in range(total_samples):
            second = sample / sample_rate
            beat = int(second * 2) % len(progression)
            frequency = progression[beat]
            envelope = 0.35 + 0.65 * abs(math.sin(math.pi * (second % 0.5) / 0.5))
            tone = math.sin(2 * math.pi * frequency * second)
            harmony = 0.35 * math.sin(2 * math.pi * frequency * 1.5 * second)
            pulse = 0.25 * math.sin(2 * math.pi * 70 * second)
            value = int(9500 * envelope * (tone + harmony + pulse) / 1.6)
            handle.writeframes(struct.pack("<h", max(-32767, min(32767, value))))


def write_voiceover(text: str, voice_path: Path) -> bool:
    command = espeak_command()
    if not command:
        return False
    result = subprocess.run(
        [command, "-w", str(voice_path), "-s", "165", "-p", "55", text],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0 and voice_path.exists() and voice_path.stat().st_size > 0


def render_video_with_ffmpeg(slides: Sequence[Path], facts: Sequence[str], output_path: Path, package_dir: Path, seed: int) -> tuple[bool, str | None, str | None]:
    ffmpeg = ffmpeg_command()
    if not ffmpeg:
        return False, None, None

    concat_path = package_dir / "slides.ffconcat"
    silent_video = package_dir / "silent_slideshow.mp4"
    music_path = package_dir / "music_bed.wav"
    voice_path = package_dir / "voiceover.wav"
    caption_path = package_dir / "captions.srt"
    total_duration = len(slides) * SLIDE_SECONDS

    write_slide_concat(slides, concat_path)
    write_music_bed(music_path, total_duration, seed)
    write_captions(facts, caption_path)
    has_voice = write_voiceover(make_narration_text(facts), voice_path)

    video_result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
            str(silent_video),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if video_result.returncode != 0:
        return False, None, str(caption_path)

    if has_voice:
        mux_command = [
            ffmpeg,
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(voice_path),
            "-i",
            str(music_path),
            "-filter_complex",
            "[1:a]volume=1.25[a1];[2:a]volume=0.18[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        audio_path = str(voice_path)
    else:
        mux_command = [
            ffmpeg,
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(music_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        audio_path = str(music_path)

    mux_result = subprocess.run(mux_command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if mux_result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        return False, None, str(caption_path)
    return True, audio_path, str(caption_path)

def imagemagick_command() -> str | None:
    return shutil.which("magick") or shutil.which("convert")


def render_video(slides: Sequence[Path], facts: Sequence[str], output_path: Path, package_dir: Path, seed: int) -> tuple[str, str | None, str | None]:
    rendered, audio_path, caption_path = render_video_with_ffmpeg(slides, facts, output_path, package_dir, seed)
    if rendered:
        return "ffmpeg-audio-short", audio_path, caption_path

    command = imagemagick_command()
    if command:
        args = [command]
        if Path(command).name == "magick":
            args.append("convert")
        args.extend([str(slide) for slide in slides])
        args.extend(["-delay", str(SLIDE_SECONDS * 100), "-loop", "0", str(output_path)])
        result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return "imagemagick-silent", None, caption_path
    write_python_mjpeg_mp4(slides, output_path)
    return "python-mjpeg-mp4-fallback-silent", None, caption_path


def write_metadata(package: VideoPackage, metadata_path: Path) -> None:
    metadata_path.write_text(json.dumps(asdict(package), indent=2) + "\n", encoding="utf-8")


def build_package(run_date: date, output_dir: Path, fact_count: int | None) -> VideoPackage:
    facts = select_facts(run_date, fact_count)
    slug = run_date.isoformat()
    package_dir = output_dir / slug
    slides_dir = package_dir / "slides"
    package_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(stable_seed(run_date))

    slides: list[Path] = []
    for index, fact in enumerate(facts):
        slide_path = slides_dir / f"slide_{index + 1:02d}.png"
        render_slide(fact, index, len(facts), slide_path, rng)
        slides.append(slide_path)

    video_path = package_dir / f"weird_facts_{slug}.mp4"
    renderer, audio_path, caption_path = render_video(slides, facts, video_path, package_dir, stable_seed(run_date))
    package = VideoPackage(
        run_date=slug,
        title=f"{len(facts)} Weird Facts You Won't Believe",
        video_path=str(video_path),
        slides=[str(path) for path in slides],
        facts=facts,
        renderer=renderer,
        audio_path=audio_path,
        caption_path=caption_path,
    )
    write_metadata(package, package_dir / "metadata.json")
    write_metadata(package, output_dir / "latest.json")
    return package


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a daily vertical weird-facts MP4.")
    parser.add_argument("--date", default=os.environ.get("RUN_DATE"), help="Run date in YYYY-MM-DD format. Defaults to today UTC.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="Output directory.")
    parser.add_argument("--facts", type=int, default=None, help="Number of facts/slides, clamped to 5-10.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    run_date = datetime.now(timezone.utc).date() if not args.date else date.fromisoformat(args.date)
    package = build_package(run_date, args.output, args.facts)
    print(json.dumps(asdict(package), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
