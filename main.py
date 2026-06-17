#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, random, subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
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
    ((11,19,43),(255,196,61),(255,255,255)),
    ((22,33,62),(233,69,96),(255,255,255)),
    ((7,59,76),(6,214,160),(255,255,255)),
    ((36,0,70),(255,158,0),(255,255,255)),
    ((0,48,73),(252,191,73),(255,255,255)),
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

def stable_seed(d: date) -> int:
    return int(d.strftime("%Y%m%d"))

def select_facts(d: date, count: int | None):
    rng = random.Random(stable_seed(d))
    c = count or rng.randint(FACT_COUNT_MIN, FACT_COUNT_MAX)
    c = max(FACT_COUNT_MIN, min(FACT_COUNT_MAX, c))
    return rng.sample(WEIRD_FACTS, c)

def find_font(size: int, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()

def text_size(draw, text, font):
    l,t,r,b = draw.multiline_textbbox((0,0), text, font=font, spacing=16)
    return r-l, b-t

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur+[w])
        if text_size(draw, trial, font)[0] <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join
