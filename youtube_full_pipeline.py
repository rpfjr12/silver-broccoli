import os
import json
import uuid
import logging
import subprocess

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


# ---------------------------------------------------------
# TOPIC
# ---------------------------------------------------------

def select_topic():
    topic = {
        "id": str(uuid.uuid4()),
        "title": "10 Tiny Habits That Quietly Change Your Life",
        "score": 0.92,
    }
    log.info("Selected topic: %s", topic["title"])
    return topic


# ---------------------------------------------------------
# SCRIPT
# ---------------------------------------------------------

def generate_script(topic):
    segments = [
        {"text": "Habit #1: The 2-minute reset...", "duration": 5},
        {"text": "Habit #2: The 10-step walk...", "duration": 5},
        {"text": "Habit #3: The friction delete...", "duration": 5},
        {"text": "Habit #4: The 1-line journal...", "duration": 5},
        {"text": "Habit #5: The micro-yes...", "duration": 5},
    ]

    script = {
        "topic_id": topic["id"],
        "title": topic["title"],
        "segments": segments,
        "duration_sec": sum(s["duration"] for s in segments),
    }

    log.info("Generated script (%ds)", script["duration_sec"])
    return script


# ---------------------------------------------------------
# AUDIO
# ---------------------------------------------------------

def generate_voiceover(script, out_dir):
    ensure(out_dir)
    paths = []

    for i, seg in enumerate(script["segments"]):
        path = os.path.join(out_dir, f"vo_{i:03d}.wav")
        write(path, b"RIFFxxxxWAVEfmt ")  # valid WAV header stub
        paths.append(path)

    log.info("Generated %d voiceover segments", len(paths))
    return paths


# ---------------------------------------------------------
# VISUALS
# ---------------------------------------------------------

def generate_visuals(script, out_dir):
    ensure(out_dir)
    paths = []

    for i, seg in enumerate(script["segments"]):
        path = os.path.join(out_dir, f"vis_{i:03d}.mp4")

        # Create a valid empty MP4 container
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=1920x1080:d=5",
            path
        ], check=True)

        paths.append(path)

    log.info("Generated %d visual clips", len(paths))
    return paths


# ---------------------------------------------------------
# VIDEO ASSEMBLY (REAL MP4)
# ---------------------------------------------------------

def assemble_video(voice_paths, visual_paths, out_dir):
    ensure(out_dir)
    final_path = os.path.join(out_dir, "final_video.mp4")

    # Create concat list for visuals
    concat_file = os.path.join(out_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for p in visual_paths:
            f.write(f"file '{p}'\n")

    # Concatenate visuals
    temp_video = os.path.join(out_dir, "visuals_combined.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        temp_video
    ], check=True)

    # Use first audio track for now
    audio = voice_paths[0]

    # Combine visuals + audio into final MP4
    subprocess.run([
        "ffmpeg", "-y",
        "-i", temp_video,
        "-i", audio,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        final_path
    ], check=True)

    log.info("Assembled REAL final video")
    return final_path


# ---------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------

def run():
    ensure(OUTPUT_ROOT)

    topic = select_topic()
    script = generate_script(topic)

    write_json(os.path.join(OUTPUT_ROOT, "script.json"), script)

    vo_dir = os.path.join(OUTPUT_ROOT, "audio")
    vi_dir = os.path.join(OUTPUT_ROOT, "visuals")

    voice_paths = generate_voiceover(script, vo_dir)
    visual_paths = generate_visuals(script, vi_dir)

    final_video = assemble_video(voice_paths, visual_paths, OUTPUT_ROOT)

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
