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
import os
import random
import shutil
import struct
import subprocess
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


def find_font(size: int, bold: bool = True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size=size)
    return ImageFont.load_default()


def text_size(draw, text, font):
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=16)
    return right - left, bottom - top


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = []
    for w in words:
        trial = " ".join(current + [w])
        width, _ = text_size(draw, trial, font)
        if width <= max_width or not current:
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def gradient_background(top, bottom):
    image = Image.new("RGB", (WIDTH, HEIGHT), top)
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / max(HEIGHT - 1, 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = color
    return image.filter(ImageFilter.GaussianBlur(radius=0.3))


def draw_centered_text(draw, text, font, center_y, fill, stroke_fill, stroke_width=4):
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


def render_slide(fact, index, total, out_path, rng):
    bg_top, accent, text_color = PALETTES[index % len(PALETTES)]
    bg_bottom = tuple(max(0, c - 45) for c in bg_top)
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

    draw_centered_text(draw, "WEIRD FACT", title_font, 210, accent, (0, 0,
