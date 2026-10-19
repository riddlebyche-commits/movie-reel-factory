# movie-reel-factory

Free, manually triggered renderer for one complete input video, exported as a vertical 9:16 Reel. It does not split the source into short cuts. It rejects videos shorter than 15 seconds, but has no configured maximum duration. Outputs are downloadable from GitHub Actions; optional Google Drive upload is supported. It never publishes to Instagram.

## What it does

- Uses the whole source from first frame to last; rejects input shorter than 15 seconds.
- Selects an on-screen hook from `hooks.txt` based on the workflow run number. Each non-empty, non-comment line is used in order; after the last line, the queue cycles back to the first. The hook appears for the first three seconds and is copied into posting notes.
- Fits the full frame over a softly blurred vertical background, adds subtle visual adjustments and fades the video and original audio at the beginning and end.
- Keeps original audio when present; adds no voice-over, music or transcription.
- Creates `reel_full.mp4`, a matching JPG cover, posting notes and `render-report.json` with the full source duration.
- Uploads a GitHub Actions artifact with 7-day retention. Optional Drive upload is described below.

The renderer does not judge story meaning or guarantee reach. Use only footage and audio you have rights to post. Review the final output before posting.

## Run it

1. In **Actions**, select **Render vertical Reels**, then **Run workflow**.
2. Set **config_path** to `clips.json` (or another repository JSON config).
3. Paste an HTTPS download URL or Google Drive share URL into **video_url**. The runner must be able to access it.
4. When the run finishes, open the run page and download the `reel-package-<run number>` artifact. It contains the complete vertical MP4, cover image, posting notes and report.

The workflow form cannot receive a local file upload. Never commit movie files. For sensitive footage, use a private, short-lived transfer link that the runner can access. The workflow input and logs may be visible to repository users, so do not paste credentials or long-lived private links. Artifacts are accessible to people with repository access.

## Configure

Edit `clips.json` for title and posting metadata. There are no clip start/end, duration or hook fields in this JSON.

Edit `hooks.txt` to set the on-video hook queue. Put one hook per line (maximum 80 characters). Blank lines and lines starting with `#` are ignored. Run 1 uses the first hook, run 2 the second, and so on; after the final hook it cycles to the first. A rerun uses the same run number and therefore the same hook.

- **movie_title**: required, up to 120 characters.
- **content_keywords**: optional, up to five short phrases used in caption drafts.
- **hashtags**: optional, up to five relevant tags.
- **music_mood**: optional phrase to guide a search idea in the notes.

Captions are editable templates, not AI-written scene descriptions. Music notes suggest a search phrase, not a live trend result; choose a currently available track yourself in Instagram. The complete source audio remains in the rendered video.

## Optional Google Drive upload

Make the repository **private before adding Drive credentials**. GitHub artifact delivery works when Drive upload is off.

In **Settings → Secrets and variables → Actions**, add:

- Secret **RCLONE_CONFIG_CONTENT**: contents of an rclone config with an OAuth-authorized Google Drive remote named drive. Keep its token private; never commit it or paste it into workflow inputs.
- Variable **DRIVE_UPLOAD_ENABLED**: `true`.
- Variable **DRIVE_DESTINATION**: for example `drive:Reels`.

Disable Drive upload by changing the variable or removing the secret. Limit repository write access because workflow changes can use configured secrets.

## Limits and local use

There is no configured maximum duration. Practical limits still apply: source files are capped at 5 GB, the GitHub-hosted job has a 6-hour timeout, and runner disk, Actions usage and artifact storage depend on your plan and repository settings. Long or high-resolution video may exceed time, disk or free usage limits. See GitHub's current [Actions limits](https://docs.github.com/en/actions/reference/limits) and [usage details](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions).

Local use requires Python 3.10+ and FFmpeg with `drawtext` and `libx264`:

```sh
python reel_renderer.py --video /path/to/authorized-video.mp4 --config clips.json --hook-queue hooks.txt --run-number 1 --output-dir reels
```

No Python packages or AI keys are required for rendering.

