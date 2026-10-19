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
4. For `video_url`, use an HTTPS download URL for footage you are authorized to process. The workflow masks it from normal logs. Use only a temporary, read-only link that expires soon; workflow input values remain visible to people who can inspect the run, so do not put credentials or private URLs in a public repository. For real/private footage, make this repository private before running it, or use a private CI runner/storage arrangement. Do not commit the movie to Git.
5. When the run finishes, open the run page, find **Artifacts**, and download `rendered-reels-<run number>`. The ZIP contains one MP4 per configured clip and expires after 7 days.

GitHub's **Run workflow** form does not accept a local file upload. Transfer the input through a temporary HTTPS location you control, then paste its expiring read-only download link. Never use a public movie URL unless you have permission to download and edit it. Keep copyrighted footage out of public repositories, logs, and artifacts shared with people who should not access it.

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
