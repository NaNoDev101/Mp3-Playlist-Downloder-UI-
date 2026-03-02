"""
YouTube Playlist MP3 Downloader - Backend v3
Requirements: pip install flask yt-dlp flask-cors
Run: python app.py
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
import uuid
import zipfile
import shutil
import subprocess
import time

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}


# ─────────────────────────────────────────────
#  Fetch playlist tracks (no download)
# ─────────────────────────────────────────────
@app.route("/api/info", methods=["POST"])
def get_info():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if "entries" in info:
            entries = [e for e in info["entries"] if e]
            tracks = []
            for i, e in enumerate(entries):
                tracks.append({
                    "index": i,
                    "id": e.get("id", ""),
                    "title": e.get("title", f"Track {i+1}"),
                    "duration": e.get("duration", 0),
                    "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id','')}",
                    "thumbnail": e.get("thumbnail", ""),
                })
            return jsonify({
                "title": info.get("title", "Playlist"),
                "uploader": info.get("uploader", info.get("channel", "Unknown")),
                "type": "playlist",
                "tracks": tracks,
            })
        else:
            return jsonify({
                "title": info.get("title", "Track"),
                "uploader": info.get("uploader", info.get("channel", "Unknown")),
                "type": "video",
                "tracks": [{
                    "index": 0,
                    "id": info.get("id", ""),
                    "title": info.get("title", "Track"),
                    "duration": info.get("duration", 0),
                    "url": url,
                    "thumbnail": info.get("thumbnail", ""),
                }],
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ─────────────────────────────────────────────
#  Start download for selected tracks
# ─────────────────────────────────────────────
@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.json
    tracks = data.get("tracks", [])   # list of {url, title, index}
    quality = data.get("quality", "medium")

    if not tracks:
        return jsonify({"error": "No tracks selected"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "convert_progress": 0,
        "phase": "download",       # "download" | "convert" | "zip" | "done"
        "downloaded": 0,
        "converted": 0,
        "total": len(tracks),
        "title": data.get("playlist_title", "Playlist"),
        "current_track": "Initializing...",
        "speed": "",
        "eta": "",
    }

    thread = threading.Thread(
        target=download_tracks,
        args=(job_id, tracks, quality),
        daemon=True
    )
    thread.start()
    return jsonify({"job_id": job_id})


def fmt_duration(secs):
    if not secs:
        return ""
    secs = int(secs)
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def download_tracks(job_id, tracks, quality):
    job = jobs[job_id]
    job_dir = os.path.join(DOWNLOAD_DIR, job_id)
    raw_dir = os.path.join(job_dir, "raw")
    mp3_dir = os.path.join(job_dir, "mp3")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(mp3_dir, exist_ok=True)

    bitrate = {"low": "96", "medium": "192", "high": "320"}.get(quality, "192")
    total = len(tracks)

    try:
        # ── Phase 1: Download audio (no conversion yet) ──
        job["phase"] = "download"
        job["status"] = "downloading"

        for i, track in enumerate(tracks):
            job["current_track"] = track["title"]
            job["downloaded"] = i

            def make_hook(track_idx, track_total):
                def hook(d):
                    j = jobs[job_id]
                    if d["status"] == "downloading":
                        downloaded_bytes = d.get("downloaded_bytes", 0)
                        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                        if total_bytes:
                            within = downloaded_bytes / total_bytes
                            j["progress"] = min(int(((track_idx + within) / track_total) * 100), 99)
                        speed = d.get("speed", 0) or 0
                        eta = d.get("eta", 0) or 0
                        if speed:
                            j["speed"] = f"{speed/1024/1024:.1f} MB/s"
                        if eta:
                            mins, secs = divmod(int(eta), 60)
                            j["eta"] = f"{mins}:{secs:02d}" if mins else f"{secs}s"
                return hook

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(raw_dir, f"{i:03d} - %(title)s.%(ext)s"),
                "progress_hooks": [make_hook(i, total)],
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
                "nopostoverwrites": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([track["url"]])

        job["downloaded"] = total
        job["progress"] = 100
        job["speed"] = ""
        job["eta"] = ""

        # ── Phase 2: Convert each file to MP3 with FFmpeg ──
        job["phase"] = "convert"
        job["status"] = "converting"
        job["convert_progress"] = 0

        raw_files = sorted([
            f for f in os.listdir(raw_dir)
            if not f.endswith(".mp3") and not f.endswith(".part")
        ])

        for idx, filename in enumerate(raw_files):
            raw_path = os.path.join(raw_dir, filename)
            base = os.path.splitext(filename)[0]
            mp3_path = os.path.join(mp3_dir, base + ".mp3")

            job["current_track"] = base.split(" - ", 1)[-1] if " - " in base else base
            job["converted"] = idx

            # Get duration for progress calculation
            duration = get_duration(raw_path)

            # Run FFmpeg with progress pipe
            convert_with_progress(job_id, raw_path, mp3_path, bitrate, idx, len(raw_files), duration)

        job["converted"] = len(raw_files)
        job["convert_progress"] = 100

        # ── Phase 3: ZIP ──
        job["phase"] = "zip"
        job["status"] = "zipping"
        job["current_track"] = "Packaging ZIP archive..."

        zip_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.zip")
        mp3_files = [f for f in os.listdir(mp3_dir) if f.endswith(".mp3")]

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(mp3_files):
                zf.write(os.path.join(mp3_dir, f), f)

        shutil.rmtree(job_dir, ignore_errors=True)

        job["status"] = "done"
        job["phase"] = "done"
        job["progress"] = 100
        job["convert_progress"] = 100
        job["zip_path"] = zip_path
        job["track_count"] = len(mp3_files)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        shutil.rmtree(job_dir, ignore_errors=True)


def get_duration(filepath):
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", filepath],
            capture_output=True, text=True, timeout=10
        )
        import json
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("duration"):
                return float(stream["duration"])
    except Exception:
        pass
    return 0


def convert_with_progress(job_id, input_path, output_path, bitrate, track_idx, total_tracks, duration):
    """Run FFmpeg conversion and report progress via progress pipe."""
    job = jobs[job_id]

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", f"{bitrate}k",
        "-progress", "pipe:1",
        "-nostats",
        output_path
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )

        current_time = 0.0
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    ms = int(line.split("=")[1])
                    current_time = ms / 1_000_000  # convert to seconds
                    if duration > 0:
                        track_frac = min(current_time / duration, 1.0)
                    else:
                        track_frac = 0
                    overall = (track_idx + track_frac) / total_tracks
                    job["convert_progress"] = min(int(overall * 100), 99)
                except (ValueError, ZeroDivisionError):
                    pass

        proc.wait()

    except FileNotFoundError:
        # FFmpeg not found — fall back to yt-dlp built-in conversion
        job["current_track"] = f"[ffmpeg not in PATH, using fallback]"
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }],
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_path.replace(".mp3", ".%(ext)s"),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([input_path])
        job["convert_progress"] = int(((track_idx + 1) / total_tracks) * 100)


# ─────────────────────────────────────────────
#  Status & file endpoints
# ─────────────────────────────────────────────
@app.route("/api/status/<job_id>")
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(jobs[job_id])


@app.route("/api/file/<job_id>")
def get_file(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    job = jobs[job_id]
    if job["status"] != "done":
        return jsonify({"error": "Not ready yet"}), 400
    zip_path = job.get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"error": "File missing on server"}), 404

    safe_title = job.get("title", "playlist").replace("/", "-").replace("\\", "-")
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"{safe_title}.zip",
        mimetype="application/zip"
    )


if __name__ == "__main__":
    print("\n🎵  TUNEGRAB Backend v3")
    print("=" * 40)
    print("📦  Install:  pip install flask yt-dlp flask-cors")
    print("🎬  FFmpeg:   https://ffmpeg.org/download.html")
    print("🌐  Running:  http://localhost:5000")
    print("=" * 40 + "\n")
    app.run(debug=False, port=5000, threaded=True)
