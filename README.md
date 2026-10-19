# movie-reel-factory

Free, manually triggered renderer for vertical 9:16 Reels from footage you have the right to use. It uses Python and FFmpeg in GitHub Actions and packages MP4s with posting notes as a downloadable artifact. Google Drive upload is optional. It never publishes to Instagram.

## What it does

- Uses the timestamps you choose in clips.json; it does not guess the best scene.
- Crops to 1080×1920, applies subtle contrast/saturation and vignette, adds a title overlay, and fades the video and original audio at the start and end.
- Keeps the source audio when present; adds no voice-over or music.
- Creates one MP4 and matching _posting-notes.txt per configured scene, with your caption, hashtags and music-library search ideas.
- Uploads a GitHub Actions artifact (7-day retention). Optional Drive upload is available after setup below.

Effects do not make copyrighted footage yours or guarantee reach. Use footage and audio you own or are licensed to use. Meta's creator resources emphasize original, meaningful content; small edits to others' material may not qualify for recommendations. See [Instagram Best Practices](https://about.fb.com/news/2024/10/best-practices-education-hub-creators-instagram/) and [recommendation guidelines](https://about.fb.com/news/2020/08/recommendation-guidelines/).

## Run it

1. In **Actions**, select **Render vertical Reels**, then **Run workflow**.
2. Set config_path to clips.json (or another committed JSON config).
3. Paste a direct HTTPS video URL or Google Drive share URL into video_url. The runner must have access; a Drive link needs **Anyone with the link — Viewer** access.
4. When finished, open the run page and download the **reel-package-<run number>** artifact. It contains each MP4 and its posting notes.

GitHub's workflow form cannot accept a local file upload. Never commit movie files. This repository is public, so workflow inputs, logs and artifacts may be visible to others. Use only footage and source links you are comfortable exposing, or make the repository private before running sensitive footage. Restrict or revoke the shared source link after the run.

## Optional Google Drive upload

Make this public repository **private before adding Drive credentials**. GitHub artifact delivery works when Drive upload is off.

In **Settings → Secrets and variables → Actions**, add:

- Secret **RCLONE_CONFIG_CONTENT**: contents of an rclone config with an OAuth-authorized Google Drive remote named drive. Keep its token private; never commit it or paste it into workflow inputs.
- Variable **DRIVE_UPLOAD_ENABLED**: true.
- Variable **DRIVE_DESTINATION**: for example drive:Reels (the folder must be accessible to that Google account).

Disable by removing the secret or changing DRIVE_UPLOAD_ENABLED from true. Limit repository write access because anyone who can alter workflow code could misuse secrets.

## Configure scenes and posting notes

Edit clips.json. Times may be seconds, MM:SS or HH:MM:SS. Each scene becomes a separate Reel. Select the timestamps yourself, then add a short title, caption, relevant hashtags and a scene mood for music search ideas.

Example:

```json
{
  "movie_title": "Example Film",
  "music_mood": "cinematic suspense",
  "hashtags": ["#FilmScene", "#Cinema"],
  "clips": [
    {
      "label": "reel_01",
      "start": "00:42",
      "end": "01:05",
      "title": "The moment everything changes",
      "caption": "What would you have done here?",
      "hashtags": ["#FilmScene", "#MovieMoment", "#Cinema"],
      "music_mood": "dramatic piano tension"
    }
  ]
}
```

Instagram audio trends and availability vary by account, country and day. This workflow has no reliable free public API to determine the current trend for your account. The notes give mood-based search phrases; check Instagram's music picker for a current trending indicator when uploading. The original movie audio stays in the MP4, so check its rights before posting and mute it in Instagram if choosing licensed in-app music.

Limits: 1–20 scenes; each up to 180 seconds; title up to 80 characters; caption up to 2,200 characters; at most 30 hashtags; source up to 5 GB; end times must be within the video duration. Output is 1080×1920 H.264/AAC. FFmpeg needs drawtext and libx264.

Local use requires Python 3.10+ and FFmpeg:

```sh
python reel_renderer.py --video /path/to/authorized-video.mp4 --config clips.json --output-dir reels
```

No Python packages or AI keys are required. GitHub Actions minutes and storage depend on your plan and can change; long, high-resolution movies may exceed runner limits.
