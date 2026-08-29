# YouTube Downloader

Interactive Python CLI for downloading YouTube videos with settings that work well for long videos up to 12 hours.

## Features

- Takes the YouTube URL first and guides you through the rest
- Shows available quality choices before download
- Lets you choose `audio + video`, `only video`, or `only audio`
- Checks the video duration before downloading
- Refuses downloads longer than the configured limit
- Resumes interrupted downloads when possible
- Saves to `DEFAULT_OUTPUT_DIR` by default
- Uses `ffmpeg` automatically when available for better quality merging/conversion

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional but recommended:

- Install `ffmpeg` and make sure it is available in your `PATH`
```powershell
winget install Gyan.FFmpeg
```

## Usage

Run the script and follow the prompts:

```powershell
python ytdl.py
```

Interactive flow:

1. Enter the YouTube URL
2. Review the available quality options
3. Choose a quality
4. Choose `audio + video`, `only video`, or `only audio`
5. Download starts automatically into `D:\lappify\Videos`

You can still pass a URL directly:

```powershell
python ytdl.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Raw format list:

```powershell
python ytdl.py "https://www.youtube.com/watch?v=VIDEO_ID" --list-formats
```

Only audio:

```powershell
python ytdl.py "https://www.youtube.com/watch?v=VIDEO_ID" --audio-only
```

Only video:

```powershell
python ytdl.py "https://www.youtube.com/watch?v=VIDEO_ID" --video-only
```

Choose a different output folder:

```powershell
python ytdl.py --output-dir "D:\OtherVideos"
```

Allow a different maximum duration:

```powershell
python ytdl.py "https://www.youtube.com/watch?v=VIDEO_ID" --max-hours 6
```

## Notes

- `yt-dlp` is the core downloader used by this script.
- Some videos may require cookies, login, or may not be downloadable depending on YouTube restrictions.
- If `ffmpeg` is missing, the script still works, but some high-quality formats may not merge automatically.
- `--quality` accepts `best`, `worst`, or a maximum video height like `1080`, `720`, `480`, or `360`.
- `--audio-only` downloads the best available audio stream.
- `--video-only` downloads only the video stream without audio.
