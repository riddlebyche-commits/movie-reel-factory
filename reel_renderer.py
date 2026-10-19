#!/usr/bin/env python3
"""Render configured video segments as vertical MP4 Reels using FFmpeg."""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

MAX_INPUT_BYTES = 2_000_000_000

def seconds(value, name):
    if isinstance(value, (int, float)) and not isinstance(value, bool): result = float(value)
    elif isinstance(value, str):
        parts=value.strip().split(':')
        if not 1 <= len(parts) <= 3 or not all(re.fullmatch(r'\d+(?:\.\d+)?',p) for p in parts): raise ValueError(f'{name} must be seconds, MM:SS, or HH:MM:SS')
        result=sum(float(part)*60**i for i,part in enumerate(reversed(parts)))
    else: raise ValueError(f'{name} must be a number or timestamp string')
    if result < 0: raise ValueError(f'{name} cannot be negative')
    return result

def load_config(path):
    try: data=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError) as exc: raise ValueError(f'Cannot read JSON config: {exc}') from exc
    clips=data.get('clips') if isinstance(data,dict) else None
    captions=data.get('captions',[]) if isinstance(data,dict) else []
    if not isinstance(clips,list) or not 1 <= len(clips) <= 20: raise ValueError('Config must contain 1 to 20 clips')
    if not isinstance(captions,list) or any(not isinstance(c,str) for c in captions): raise ValueError('captions must be an array of strings')
    result=[]; labels=set()
    for i,clip in enumerate(clips,1):
        if not isinstance(clip,dict): raise ValueError(f'clip {i} must be an object')
        start=seconds(clip.get('start'),f'clip {i} start'); end=seconds(clip.get('end'),f'clip {i} end')
        label=str(clip.get('label') or f'clip_{i:02d}').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',label) or label in labels: raise ValueError(f'Invalid or duplicate clip label: {label!r}')
        if end <= start or end-start > 180: raise ValueError(f'clip {i} must be positive and at most 180 seconds')
        caption=clip.get('caption',captions[(i-1)%len(captions)] if captions else '')
        if not isinstance(caption,str) or len(caption)>240: raise ValueError(f'clip {i} caption must be at most 240 characters')
        result.append((label,start,end,caption)); labels.add(label)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',required=True); parser.add_argument('--config',default='clips.json'); parser.add_argument('--output-dir',default='output')
    args=parser.parse_args()
    try:
        ffmpeg=shutil.which('ffmpeg'); ffprobe=shutil.which('ffprobe')
        if not ffmpeg or not ffprobe: raise ValueError('FFmpeg and ffprobe must be installed')
        video=Path(args.video).resolve()
        if not video.is_file() or not 0 < video.stat().st_size <= MAX_INPUT_BYTES: raise ValueError('Input video missing, empty, or over 2 GB')
        probe=subprocess.run([ffprobe,'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(video)],capture_output=True,text=True,check=True,timeout=30)
        duration=float(probe.stdout.strip()); clips=load_config(args.config)
        if any(end>duration for _,_,end,_ in clips): raise ValueError(f'Clip end exceeds source duration ({duration:.2f}s)')
        out=Path(args.output_dir).resolve(); out.mkdir(parents=True,exist_ok=True); work=out/'.render_work'; work.mkdir(exist_ok=True)
        for label,start,end,caption in clips:
            hook=work/f'{label}_hook.txt'; cap=work/f'{label}_caption.txt'
            hook.write_text(label.replace('_',' '),encoding='utf-8'); cap.write_text(caption,encoding='utf-8')
            vf=('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,'
                f'drawtext=fontcolor=white:fontsize=68:borderw=3:shadowcolor=black:shadowx=2:shadowy=2:textfile={hook.name}:x=(w-text_w)/2:y=h*0.72,'
                f'drawtext=fontcolor=white:fontsize=44:borderw=2:shadowcolor=black:shadowx=2:shadowy=2:textfile={cap.name}:x=(w-text_w)/2:y=h*0.82')
            target=out/f'{label}.mp4'
            cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y','-ss',f'{start:.3f}','-i',str(video),'-t',f'{end-start:.3f}','-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)]
            print(f'Rendering {target.name}'); subprocess.run(cmd,check=True,timeout=1800,cwd=work)
            if not target.is_file() or not target.stat().st_size: raise ValueError(f'No output produced for {label}')
            hook.unlink(missing_ok=True); cap.unlink(missing_ok=True)
        work.rmdir(); print(f'Rendered {len(clips)} Reels to {out}')
    except (ValueError,OSError,subprocess.SubprocessError) as exc: print(f'ERROR: {exc}',file=sys.stderr); return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
