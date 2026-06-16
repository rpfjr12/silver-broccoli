"""
youtube_full_pipeline.py

End-to-end YouTube video generation pipeline:
- Topic selection
- Script generation
- Voiceover generation
- Visual asset generation
- Video assembly
- Quality evaluation
- Artifact export

Designed for:
- GitHub Actions / CI usage
- Clear logging and error handling
- Easy swapping of providers (LLM, TTS, video editor, etc.)
"""

import os
import sys
import json
import time
import uuid
import shutil
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

# =========================
# Logging configuration
# =========================

LOG_LEVEL = os.getenv("PIPELINE_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("youtube_pipeline")


# =========================
# Data models
# =========================

@dataclass
class Topic:
    id: str
    title: str
    description: str
    keywords: List[str]
    score: float  # virality / interest score


@dataclass
class ScriptSegment:
    index: int
    start_sec: float
    end_sec: float
    text: str
    visual_hint: str


@dataclass
class Script:
    topic_id: str
    title: str
    hook: str
    segments: List[ScriptSegment]
    estimated_duration_sec: float


@dataclass
class VoiceoverSegment:
    index: int
    audio_path: str
    start_sec: float
    end_sec: float


@dataclass
class VisualAsset:
    index: int
    type: str  # "image", "video", "broll", "overlay"
    path: str
    start_sec: float
    end_sec: float
    metadata: Dict[str, Any]


@dataclass
class AssembledVideo:
    video_path: str
    duration_sec: float
    metadata: Dict[str, Any]


@dataclass
class QualityReport:
    score: float
    issues: List[str]
    recommendations: List[str]
    passes_threshold: bool


# =========================
# Configuration
# =========================

@dataclass
class PipelineConfig:
    output_root: str = "artifacts"
    min_quality_score: float = 0.78
    max_regenerations: int = 2
    target_duration_min: float = 8.0
    target_duration_max: float = 14.0
    # Provider-specific configs (placeholders)
    llm_model: str = "gpt-4.1"
    tts_voice: str = "en-US-Professional"
    video_resolution: str = "1920x1080"
    fps: int = 30


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# =========================
# Topic selection
# =========================

def select_topic(config: PipelineConfig) -> Topic:
    """
    Placeholder topic engine.
    In a real system, this would use:
    - Trends APIs
    - Keyword tools
    - Historical performance
    """
    # For now, deterministic but realistic placeholder.
    topic_id = str(uuid.uuid4())
    topic = Topic(
        id=topic_id,
        title="10 Tiny Habits That Quietly Change Your Life",
        description=(
            "A fast-paced breakdown of small, science-backed habits that "
            "dramatically improve life over time."
        ),
        keywords=[
            "self improvement",
            "habits",
            "productivity",
            "mental health",
            "life hacks",
        ],
        score=0.91,
    )
    logger.info("Selected topic: %s (score=%.2f)", topic.title, topic.score)
    return topic


# =========================
# Script generation
# =========================

def generate_script(config: PipelineConfig, topic: Topic) -> Script:
    """
    High-retention script structure:
    - 3s hook
    - Fast pacing
    - Short segments with visual hints
    - Built-in pattern interrupts
    """
    logger.info("Generating script for topic: %s", topic.title)

    # In a real system, call LLM here. For now, structured placeholder.
    hook = (
        "In the next few minutes, I'm going to show you ten tiny habits "
        "that quietly rewire your life—without you even noticing."
    )

    raw_segments = [
        (
            "Habit #1: The 2-minute reset. "
            "Anytime you feel overwhelmed, stop and do a 2-minute reset: "
            "deep breath, unclench your jaw, drop your shoulders, and name "
            "one thing you're grateful for."
        ),
        (
            "Habit #2: The 10-step walk. "
            "Before you open your phone in the morning, take just ten slow "
            "steps and notice three details in your environment."
        ),
        (
            "Habit #3: The friction delete. "
            "Pick one tiny annoyance in your day—like a messy desk or "
            "cluttered app screen—and remove it completely."
        ),
        (
            "Habit #4: The 1-line journal. "
            "Every night, write just one sentence: 'Today was better when…'"
        ),
        (
            "Habit #5: The micro-yes. "
            "Instead of saying 'I'll start tomorrow', say 'I'll do 60 seconds "
            "right now'—and actually do it."
        ),
        (
            "Habit #6: The no-notification block. "
            "Give yourself one 25-minute block with all notifications off."
        ),
        (
            "Habit #7: The future-you check. "
            "Before any decision, ask: 'Will future me thank me for this?'"
        ),
        (
            "Habit #8: The one-message rule. "
            "If someone crosses your mind, send them one kind message."
        ),
        (
            "Habit #9: The tiny upgrade. "
            "Once a week, upgrade one small thing you use daily."
        ),
        (
            "Habit #10: The 5-second pause. "
            "Before reacting, count down from five in your head."
        ),
        (
            "If you pick just one of these habits and actually stick with it "
            "for 30 days, your life will feel different in a way that's hard "
            "to explain—but impossible to ignore."
        ),
    ]

    segments: List[ScriptSegment] = []
    current_time = 0.0
    index = 0

    # Hook segment
    hook_duration = 4.0
    segments.append(
        ScriptSegment(
            index=index,
            start_sec=current_time,
            end_sec=current_time + hook_duration,
            text=hook,
            visual_hint="Fast cuts of people changing small habits, bold text on screen",
        )
    )
    current_time += hook_duration
    index += 1

    # Main segments
    avg_segment_duration = 8.0  # seconds
    visual_hints = [
        "Close-up of phone, timer, breathing overlay",
        "Morning light, slow walking shots, nature b-roll",
        "Desk cleanup timelapse, before/after shots",
        "Handwriting close-up, cozy night scene",
        "Person doing quick workout, timer overlay",
        "Laptop closed, focus shot, deep work b-roll",
        "Split-screen: present self vs future self",
        "Messaging app close-up, smile reactions",
        "Upgraded workspace, small product shots",
        "Person pausing before replying, calm face",
        "Montage of all habits, uplifting music",
    ]

    for raw_text in raw_segments:
        duration = avg_segment_duration
        segments.append(
            ScriptSegment(
                index=index,
                start_sec=current_time,
                end_sec=current_time + duration,
                text=raw_text,
                visual_hint=visual_hints[min(index, len(visual_hints) - 1)],
            )
        )
        current_time += duration
        index += 1

    script = Script(
        topic_id=topic.id,
        title=topic.title,
        hook=hook,
        segments=segments,
        estimated_duration_sec=current_time,
    )

    logger.info(
        "Generated script with %d segments, est. duration=%.1fs",
        len(script.segments),
        script.estimated_duration_sec,
    )
    return script


# =========================
# Voiceover generation
# =========================

def generate_voiceover(
    config: PipelineConfig,
    script: Script,
    work_dir: str,
) -> List[VoiceoverSegment]:
    """
    Generate per-segment voiceover.
    In a real system, this would call a TTS provider.
    Here we just simulate paths and timings.
    """
    logger.info("Generating voiceover segments...")
    vo_dir = os.path.join(work_dir, "voiceover")
    ensure_dir(vo_dir)

    segments: List[VoiceoverSegment] = []
    for seg in script.segments:
        audio_filename = f"vo_segment_{seg.index:03d}.wav"
        audio_path = os.path.join(vo_dir, audio_filename)

        # Placeholder: in real code, call TTS and save to audio_path
        # e.g., tts_client.synthesize(seg.text, voice=config.tts_voice, out=audio_path)
        with open(audio_path, "wb") as f:
            f.write(b"FAKE_WAV_DATA")  # placeholder

        segments.append(
            VoiceoverSegment(
                index=seg.index,
                audio_path=audio_path,
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
            )
        )

    logger.info("Generated %d voiceover segments", len(segments))
    return segments


# =========================
# Visual asset generation
# =========================

def generate_visuals(
    config: PipelineConfig,
    script: Script,
    work_dir: str,
) -> List[VisualAsset]:
    """
    Generate or select visuals per segment.
    In a real system, this might:
    - Query stock libraries
    - Generate AI images
    - Pull from a curated B-roll library
    """
    logger.info("Generating visual assets...")
    vis_dir = os.path.join(work_dir, "visuals")
    ensure_dir(vis_dir)

    assets: List[VisualAsset] = []
    for seg in script.segments:
        asset_filename = f"visual_segment_{seg.index:03d}.mp4"
        asset_path = os.path.join(vis_dir, asset_filename)

        # Placeholder: in real code, generate or copy a clip here
        with open(asset_path, "wb") as f:
            f.write(b"FAKE_VIDEO_DATA")  # placeholder

        assets.append(
            VisualAsset(
                index=seg.index,
                type="broll",
                path=asset_path,
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                metadata={
                    "hint": seg.visual_hint,
                    "resolution": config.video_resolution,
                    "fps": config.fps,
                },
            )
        )

    logger.info("Generated %d visual assets", len(assets))
    return assets


# =========================
# Video assembly
# =========================

def assemble_video(
    config: PipelineConfig,
    script: Script,
    voiceover_segments: List[VoiceoverSegment],
    visual_assets: List[VisualAsset],
    work_dir: str,
) -> AssembledVideo:
    """
    Assemble final video from voiceover + visuals.
    In a real system, this would use ffmpeg or a video editing library.
    """
    logger.info("Assembling final video...")
    out_dir = os.path.join(work_dir, "final")
    ensure_dir(out_dir)

    final_video_path = os.path.join(out_dir, "final_video.mp4")

    # Placeholder: in real code, build a timeline and render via ffmpeg
    with open(final_video_path, "wb") as f:
        f.write(b"FAKE_FINAL_VIDEO")  # placeholder

    video = AssembledVideo(
        video_path=final_video_path,
        duration_sec=script.estimated_duration_sec,
        metadata={
            "title": script.title,
            "topic_id": script.topic_id,
            "segments": len(script.segments),
            "resolution": config.video_resolution,
            "fps": config.fps,
        },
    )

    logger.info(
        "Assembled video at %s (duration=%.1fs)",
        video.video_path,
        video.duration_sec,
    )
    return video


# =========================
# Quality evaluation
# =========================

def evaluate_quality(
    config: PipelineConfig,
    script: Script,
    video: AssembledVideo,
) -> QualityReport:
    """
    Heuristic quality evaluator.
    In a real system, this might:
    - Use an LLM to rate hook, pacing, clarity
    - Analyze audio levels and visual cuts
    - Predict retention
    """
    logger.info("Evaluating video quality...")

    issues: List[str] = []
    recommendations: List[str] = []

    duration_min = video.duration_sec / 60.0
    if duration_min < config.target_duration_min:
        issues.append("Video is shorter than target duration.")
        recommendations.append("Add more depth or examples to key habits.")
    if duration_min > config.target_duration_max:
        issues.append("Video is longer than target duration.")
        recommendations.append("Tighten explanations and remove repetition.")

    if len(script.segments) < 8:
        issues.append("Too few segments; pacing may feel slow.")
        recommendations.append("Increase number of short, punchy segments.")

    # Simple heuristic score
    base_score = 0.8
    penalty = 0.0
    penalty += 0.05 * len(issues)
    score = max(0.0, min(1.0, base_score - penalty))

    passes = score >= config.min_quality_score

    if not issues:
        recommendations.append("Script structure and duration look solid. Proceed to publish tests.")

    report = QualityReport(
        score=score,
        issues=issues,
        recommendations=recommendations,
        passes_threshold=passes,
    )

    logger.info(
        "Quality score=%.2f (passes=%s, issues=%d)",
        report.score,
        report.passes_threshold,
        len(report.issues),
    )
    return report


# =========================
# Pipeline orchestration
# =========================

def run_pipeline(config: Optional[PipelineConfig] = None) -> Dict[str, Any]:
    if config is None:
        config = PipelineConfig()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + str(uuid.uuid4())[:8]
    run_root = os.path.join(config.output_root, run_id)
    ensure_dir(run_root)

    logger.info("Starting pipeline run: %s", run_id)

    attempt = 0
    final_report: Optional[QualityReport] = None
    final_video: Optional[AssembledVideo] = None
    final_script: Optional[Script] = None
    topic: Optional[Topic] = None

    while attempt <= config.max_regenerations:
        attempt += 1
        attempt_dir = os.path.join(run_root, f"attempt_{attempt}")
        ensure_dir(attempt_dir)
        logger.info("Attempt %d/%d", attempt, config.max_regenerations + 1)

        topic = select_topic(config)
        script = generate_script(config, topic)
        voiceover_segments = generate_voiceover(config, script, attempt_dir)
        visual_assets = generate_visuals(config, script, attempt_dir)
        video = assemble_video(config, script, voiceover_segments, visual_assets, attempt_dir)
        report = evaluate_quality(config, script, video)

        # Save metadata for this attempt
        meta = {
            "run_id": run_id,
            "attempt": attempt,
            "topic": asdict(topic),
            "script": {
                "title": script.title,
                "estimated_duration_sec": script.estimated_duration_sec,
                "segments": [asdict(s) for s in script.segments],
            },
            "video": asdict(video),
            "quality_report": asdict(report),
        }
        with open(os.path.join(attempt_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        if report.passes_threshold:
            logger.info("Quality threshold met on attempt %d", attempt)
