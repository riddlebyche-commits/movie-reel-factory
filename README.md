# movie-reel-factory

Free, manually triggered renderer for making vertical 9:16 MP4 Reels from video footage you have the right to use. It runs Python and FFmpeg in GitHub Actions, then attaches the finished files as a downloadable workflow artifact. It does not publish to Instagram.

## What is in this repository

- `.github/workflows/render-reels.yml`: manual GitHub Actions workflow.
- `reel_renderer.py`: validates clip timing and renders portrait MP4s with a label and optional caption.
- `clips.json`: editable example of clip ranges and captions.
- `.gitignore`: keeps local video and rendered outputs out of Git.

This is a small independent implementation inspired by the capabilities of [goon-git/clip_generator](https://github.com/goon-git/clip_generator). It does not copy that project's code. That upstream project declares an MIT license; this repository contains no upstream assets or sample footage.

## Run it

1. Open the repository on GitHub and select **Actions**. If prompted, enable Actions for the repository.
2. Select **Render vertical Reels** and click **Run workflow**.
3. Set `config_path` to a committed JSON configuration (start with `clips.json`).
4. For `video_url`, paste either a direct HTTPS video download URL or a Google Drive share URL for footage you are authorized to process. Google Drive files must be accessible to the workflow runner; for this workflow, that means setting General access to **Anyone with the link — Viewer**. The run input and Drive URL can appear in Actions logs and run details. Because this repository is public, do not use it with private footage or a sensitive link; use only footage you are comfortable exposing, or make the repository private before running. Never commit movie files to Git.
5. When the run finishes, open the run page, find **Artifacts**, and download `rendered-reels-<run number>`. The ZIP contains one MP4 per configured clip and expires after 7 days.

GitHub's **Run workflow** form does not accept a local file upload. A Google Drive share link works with the workflow's Drive downloader, but it must permit access to the runner. Anyone with repository access may see workflow inputs, logs, and artifacts. This repository is public, so use only footage and links you are comfortable exposing. The workflow does not publish to Instagram or upload to Drive.

## Configure clips

Edit `clips.json` and commit the configuration. Times may be numbers in seconds, `MM:SS`, or `HH:MM:SS`. Each clip has a unique filename-safe `label`, `start`, `end`, and optional `caption`. If a clip has no caption, the renderer cycles through the top-level captions list. Captions are burned into the video. Labels are displayed as the hook text.

```json
{
  "captions": ["A caption for this moment"],
  "clips": [
    {"label": "scene_01", "start": "00:42", "end": "01:05"}
  ]
}
```

Constraints: 1–20 clips, each at most 180 seconds; caption length at most 240 characters; input at most 2 GB; end time must be within the source duration. The renderer outputs 1080×1920 H.264/AAC MP4, centered crop, with audio when present. Keep labels to letters, numbers, underscores, and hyphens.

## Local rendering (optional)

Install Python 3.10+ and FFmpeg (including ffprobe), then run:

```sh
python reel_renderer.py --video /path/to/authorized-video.mp4 --config clips.json --output-dir reels
```

No pip packages or API keys are needed.

## Free-tier limits and privacy

The code and FFmpeg are free. GitHub Actions usage, minutes, and artifact storage depend on your account plan and repository visibility; GitHub can change its quotas. Long or high-resolution movies may exceed the runner time or storage limits. The workflow uses a 90-minute job cap, limits downloads to 2 GB, and retains output artifacts for 7 days. Check the current quotas for your own account before processing large footage. Artifacts are accessible to users with repository access.

The workflow uses standard GitHub-maintained checkout/setup-python and upload-artifact actions pinned to major versions. It only reads repository content and uploads the rendered MP4 as a run artifact; it grants no write permission to repository contents and does not publish or schedule anything externally.
