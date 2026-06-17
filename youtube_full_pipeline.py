#!/usr/bin/env python3
"""Backward-compatible entrypoint for older GitHub Actions runs.

Older workflow history called ``python youtube_full_pipeline.py``. The current
production generator lives in ``main.py`` and does not use the previous FFmpeg
concat pipeline, so this shim delegates to the new Weird Facts generator instead
of letting old Actions runs fail on removed code.
"""

from __future__ import annotations

from main import main


if __name__ == "__main__":
    raise SystemExit(main(["--output", "output"]))
