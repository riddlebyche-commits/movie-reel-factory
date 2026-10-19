#!/usr/bin/env python3
"""Scan a full source video and render candidate vertical Reels."""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_INPUT_BYTES = 5_000_000_000
MAX_CANDIDATES = 10
MIN_CLIP_SECONDS = 7
MAX_CLIP_SECONDS = 20
MIN_GAP_SECONDS = 2


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
    count = cfg.get("candidate_count", 5)
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_CANDIDATES:
        raise ValueError(f"candidate_count must be 1 to {MAX_CANDIDATES}")
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
    return {"movie_title": title.strip(), "candidate_count": count,
            "hook": hook.strip(), "music_mood": mood.strip(),
            "content_keywords": [x.strip() for x in keywords if x.strip()],
            "hashtags": list(dict.fromkeys(x.strip() for x in hashtags))}


def probe_duration(ffprobe, video):
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                            capture_output=True, text=True, check=True, timeout=30)
    return float(result.stdout.strip())


def detect_cuts(ffmpeg, video):
    filters = "fps=1,scale=320:-2,select='gt(scene,0.22)',showinfo"
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-loglevel", "info", "-i", str(video),
           "-vf", filters, "-an", "-f", "null", "-"]
    print("Scanning the full video for scene changes; long movies may take a while...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=21600)
    return sorted({float(x) for x in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", result.stderr)})


def choose_windows(cuts, duration, count):
    """Pick visually busy, variable-length windows with a hard gap between clips."""
    if duration < MIN_CLIP_SECONDS:
        raise ValueError(f"Source video must be at least {MIN_CLIP_SECONDS} seconds long")
    cuts = sorted({float(t) for t in cuts if 0 <= float(t) <= duration})
    max_slots = max(1, int((duration + MIN_GAP_SECONDS) //
                           (MIN_CLIP_SECONDS + MIN_GAP_SECONDS)))
    target_count = min(count, max_slots)
    candidates = []
    for cut in cuts:
        local = [t for t in cuts if max(0, cut - 10) <= t <= min(duration, cut + 10)]
        length = min(MAX_CLIP_SECONDS, MIN_CLIP_SECONDS + max(0, len(local) - 1) * 1.5)
        start = max(0.0, min(duration - length, cut - length / 2))
        end = start + length
        score = sum(start <= t <= end for t in cuts)
        if not any(abs(start - old["start"]) < MIN_CLIP_SECONDS for old in candidates):
            candidates.append({"start": start, "end": end, "scene_changes": score})
    candidates.sort(key=lambda item: (-item["scene_changes"], item["start"]))
    chosen = []
    for item in candidates:
        if all(item["start"] >= old["end"] + MIN_GAP_SECONDS or
               old["start"] >= item["end"] + MIN_GAP_SECONDS for old in chosen):
            chosen.append(item)
            if len(chosen) == target_count:
                break
    if len(chosen) < target_count:
        if not chosen:
            length = min(MAX_CLIP_SECONDS,
                         max(MIN_CLIP_SECONDS,
                             (duration - MIN_GAP_SECONDS * (target_count - 1)) / target_count))
            for i in range(target_count):
                start = i * (length + MIN_GAP_SECONDS)
                if start + length <= duration + 1e-8:
                    chosen.append({"start": start, "end": start + length, "scene_changes": 0})
        else:
            # Fill unused space with minimum-length clips without extending past the source.
            step = 0.5
            slots = int(max(0.0, duration - MIN_CLIP_SECONDS) / step) + 1
            for i in range(slots):
                start = i * step
                item = {"start": start, "end": start + MIN_CLIP_SECONDS,
                        "scene_changes": sum(start <= t <= start + MIN_CLIP_SECONDS for t in cuts)}
                if all(item["start"] >= old["end"] + MIN_GAP_SECONDS or
                       old["start"] >= item["end"] + MIN_GAP_SECONDS for old in chosen):
                    chosen.append(item)
                    if len(chosen) == target_count:
                        break
    return sorted(chosen, key=lambda item: item["start"])


def render(ffmpeg, ffprobe, video, cfg, output):
    duration = probe_duration(ffprobe, video)
    has_audio = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a:0",
                                "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True, check=True, timeout=30).stdout.strip() != ""
    cuts = detect_cuts(ffmpeg, video)
    windows = choose_windows(cuts, duration, cfg["candidate_count"])
    output.mkdir(parents=True, exist_ok=True)
    report = {"source_duration_seconds": round(duration, 3), "scan_rate_fps": 1,
              "detected_scene_change_count": len(cuts), "minimum_gap_seconds": MIN_GAP_SECONDS,
              "selected_candidates": []}
    work = output / ".render_work"
    work.mkdir(exist_ok=True)
    for i, item in enumerate(windows, 1):
        label = f"reel_{i:02d}"
        start, end = item["start"], item["end"]
        length = end - start
        fade = min(0.45, length / 4)
        title_file = work / f"{label}_hook.txt"
        title_file.write_text(cfg["hook"], encoding="utf-8")
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
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}",
               "-i", str(video), "-t", f"{length:.3f}", "-filter_complex", vf, "-map", "[v]",
               "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-pix_fmt", "yuv420p", "-r", "30"]
        if has_audio:
            cmd += ["-af", f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={length-fade:.3f}:d={fade:.3f}",
                    "-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-an"]
        cmd += ["-movflags", "+faststart", str(target)]
        print(f"Rendering {label}: {start:.1f}s–{end:.1f}s ({length:.1f}s)", flush=True)
        subprocess.run(cmd, check=True, timeout=1800, cwd=work)
        title_file.unlink(missing_ok=True)
        if not target.is_file() or not target.stat().st_size:
            raise ValueError(f"No output produced for {label}")
        cover = output / f"{label}_cover.jpg"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", f"{min(1.0, length / 2):.3f}", "-i", str(target),
                        "-frames:v", "1", "-q:v", "2", str(cover)],
                       check=True, timeout=60)
        keyword_text = ", ".join(cfg["content_keywords"])
        caption = (f"{cfg['movie_title']} — {keyword_text}. {cfg['hook']} Which detail stood out to you?") if keyword_text else (
                   f"{cfg['movie_title']} — {cfg['hook']} Which detail stood out to you?")
        music = (f"Search Instagram audio for {cfg['music_mood']} or {cfg['movie_title']} soundtrack, then choose a currently trending sound that fits the moment.") if cfg["music_mood"] else (
                 "In Instagram's music picker, choose a current trending sound that fits this moment.")
        notes = [f"POSTING NOTES — {cfg['movie_title']} / {label}",
                 f"Suggested keywords: {keyword_text or cfg['movie_title']}",
                 f"Detected candidate range: {start:.1f}s–{end:.1f}s ({length:.1f}s; review before posting)",
                 "Cover image: " + cover.name, "", "Caption draft:", caption, "",
                 "Hashtags:", " ".join(cfg["hashtags"]) or "(Choose up to five highly relevant tags)", "",
                 "Instagram music search idea (not a live trend result):", music, "",
                 "The source movie audio is retained. No speech or voice-over is generated.",
                 "Use only footage/audio you have rights to post. Scene changes cannot judge plot meaning or guarantee reach."]
        (output / f"{label}_posting-notes.txt").write_text(chr(10).join(notes) + chr(10), encoding="utf-8")
        report["selected_candidates"].append({"label": label, "start_seconds": round(start, 3),
                                               "end_seconds": round(end, 3), "duration_seconds": round(length, 3),
                                               "scene_changes_in_window": item["scene_changes"]})
    report["detected_cut_times_seconds"] = cuts
    (output / "scene-analysis.json").write_text(json.dumps(report, indent=2) + chr(10), encoding="utf-8")
    work.rmdir()
    return report


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
        cfg = load_config(args.config)
        report = render(ffmpeg, ffprobe, video, cfg, Path(args.output_dir).resolve())
        print(f"Rendered {len(report['selected_candidates'])} candidate Reels; scan found {report['detected_scene_change_count']} scene changes")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
