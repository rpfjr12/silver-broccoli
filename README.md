# Daily Weird Facts Shorts Generator

This repository contains a complete, zero-API-key GitHub Actions system that generates daily vertical weird-facts short-form videos.

## Repo structure

```text
.
├── .github/
│   └── workflows/
│       └── generate.yml
├── main.py
├── requirements.txt
├── README.md
└── output/              # created automatically by the workflow
```

## What it does

- Generates one daily 1080x1920 vertical video.
- Uses the viral-friendly **Weird Facts** niche.
- Selects 5-10 weird facts deterministically from a built-in fact bank.
- Creates one high-contrast centered slide per fact.
- Saves PNG source slides, generated captions, a synthetic music bed, optional offline voiceover, `metadata.json`, `latest.json`, and an audio-backed `.mp4` short under `output/`.
- Runs on GitHub Actions daily or manually.
- Commits the generated output back to the repository.

## Free tools only

The system uses:

- Python 3.11
- Pillow, a pure Python package distributed through `requirements.txt`
- ImageMagick installed by GitHub Actions
- FFmpeg installed by GitHub Actions for free local audio/video muxing
- espeak-ng installed by GitHub Actions for free offline narration
- GitHub Actions hosted runners

It does **not** use paid APIs, API keys, browser automation, Playwright, Puppeteer, Whisper, OpenAI, Gemini, or external content services. FFmpeg and espeak-ng are free local command-line tools installed inside GitHub Actions so the generated MP4 can include audio.

## Running locally

```bash
python -m pip install -r requirements.txt
python main.py --output output
```

Generate a specific date:

```bash
python main.py --date 2026-06-17 --output output
```

Generate a specific number of slides:

```bash
python main.py --facts 8 --output output
```

## Running in GitHub Actions

1. Push this repo to GitHub.
2. Open the **Actions** tab.
3. Select **Generate Daily Weird Facts Video**.
4. Click **Run workflow**.

The workflow also runs every day at `12:17 UTC`.

## Output

A successful run creates:

```text
output/
├── latest.json
└── YYYY-MM-DD/
    ├── metadata.json
    ├── captions.srt
    ├── music_bed.wav
    ├── voiceover.wav        # present when espeak-ng is available
    ├── weird_facts_YYYY-MM-DD.mp4
    └── slides/
        ├── slide_01.png
        ├── slide_02.png
        └── ...
```


## Legacy workflow compatibility

Older workflow runs may show failures from `youtube_full_pipeline.py` and FFmpeg concat paths such as `output/output/visuals/...`. That was the removed pipeline. This repo now uses `main.py` and `.github/workflows/generate.yml`. A small `youtube_full_pipeline.py` compatibility wrapper is kept so accidental old entrypoint calls delegate to the current generator instead of running the deleted FFmpeg pipeline.

## Stability notes

The generator first attempts to create a complete audio-backed MP4 with FFmpeg and offline espeak-ng narration. If those local tools are unavailable, it falls back to ImageMagick and finally to a pure-Python Motion-JPEG MP4 writer so a visual package can still be produced.
