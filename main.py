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
    "The first oranges were