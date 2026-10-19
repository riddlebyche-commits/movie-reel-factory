#!/usr/bin/env python3
"""Render authorized source footage into vertical Reel MP4s and posting notes."""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_INPUT_BYTES = 5_000_000_000
MAX_CLIPS = 20
MAX_CLIP_SECONDS = 180


def seconds(value, name):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
    elif isinstance(value, str):
        parts = value.strip().split(":")
        if not 1 <= len(parts) <= 3 or not all(re.fullmatch(r"\d+(?:\.\d+)?", p) for p in parts):
            raise ValueError(f"{name} must be seconds, MM:SS, or HH:MM:SS")
        result = sum(float(part) * 60**i for i, part in enumerate(reversed(parts)))
    else:
        raise ValueError(f"{name} must be a number or timestamp string")
    if result < 0:
        raise ValueError(f"{name} cannot be negative")
    return result


def field(value, name, limit, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} must be at most {limit} characters")
    return value


def tags(value, name):
    if not isinstance(value, list) or any(not isinstance(tag, str) for tag in value):
        raise ValueError(f"{name} must be an array of hashtag strings")
    result = []
    for tag in value:
        tag = tag.strip().replace(" ", "")
        if not re.fullmatch(r"#[A-Za-z0-9_]{1,50}", tag):
            raise ValueError(f"Invalid hashtag {tag!r}; use #tag format")
        if tag not in result:
            result.append(tag)
    if len(result) > 30:
        raise ValueError(f"{name} may contain at most 30 hashtags")
    return result


def load_config(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON config: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object")
    movie = field(data.get("movie_title", "Untitled film"), "movie_title", 120, True)
    common_tags = tags(data.get("hashtags", []), "hashtags")
    common_mood = field(data.get("music_mood", ""), "music_mood", 120)
    clips = data.get("clips")
    if not isinstance(clips, list) or not 1 <= len(clips) <= MAX_CLIPS:
        raise ValueError(f"Config must contain 1 to {MAX_CLIPS} clips")
    output, labels = [], set()
    for i, clip in enumerate(clips, 1):
        if not isinstance(clip, dict):
            raise ValueError(f"clip {i} must be an object")
        start = seconds(clip.get("start"), f"clip {i} start")
        end = seconds(clip.get("end"), f"clip {i} end")
        label = str(clip.get("label") or f"reel_{i:02d}").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", label) or label in labels:
            raise ValueError(f"Invalid or duplicate clip label: {label!r}")
        if end <= start or end - start > MAX_CLIP_SECONDS:
            raise ValueError(f"clip {i} must be positive and at most {MAX_CLIP_SECONDS} seconds")
        title = field(clip.get("title", label.replace("_", " ")), f"clip {i} title", 80)
        caption = field(clip.get("caption", ""), f"clip {i} caption", 2200)
        clip_tags = tags(clip.get("hashtags", common_tags), f"clip {i} hashtags")
        mood = field(clip.get("music_mood", common_mood), f"clip {i} music_mood", 120)
        output.append({"label": label, "start": start, "end": end, "title": title,
                       "caption": caption, "hashtags": clip_tags, "music_mood": mood})
        labels.add(label)
    return movie, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--config", default="clips.json")
    parser.add_argument("--output-dir", default="reels")
    args = parser.parse_args()
    try:
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            raise ValueError("FFmpeg and ffprobe must be installed")
        video = Path(args.video).resolve()
        if not video.is_file() or not 0 < video.stat().st_size <= MAX_INPUT_BYTES:
            raise ValueError("Input video missing, empty, or over 5 GB")
        probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                               capture_output=True, text=True, check=True, timeout=30)
        duration = float(probe.stdout.strip())
        audio = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a:0",
                                "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True, check=True, timeout=30)
        has_audio = bool(audio.stdout.strip())
        movie, clips = load_config(args.config)
        if any(c["end"] > duration for c in clips):
            raise ValueError(f"A clip end exceeds source duration ({duration:.2f}s)")
        out = Path(args.output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        work = out / ".render_work"
        work.mkdir(exist_ok=True)
        for clip in clips:
            label, start, end = clip["label"], clip["start"], clip["end"]
            length = end - start
            fade = min(0.45, length / 4)
            title_file = work / f"{label}_title.txt"
            title_file.write_text(clip["title"], encoding="utf-8")
            vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
                  "eq=contrast=1.04:saturation=1.08:brightness=0.005,vignette=PI/5,"
                  f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={length-fade:.3f}:d={fade:.3f},"
                  f"drawtext=font='DejaVu Sans':fontcolor=white:fontsize=58:borderw=3:"
                  f"bordercolor=black@0.75:shadowcolor=black@0.5:shadowx=2:shadowy=2:"
                  f"textfile={title_file.name}:x=(w-text_w)/2:y=h*0.72")
            target = out / f"{label}.mp4"
            cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}",
                   "-i", str(video), "-t", f"{length:.3f}", "-vf", vf,
                   "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "23", "-pix_fmt", "yuv420p", "-r", "30"]
            if has_audio:
                cmd += ["-af", f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={length-fade:.3f}:d={fade:.3f}",
                        "-c:a", "aac", "-b:a", "128k"]
            else:
                cmd += ["-an"]
            cmd += ["-movflags", "+faststart", str(target)]
            print(f"Rendering {target.name}")
            subprocess.run(cmd, check=True, timeout=1800, cwd=work)
            if not target.is_file() or not target.stat().st_size:
                raise ValueError(f"No output produced for {label}")
            music = (f"Search Instagram music for: {clip['music_mood']}, {movie} soundtrack, "
                     f"cinematic {clip['music_mood']}") if clip["music_mood"] else (
                     "Check Instagram's music picker for a currently trending sound that fits this scene.")
            notes = [f"POSTING NOTES — {clip['title']}", f"Film/source: {movie}", "",
                     "Caption:", clip["caption"] or f"A moment from {movie}.", "",
                     "Hashtags:", " ".join(clip["hashtags"]) or "(Add a few relevant tags)", "",
                     "Instagram music search ideas (not live trend rankings):", music, "",
                     "Use only footage/audio you have rights to. Effects do not guarantee recommendation reach."]
            (out / f"{label}_posting-notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")
            title_file.unlink(missing_ok=True)
        work.rmdir()
        print(f"Rendered {len(clips)} Reels and posting notes to {out}")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
