# movie-reel-factory

Free, manually triggered renderer for vertical 9:16 Reels from footage you have the right to use. It scans the full source video for visual scene changes, selects candidate moments, renders MP4s and creates posting notes. Outputs are downloadable from GitHub Actions; optional Google Drive upload is available. It never publishes to Instagram.

## What it does

- Scans the complete input video at 1 frame per second for visual scene changes.
- Selects up to 10 short candidate moments (5 by default). Each rendered candidate is up to 20 seconds; this internal render length is not a config field.
- Crops to 1080×1920, applies subtle contrast/saturation and vignette, adds a brief hook overlay, and fades video and original audio at the start and end.
- Keeps source audio when present; adds no voice-over or music.
- Creates one MP4 and matching posting-notes text file per candidate, plus scene-analysis.json with selected source timestamps.
- Uploads a GitHub Actions artifact (7-day retention). Optional Drive upload is described below.

Automatic scene-change detection does not understand story meaning, dialogue, or whether a moment is compelling. It ranks busy visual moments and spreads candidates; review the videos and timestamps before posting. Effects cannot make copyrighted footage yours or guarantee reach. Use footage and audio you own or are licensed to use. See Meta's [Instagram Best Practices](https://about.fb.com/news/2024/10/best-practices-education-hub-creators-instagram/) and [recommendation guidelines](https://about.fb.com/news/2020/08/recommendation-guidelines/).

## Run it

1. In **Actions**, select **Render vertical Reels**, then **Run workflow**.
2. Set **config_path** to `clips.json` (or another committed JSON config).
3. Paste an HTTPS download URL or Google Drive share URL into **video_url**. The runner must be able to access it; a Drive file must allow **Anyone with the link — Viewer**.
4. When the run finishes, open its page and download the **reel-package-<run number>** artifact. It contains MP4s, posting notes and the timestamp report.

The workflow form cannot receive a local file upload. Never commit movie files. For sensitive footage, make the repository private and use a private, short-lived transfer link that the runner can access; avoid public Drive links. The workflow input and logs may be visible to repository users, so do not paste credentials or long-lived private links. GitHub Actions artifacts are also accessible to people with repository access.

## Configure the run

Edit `clips.json`. It contains no start/end times and no clip-duration setting. The full source is scanned; candidate cut points and source ranges are chosen automatically.

```json
{
  "movie_title": "Example Film",
  "candidate_count": 5,
  "hook": "Why this moment stays with you",
  "content_keywords": ["cinematic film moment", "tense confrontation"],
  "hashtags": ["#FilmScene", "#Cinema", "#MovieMoment"],
  "music_mood": "cinematic suspense"
}
```

- **movie_title**: required, up to 120 characters.
- **candidate_count**: optional, 1–10; defaults to 5.
- **hook**: optional short on-video opening line, up to 80 characters.
- **content_keywords**: optional, up to five short phrases used in caption drafts.
- **hashtags**: optional, up to five relevant tags.
- **music_mood**: optional mood phrase for a search idea in the notes.

The captions are editable templates using the title, hook and keywords, not AI-written scene descriptions. Music notes suggest a search phrase only; there is no reliable free API here that can identify what is trending in your Instagram account, region and upload day. Check Instagram's music picker and choose an eligible track yourself. The source audio remains in the video. If you add licensed in-app music, check whether the original audio should be muted.

## Optional Google Drive upload

Make the repository **private before adding Drive credentials**. GitHub artifact delivery works when Drive upload is off.

In **Settings → Secrets and variables → Actions**, add:

- Secret **RCLONE_CONFIG_CONTENT**: contents of an rclone config with an OAuth-authorized Google Drive remote named `drive`. Keep its token private; never commit it or paste it into workflow inputs.
- Variable **DRIVE_UPLOAD_ENABLED**: `true`.
- Variable **DRIVE_DESTINATION**: for example `drive:Reels` (the folder must be accessible to that Google account).

Disable Drive upload by removing the secret or changing the variable from `true`. Limit repository write access because anyone who can alter workflow code could misuse secrets.

## Limits and local use

The source file limit is 5 GB. Full-length video scanning can take hours; GitHub-hosted jobs have a 6-hour maximum and free Actions usage/storage limits depend on repository visibility and account plan. A long or high-resolution source may exceed available time, disk, or free usage. GitHub's current [Actions limits](https://docs.github.com/en/actions/reference/limits) and [usage details](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) can change. Public-repository Actions usage currently has no billable minutes for standard GitHub-hosted runners, but artifact storage and limits still apply; verify your plan before repeated large runs.

Local use requires Python 3.10+ and FFmpeg with `drawtext` and `libx264`:

```sh
python reel_renderer.py --video /path/to/authorized-video.mp4 --config clips.json --output-dir reels
```

No Python packages or AI keys are required for rendering.
