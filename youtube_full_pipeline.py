import os
import json
import uuid
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


OUTPUT_ROOT = "output"


def ensure(path: str):
    os.makedirs(path, exist_ok=True)


def write(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def select_topic():
    topic = {
        "id": str(uuid.uuid4()),
        "title": "10 Tiny Habits That Quietly Change Your Life",
        "score": 0.92,
    }
    log.info("Selected topic: %s", topic["title"])
    return topic


def generate_script(topic):
    segments = [
        {"text": "Habit #1: The 2-minute reset...", "duration": 8},
        {"text": "Habit #2: The 10-step walk...", "duration": 8},
        {"text": "Habit #3: The friction delete...", "duration": 8},
        {"text": "Habit #4: The 1-line journal...", "duration": 8},
        {"text": "Habit #5: The micro-yes...", "duration": 8},
        {"text": "Habit #6: The no-notification block...", "duration": 8},
        {"text": "Habit #7: The future-you check...", "duration": 8},
        {"text": "Habit #8: The one-message rule...", "duration": 8},
        {"text": "Habit #9: The tiny upgrade...", "duration": 8},
        {"text": "Habit #10: The 5-second pause...", "duration": 8},
    ]

    script = {
        "topic_id": topic["id"],
        "title": topic["title"],
        "segments": segments,
        "duration_sec": sum(s["duration"] for s in segments),
    }

    log.info("Generated script (%ds)", script["duration_sec"])
    return script


def generate_voiceover(script, out_dir):
    ensure(out_dir)
    paths = []

    for i, seg in enumerate(script["segments"]):
        path = os.path.join(out_dir, f"vo_{i:03d}.wav")
        write(path, b"FAKE_WAV_DATA")
        paths.append(path)

    log.info("Generated %d voiceover segments", len(paths))
    return paths


def generate_visuals(script, out_dir):
    ensure(out_dir)
    paths = []

    for i, seg in enumerate(script["segments"]):
        path = os.path.join(out_dir, f"vis_{i:03d}.mp4")
        write(path, b"FAKE_VIDEO_DATA")
        paths.append(path)

    log.info("Generated %d visual clips", len(paths))
    return paths


def assemble_video(voice_paths, visual_paths, out_dir):
    ensure(out_dir)
    final_path = os.path.join(out_dir, "final_video.mp4")
    write(final_path, b"FAKE_FINAL_VIDEO")
    log.info("Assembled final video")
    return final_path


def run():
    ensure(OUTPUT_ROOT)

    topic = select_topic()
    script = generate_script(topic)

    script_path = os.path.join(OUTPUT_ROOT, "script.json")
    write_json(script_path, script)

    vo_dir = os.path.join(OUTPUT_ROOT, "audio")
    vi_dir = os.path.join(OUTPUT_ROOT, "visuals")
    final_dir = OUTPUT_ROOT

    voice_paths = generate_voiceover(script, vo_dir)
    visual_paths = generate_visuals(script, vi_dir)
    final_video = assemble_video(voice_paths, visual_paths, final_dir)

    summary = {
        "topic": topic,
        "script": script,
        "voiceover": voice_paths,
        "visuals": visual_paths,
        "final_video": final_video,
    }

    write_json(os.path.join(OUTPUT_ROOT, "summary.json"), summary)
    log.info("Pipeline complete")


if __name__ == "__main__":
    run()
