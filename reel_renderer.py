#!/usr/bin/env python3
"""Render the complete source video as one vertical Reel."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_INPUT_BYTES = 5_000_000_000
MIN_SOURCE_SECONDS = 15


def load_config(path):
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON config: {exc}") from exc
    if not isinstance(cfg, dict):
        raise ValueError("Config must be a JSON object")
    title = cfg.get("movie_title")
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise ValueError("movie_title is required and must be at most 120 characters")
    hook = cfg.get("hook", "A moment from " + title.strip())
    mood = cfg.get("music_mood", "")
    keywords = cfg.get("content_keywords", [])
    hashtags = cfg.get("hashtags", [])
    for value, name, limit in [(hook, "hook", 80), (mood, "music_mood", 120)]:
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"{name} must be text up to {limit} characters")
    if not isinstance(keywords, list) or len(keywords) > 5 or any(not isinstance(x, str) or len(x) > 60 for x in keywords):
        raise ValueError("content_keywords must be an array of at most 5 short phrases")
    if not isinstance(hashtags, list) or len(hashtags) > 5:
        raise ValueError("Use no more than 5 relevant hashtags")
    for tag in hashtags:
        if not isinstance(tag, str) or not re.fullmatch(r"#[A-Za-z0-9_]{1,50}", tag.strip()):
            raise ValueError(f"Invalid hashtag: {tag!r}; use #tag format")
    return {"movie_title": title.strip(),
            "hook": hook.strip(), "music_mood": mood.strip(),
            "content_keywords": [x.strip() for x in keywords if x.strip()],
            "hashtags": list(dict.fromkeys(x.strip() for x in hashtags))}



def load_hook_queue(path, run_number):
    if run_number < 1:
        raise ValueError("run_number must be at least 1")
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Cannot read hook queue: {exc}") from exc
    hooks = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not hooks:
        raise ValueError("Hook queue must contain at least one non-empty hook line")
    if any(len(hook) > 80 for hook in hooks):
        raise ValueError("Each hook queue line must be no more than 80 characters")
    return hooks[(run_number - 1) % len(hooks)]


def probe_duration(ffprobe, video):
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                            capture_output=True, text=True, check=True, timeout=30)
    return float(result.stdout.strip())


def render(ffmpeg, ffprobe, video, cfg, hook, output):
    duration = probe_duration(ffprobe, video)
    if duration < MIN_SOURCE_SECONDS:
        raise ValueError(f"Input video must be at least {MIN_SOURCE_SECONDS} seconds long")
    has_audio = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a:0",
                                "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True, check=True, timeout=30).stdout.strip() != ""
    output.mkdir(parents=True, exist_ok=True)
    label = "reel_full"
    length = duration
    fade = min(0.45, length / 4)
    work = output / ".render_work"
    work.mkdir(exist_ok=True)
    title_file = work / f"{label}_hook.txt"
    title_file.write_text(hook, encoding="utf-8")
    vf = ("[0:v]split=2[bgsrc][fgsrc];"
          "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,gblur=sigma=24:steps=2[bg];"
          "[fgsrc]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
          "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,"
          "eq=contrast=1.04:saturation=1.08:brightness=0.005,vignette=PI/5,"
          f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={length-fade:.3f}:d={fade:.3f},"
          "drawtext=font='DejaVu Sans':fontcolor=white:fontsize=58:borderw=3:"
          "bordercolor=black@0.75:shadowcolor=black@0.5:shadowx=2:shadowy=2:"
          f"textfile={title_file.name}:x=(w-text_w)/2:y=120:enable='between(t,0,3)'[v]")
    target = output / f"{label}.mp4"
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(video), "-filter_complex", vf, "-map", "[v]",
           "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-pix_fmt", "yuv420p", "-r", "30"]
    if has_audio:
        cmd += ["-af", f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={length-fade:.3f}:d={fade:.3f}",
                "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(target)]
    print(f"Rendering the full source: 0.0s–{duration:.1f}s ({duration:.1f}s)", flush=True)
    subprocess.run(cmd, check=True, timeout=21600, cwd=work)
    title_file.unlink(missing_ok=True)
    if not target.is_file() or not target.stat().st_size:
        raise ValueError("No output was produced for the full source")
    cover = output / f"{label}_cover.jpg"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{min(1.0, length / 2):.3f}", "-i", str(target),
                    "-frames:v", "1", "-q:v", "2", str(cover)],
                   check=True, timeout=60)
    keyword_text = ", ".join(cfg["content_keywords"])
    caption = (f"{cfg['movie_title']} — {keyword_text}. {hook} Which detail stood out to you?") if keyword_text else (
               f"{cfg['movie_title']} — {hook} Which detail stood out to you?")
    music = (f"Search Instagram audio for {cfg['music_mood']} or {cfg['movie_title']} soundtrack, then choose a currently trending sound that fits the moment.") if cfg["music_mood"] else (
             "In Instagram's music picker, choose a current trending sound that fits this moment.")
    notes = [f"POSTING NOTES — {cfg['movie_title']} / full source",
             f"Suggested keywords: {keyword_text or cfg['movie_title']}",
             f"Full source used: 0.0s–{duration:.1f}s ({duration:.1f}s)",
             "Cover image: " + cover.name, "", "Caption draft:", caption, "",
             "Hashtags:", " ".join(cfg["hashtags"]) or "(Choose up to five highly relevant tags)", "",
             "Instagram music search idea (not a live trend result):", music, "",
             "The complete source audio is retained. No speech, voice-over, or transcription is generated.",
             "Use only footage/audio you have rights to post. The renderer does not judge story meaning or guarantee reach."]
    (output / f"{label}_posting-notes.txt").write_text(chr(10).join(notes) + chr(10), encoding="utf-8")
    report = {"source_duration_seconds": round(duration, 3),
              "minimum_source_seconds": MIN_SOURCE_SECONDS,
              "output": {"label": label, "start_seconds": 0.0,
                         "end_seconds": round(duration, 3),
                         "duration_seconds": round(duration, 3),
                         "video_file": target.name, "cover_file": cover.name,
                         "posting_notes_file": f"{label}_posting-notes.txt"}}
    (output / "render-report.json").write_text(json.dumps(report, indent=2) + chr(10), encoding="utf-8")
    work.rmdir()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--config", default="clips.json")
    parser.add_argument("--output-dir", default="reels")
    parser.add_argument("--hook-queue", default="hooks.txt")
    parser.add_argument("--run-number", type=int, default=1)
    args = parser.parse_args()
    try:
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            raise ValueError("FFmpeg and ffprobe must be installed")
        video = Path(args.video).resolve()
        if not video.is_file() or not 0 < video.stat().st_size <= MAX_INPUT_BYTES:
            raise ValueError("Input video missing, empty, or over 5 GB")
        cfg = load_config(args.config)
        hook = load_hook_queue(args.hook_queue, args.run_number)
        report = render(ffmpeg, ffprobe, video, cfg, hook, Path(args.output_dir).resolve())
        print(f"Rendered the complete source video ({report['source_duration_seconds']:.1f}s)")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

