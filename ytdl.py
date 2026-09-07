from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any, cast

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


MAX_DURATION_SECONDS = 12 * 60 * 60
DEFAULT_OUTPUT_DIR = Path(r"D:\DL Videos")
DEFAULT_OUTPUT_TEMPLATE = "%(title).200B [%(id)s].%(ext)s"


@dataclass(slots=True)
class DownloadConfig:
    url: str
    output_dir: Path
    audio_only: bool
    video_only: bool
    quality: str
    list_formats: bool
    max_duration_seconds: int


@dataclass(slots=True)
class QualityOption:
    value: str
    label: str
    has_progressive: bool
    has_video_only: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download a YouTube video with settings that work well for long videos "
            "up to 12 hours."
        )
    )
    parser.add_argument("url", nargs="?", help="YouTube video URL to download")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=(
            "Directory where the downloaded file will be saved "
            f"(default: {DEFAULT_OUTPUT_DIR})"
        ),
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Download audio only and convert it to MP3 when ffmpeg is available",
    )
    parser.add_argument(
        "--video-only",
        action="store_true",
        help="Download only the video stream without audio",
    )
    parser.add_argument(
        "--quality",
        default=None,
        help=(
            "Preferred video quality: best, worst, or a maximum height like "
            "2160, 1440, 1080, 720, 480, or 360"
        ),
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="Show the available formats for the video and exit",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=12.0,
        help="Maximum allowed video duration in hours (default: 12)",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> DownloadConfig:
    url = args.url or input("Enter the YouTube video URL: ").strip()
    if not url:
        raise ValueError("A YouTube URL is required.")

    if args.audio_only and args.video_only:
        raise ValueError("Choose only one of --audio-only or --video-only.")

    max_hours = max(args.max_hours, 0.0)
    max_duration_seconds = int(max_hours * 60 * 60)
    if max_duration_seconds <= 0:
        raise ValueError("--max-hours must be greater than 0.")

    quality = normalize_quality(args.quality) if args.quality else "best"
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    return DownloadConfig(
        url=url,
        output_dir=output_dir,
        audio_only=args.audio_only,
        video_only=args.video_only,
        quality=quality,
        list_formats=args.list_formats,
        max_duration_seconds=max_duration_seconds,
    )


def has_ffmpeg() -> bool:
    return find_ffmpeg_dir() is not None


def find_ffmpeg_dir() -> Path | None:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return Path(ffmpeg_path).resolve().parent

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None

    winget_packages_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
    if not winget_packages_dir.exists():
        return None

    matches = sorted(winget_packages_dir.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))
    if matches:
        return matches[-1].resolve().parent

    return None


def format_seconds(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_quality(raw_quality: str) -> str:
    quality = raw_quality.strip().lower()
    if quality in {"best", "worst"}:
        return quality
    if quality.isdigit():
        return quality
    raise ValueError(
        "--quality must be 'best', 'worst', or a numeric height like 1080 or 720."
    )


def prompt_choice(prompt: str, min_value: int, max_value: int) -> int:
    while True:
        answer = input(prompt).strip()
        if answer.isdigit():
            choice = int(answer)
            if min_value <= choice <= max_value:
                return choice
        print(f"Please enter a number between {min_value} and {max_value}.")


def progress_hook(status: dict[str, Any]) -> None:
    if status["status"] == "downloading":
        downloaded = status.get("downloaded_bytes", 0)
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        speed = status.get("speed")
        eta = status.get("eta")

        if total:
            percent = downloaded / total * 100
            total_mb = total / (1024 * 1024)
            downloaded_mb = downloaded / (1024 * 1024)
            line = f"\rDownloading: {percent:6.2f}% ({downloaded_mb:,.1f}/{total_mb:,.1f} MB)"
        else:
            downloaded_mb = downloaded / (1024 * 1024)
            line = f"\rDownloading: {downloaded_mb:,.1f} MB"

        if speed:
            line += f" | {speed / (1024 * 1024):.2f} MB/s"
        if eta is not None:
            line += f" | ETA {eta}s"

        sys.stdout.write(line)
        sys.stdout.flush()

    elif status["status"] == "finished":
        filename = status.get("filename", "output file")
        sys.stdout.write(f"\nDownload complete: {filename}\n")
        sys.stdout.flush()


def postprocessor_hook(status: dict[str, Any]) -> None:
    postprocessor = status.get("postprocessor")
    info = status.get("info_dict") or {}
    filepath = info.get("filepath") or "output file"

    if postprocessor == "Merger":
        if status["status"] == "started":
            print(f"Merging audio and video with ffmpeg: {filepath}")
        elif status["status"] == "finished":
            print(f"Merge finished: {filepath}")
    elif postprocessor == "ExtractAudio":
        if status["status"] == "started":
            print(f"Converting audio with ffmpeg: {filepath}")
        elif status["status"] == "finished":
            print(f"Audio conversion finished: {filepath}")


def inspect_video(url: str) -> dict[str, Any]:
    inspect_options: dict[str, Any] = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    with YoutubeDL(cast(Any, inspect_options)) as ydl:
        return cast(dict[str, Any], ydl.extract_info(url, download=False))


def list_video_formats(url: str) -> None:
    with YoutubeDL({"listformats": True, "noplaylist": True}) as ydl:
        ydl.download([url])


def is_progressive_format(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in {None, "none"} and fmt.get("acodec") not in {
        None,
        "none",
    }


def is_video_only_format(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in {None, "none"} and fmt.get("acodec") in {
        None,
        "none",
    }


def collect_quality_options(info: dict[str, Any]) -> list[QualityOption]:
    quality_map: dict[int, QualityOption] = {}

    for fmt in info.get("formats") or []:
        height = fmt.get("height")
        if not isinstance(height, int):
            continue

        option = quality_map.get(
            height,
            QualityOption(
                value=str(height),
                label=f"{height}p",
                has_progressive=False,
                has_video_only=False,
            ),
        )
        option.has_progressive = option.has_progressive or is_progressive_format(fmt)
        option.has_video_only = option.has_video_only or is_video_only_format(fmt)
        quality_map[height] = option

    options = [quality_map[key] for key in sorted(quality_map, reverse=True)]
    options.insert(
        0,
        QualityOption(
            value="best",
            label="Best available",
            has_progressive=True,
            has_video_only=True,
        ),
    )
    return options


def quality_status_label(option: QualityOption, ffmpeg_available: bool) -> str:
    if option.value == "best":
        return "automatic selection"
    if option.has_progressive and option.has_video_only:
        return "audio+video and video-only available"
    if option.has_progressive:
        return "audio+video available"
    if option.has_video_only:
        if ffmpeg_available:
            return "video-only available, audio can be merged"
        return "video-only available, needs ffmpeg for audio+video merge"
    return "availability unknown"


def prompt_for_quality(info: dict[str, Any], ffmpeg_available: bool) -> str:
    options = collect_quality_options(info)

    print("\nAvailable qualities:")
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option.label} - {quality_status_label(option, ffmpeg_available)}")

    choice = prompt_choice("Choose a quality number: ", 1, len(options))
    selected = options[choice - 1]
    print(f"Selected quality: {selected.label}")
    return selected.value


def prompt_for_download_mode() -> tuple[bool, bool]:
    print("\nDownload type:")
    print("1. Audio + video")
    print("2. Only video")
    print("3. Only audio")

    choice = prompt_choice("Choose a download type number: ", 1, 3)
    if choice == 1:
        print("Selected mode: Audio + video")
        return False, False
    if choice == 2:
        print("Selected mode: Only video")
        return False, True

    print("Selected mode: Only audio")
    return True, False


def describe_quality_fallback(
    info: dict[str, Any], requested_quality: str, ffmpeg_available: bool
) -> str | None:
    if ffmpeg_available or requested_quality in {"best", "worst"}:
        return None

    target_height = int(requested_quality)
    formats = info.get("formats") or []

    progressive_heights = {
        int(fmt["height"])
        for fmt in formats
        if fmt.get("height") and is_progressive_format(fmt)
    }
    video_only_heights = {
        int(fmt["height"])
        for fmt in formats
        if fmt.get("height") and is_video_only_format(fmt)
    }

    if target_height in video_only_heights and target_height not in progressive_heights:
        lower_progressive = [height for height in progressive_heights if height <= target_height]
        if lower_progressive:
            fallback_height = max(lower_progressive)
            return (
                f"{target_height}p is available only as a video-only stream for this video. "
                f"Because ffmpeg is not installed, yt-dlp cannot merge that stream with audio, "
                f"so it falls back to the best combined video+audio format, which is {fallback_height}p."
            )
        return (
            f"{target_height}p is available only as a video-only stream for this video. "
            "Because ffmpeg is not installed, yt-dlp cannot merge it with audio."
        )

    return None


def apply_interactive_choices(
    config: DownloadConfig, info: dict[str, Any]
) -> DownloadConfig:
    if config.list_formats:
        return config

    if config.audio_only:
        if not config.video_only:
            print("\nSelected mode: Only audio")
        return config

    if config.quality != "best" and (config.audio_only or config.video_only):
        return config

    ffmpeg_available = find_ffmpeg_dir() is not None

    if config.quality == "best":
        config.quality = prompt_for_quality(info, ffmpeg_available)

    if not config.audio_only and not config.video_only:
        audio_only, video_only = prompt_for_download_mode()
        config.audio_only = audio_only
        config.video_only = video_only

    return config


def build_download_options(config: DownloadConfig) -> dict[str, Any]:
    ffmpeg_dir = find_ffmpeg_dir()
    ffmpeg_available = ffmpeg_dir is not None

    options: dict[str, Any] = {
        "outtmpl": str(config.output_dir / DEFAULT_OUTPUT_TEMPLATE),
        "noplaylist": True,
        "continuedl": True,
        "retries": 20,
        "fragment_retries": 20,
        "file_access_retries": 5,
        "extractor_retries": 5,
        "socket_timeout": 120,
        "http_chunk_size": 10 * 1024 * 1024,
        "concurrent_fragment_downloads": 4,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "quiet": True,
        "no_warnings": False,
        "nopart": False,
        "overwrites": False,
    }

    if ffmpeg_dir:
        options["ffmpeg_location"] = str(ffmpeg_dir)

    if config.audio_only:
        options["format"] = "bestaudio/best"
        if ffmpeg_available:
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        return options

    options["format"] = choose_video_format(
        config.quality,
        ffmpeg_available,
        video_only=config.video_only,
    )
    if ffmpeg_available and not config.video_only:
        options["merge_output_format"] = "mp4"

    return options


def choose_video_format(
    quality: str, ffmpeg_available: bool, video_only: bool = False
) -> str:
    if quality == "best":
        if video_only:
            return "bestvideo/best"
        if ffmpeg_available:
            return "bv*+ba/b"
        return "best[ext=mp4]/best"

    if quality == "worst":
        if video_only:
            return "worstvideo/worst"
        if ffmpeg_available:
            return "wv*+wa/w"
        return "worst"

    max_height = int(quality)
    if video_only:
        return f"bestvideo[height<={max_height}]/best[height<={max_height}]"
    if ffmpeg_available:
        return (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        )
    return f"best[height<={max_height}][ext=mp4]/best[height<={max_height}]/best"


def download_video(config: DownloadConfig) -> Path | None:
    info = inspect_video(config.url)
    duration = info.get("duration")
    ffmpeg_dir = find_ffmpeg_dir()
    ffmpeg_available = ffmpeg_dir is not None

    if duration and duration > config.max_duration_seconds:
        allowed = format_seconds(config.max_duration_seconds)
        actual = format_seconds(duration)
        raise ValueError(
            f"Video is longer than the allowed limit. Allowed: {allowed}, actual: {actual}."
        )

    if not ffmpeg_available:
        print(
            "ffmpeg was not found in PATH. The downloader will use a simpler format "
            "selection, which may reduce quality for some videos."
        )
    elif shutil.which("ffmpeg") is None:
        print(f"Using ffmpeg from: {ffmpeg_dir}")

    fallback_reason = None
    if not config.audio_only and not config.video_only:
        fallback_reason = describe_quality_fallback(info, config.quality, ffmpeg_available)
    if fallback_reason:
        print(f"Note: {fallback_reason}")

    if config.list_formats:
        print("\nAvailable formats:\n")
        list_video_formats(config.url)
        return None

    if config.audio_only:
        print("Selected quality: audio only mode uses the best available audio stream")
    elif config.video_only:
        print(f"Selected quality: {config.quality} (video only)")
    else:
        print(f"Selected quality: {config.quality} (audio + video)")

    options = build_download_options(config)
    # yt-dlp's type stubs expose a narrower internal params type than the
    # public options mapping used by its Python API.
    with YoutubeDL(cast(Any, options)) as ydl:
        result = ydl.extract_info(config.url, download=True)

        requested_downloads = result.get("requested_downloads") or []
        for item in requested_downloads:
            filepath = item.get("filepath")
            if filepath:
                return Path(filepath)

        direct_filepath = result.get("filepath")
        if direct_filepath:
            return Path(direct_filepath)

    return None


def main() -> int:
    try:
        config = build_config(parse_args())
        info = inspect_video(config.url)
        print(f"\nTitle: {info.get('title', 'Unknown title')}")
        duration = info.get("duration")
        if duration:
            print(f"Duration: {format_seconds(duration)}")
        config = apply_interactive_choices(config, info)
        saved_file = download_video(config)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    except DownloadError as exc:
        print(f"Download failed: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nDownload cancelled by user.")
        return 130

    if saved_file:
        print(f"Saved to: {saved_file}")
    else:
        print(f"Saved to folder: {config.output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
