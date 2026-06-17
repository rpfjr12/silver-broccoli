#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, random, shutil, struct, subprocess
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

def select_facts(d: date, count: int | None) -> list[str]:
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
            lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    return "\n".join(lines)

def gradient_background(top, bottom):
    img = Image.new("RGB",(WIDTH,HEIGHT),top)
    px = img.load()
    for y in range(HEIGHT):
        r = y/max(HEIGHT-1,1)
        c = tuple(int(top[i]*(1-r)+bottom[i]*r) for i in range(3))
        for x in range(WIDTH): px[x,y]=c
    return img.filter(ImageFilter.GaussianBlur(0.3))

def draw_centered_text(draw, text, font, cy, fill, stroke_fill, stroke_width=4):
    w,h = text_size(draw,text,font)
    x = (WIDTH-w)//2
    y = cy - h//2
    draw.multiline_text((x,y), text, font=font, fill=fill,
                        spacing=16, align="center",
                        stroke_width=stroke_width, stroke_fill=stroke_fill)

def render_slide(fact, idx, total, out_path, rng):
    top, accent, txt = PALETTES[idx % len(PALETTES)]
    bottom = tuple(max(0,c-45) for c in top)
    img = gradient_background(top,bottom)
    d = ImageDraw.Draw(img)

    for _ in range(42):
        r = rng.randint(4,28)
        x = rng.randint(-r, WIDTH+r)
        y = rng.randint(-r, HEIGHT+r)
        c = tuple(min(255, a+rng.randint(10,70)) for a in accent)
        d.ellipse((x-r,y-r,x+r,y+r), fill=c)

    overlay = Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((72,360,WIDTH-72,1510), radius=54,
                         fill=(0,0,0,150), outline=accent+(255,), width=6)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    title_font = find_font(72)
    num_font = find_font(58)
    fact_font = find_font(66)
    foot_font = find_font(38, bold=False)

    draw_centered_text(d,"WEIRD FACT",title_font,210,accent,(0,0,0),3)
    draw_centered_text(d,f"#{idx+1} / {total}",num_font,315,txt,(0,0,0),3)

    wrapped = wrap_text(d,fact,fact_font,WIDTH-190)
    while text_size(d,wrapped,fact_font)[1] > 760 and fact_font.size > 44:
        fact_font = find_font(fact_font.size-4)
        wrapped = wrap_text(d,fact,fact_font,WIDTH-190)

    draw_centered_text(d,wrapped,fact_font,HEIGHT//2+60,txt,(0,0,0),5)

    footer = "Follow for daily weird facts"
    fw,fh = text_size(d,footer,foot_font)
    d.rounded_rectangle(((WIDTH-fw)//2-34,1660,(WIDTH+fw)//2+34,1660+fh+34),
                        radius=26, fill=accent)
    d.text(((WIDTH-fw)//2,1677), footer, font=foot_font, fill=(0,0,0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path,"PNG",optimize=True)

def box(kind,p=b""): return struct.pack(">I4s",len(p)+8,kind)+p
def full_box(kind,v,f,p=b""): return box(kind,bytes([v])+f.to_bytes(3,"big")+p)

def make_mvhd(ts, dur):
    m = b"\x00\x01\x00\x00"+b"\x00"*10+b"\x00\x01\x00\x00"+b"\x00"*24+b"\x00"*24+struct.pack(">I",2)
    p = struct.pack(">IIIIIIHH",0,0,ts,dur,0x00010000,0x0100,0,0)+b"\x00"*8+m
    return full_box(b"mvhd",0,0,p)

def make_tkhd(tid,dur):
    m = b"\x00\x01\x00\x00"+b"\x00"*10+b"\x00\x01\x00\x00"+b"\x00"*24
    p = struct.pack(">IIIIIIIIHHHH",0,0,tid,0,dur,0,0,0,0,0,0,0)+m+struct.pack(">II",WIDTH<<16,HEIGHT<<16)
    return full_box(b"tkhd",0,0x7,p)

def make_mdhd(ts,dur): return full_box(b"mdhd",0,0,struct.pack(">IIIIHH",0,0,ts,dur,0x55C4,0))
def make_hdlr(): return full_box(b"hdlr",0,0,b"\x00"*4+b"vide"+b"\x00"*12+b"VideoHandler\x00")

def make_stsd():
    e = b"\x00"*6+struct.pack(">H",1)+b"\x00"*16
    e += struct.pack(">HH",WIDTH,HEIGHT)
    e += struct.pack(">II",0x00480000,0x00480000)+b"\x00"*4+struct.pack(">H",1)
    e += b"Python MJPEG".ljust(32,b"\x00")+struct.pack(">Hh",24,-1)
    return full_box(b"stsd",0,0,struct.pack(">I",1)+box(b"jpeg",e))

def make_stts(n,delta): return full_box(b"stts",0,0,struct.pack(">II",1,n)+struct.pack(">I",delta))
def make_stsc(n): return full_box(b"stsc",0,0,struct.pack(">IIII",1,1,n,1))
def make_stsz(s): return full_box(b"stsz",0,0,struct.pack(">II",0,len(s))+b"".join(struct.pack(">I",x) for x in s))
def make_stco(off): return full_box(b"stco",0,0,struct.pack(">II",1,off))

def make_moov(sizes, off, ts, delta):
    dur = delta*len(sizes)
    stbl = box(b"stbl", make_stsd()+make_stts(len(sizes),delta)
               +full_box(b"stss",0,0,struct.pack(">I",len(sizes))+b"".join(struct.pack(">I",i+1) for i in range(len(sizes))))
               +make_stsc(len(sizes))+make_stsz(sizes)+make_stco(off))
    dinf = box(b"dinf", full_box(b"dref",0,0,struct.pack(">I",1)+full_box(b"url ",0,1)))
    minf = box(b"minf", full_box(b"vmhd",0,1,struct.pack(">HHHH",0,0,0,0))+dinf+stbl)
    mdia = box(b"mdia", make_mdhd(ts,dur)+make_hdlr()+minf)
    trak = box(b"trak", make_tkhd(1,dur)+mdia)
    return box(b"moov", make_mvhd(ts,dur)+trak)

def write_python_mjpeg_mp4(slides, out):
    frames=[]
    for s in slides:
        with Image.open(s) as im:
            f=im.convert("RGB")
            tmp=out.with_suffix(f".{s.stem}.jpg")
            f.save(tmp,"JPEG",quality=92,optimize=True)
            frames.append(tmp.read_bytes())
            tmp.unlink(missing_ok=True)
    ftyp=box(b"ftyp",b"qt  \x00\x00\x02\x00qt  ")
    mdat=box(b"mdat",b"".join(frames))
    moov=make_moov([len(f) for f in frames], len(ftyp)+8, 1000, SLIDE_SECONDS*1000)
    out.write_bytes(ftyp+mdat+moov)

def imagemagick_command():
    return shutil.which("magick") or shutil.which("convert")

def render_video(slides, out):
    cmd = imagemagick_command()
    if cmd:
        args=[cmd]
        if Path(cmd).name=="magick": args.append("convert")
        args += [str(s) for s in slides]
        args += ["-delay",str(SLIDE_SECONDS*100),"-loop","0",str(out)]
        r=subprocess.run(args,check=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if r.returncode==0 and out.exists() and out.stat().st_size>0:
            return "imagemagick"
    write_python_mjpeg_mp4(slides,out)
    return "python-mjpeg-mp4-fallback"

def write_metadata(pkg, path):
    path.write_text(json.dumps(asdict(pkg),indent=2)+"\n",encoding="utf-8")

def build_package(d, outdir, count):
    facts = select_facts(d,count)
    slug = d.isoformat()
    pkgdir = outdir/slug
    slidesdir = pkgdir/"slides"
    pkgdir.mkdir(parents=True,exist_ok=True)
    rng = random.Random(stable_seed(d))

    slides=[]
    for i,f in enumerate(facts):
        p = slidesdir/f"slide_{i+1:02d}.png"
        render_slide(f,i,len(facts),p,rng)
        slides.append(p)

    video = pkgdir/f"weird_facts_{slug}.mp4"
    renderer = render_video(slides,video)

    pkg = VideoPackage(
        run_date=slug,
        title=f"{len(facts)} Weird Facts You Won't Believe",
        video_path=str(video),
        slides=[str(s) for s in slides],
        facts=facts,
        renderer=renderer,
    )
    write_metadata(pkg, pkgdir/"metadata.json")
    write_metadata(pkg, outdir/"latest.json")
    return pkg

def parse_args(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=os.environ.get("RUN_DATE"))
    p.add_argument("--output",type=Path,default=OUTPUT_DIR)
    p.add_argument("--facts",type=int,default=None)
    return p.parse_args(argv)

def main(argv=None):
    a=parse_args(argv)
    d = datetime.now(timezone.utc).date() if not a.date else date.fromisoformat(a.date)
    pkg = build_package(d,a.output,a.facts)
    print(json.dumps(asdict(pkg),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
