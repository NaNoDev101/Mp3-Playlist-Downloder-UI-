# 🎵 TuneGrab

> **By [MrNaNo]([(https://github.com/NaNoDev101/)]) — N4N0 Staff**

A clean, self-hosted YouTube playlist & video MP3 downloader with a modern web UI. Paste any YouTube URL, preview your tracks, select what you want, and download a ready-to-use ZIP of MP3s — all from your browser.

---

## ✨ Features

- 🔗 Supports single videos **and** full playlists
- ✅ Selectable track list — download only what you want
- 🎚️ Quality options: Low (96k), Medium (192k), High (320k)
- 📊 Real-time progress — download & conversion phases tracked separately
- 📦 Auto-packages all tracks into a ZIP file
- 🌐 Simple browser UI — no install needed on the client side

---

## 🛠️ Requirements

| Tool | Purpose |
|------|---------|
| Python 3.8+ | Backend runtime |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube audio extraction |
| [FFmpeg](https://ffmpeg.org/download.html) | MP3 conversion |
| Flask + flask-cors | Web server |

---

## 🚀 Setup & Run

### 1. Clone the repo

```bash
git clone https://github.com/MrNaNo/tunegrab.git
cd tunegrab
```

### 2. Install Python dependencies

```bash
pip install flask yt-dlp flask-cors
```

### 3. Install FFmpeg

- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

### 4. Start the backend

```bash
python app.py
```

The API will be running at `http://localhost:5000`

### 5. Open the frontend

Open `index.html` in your browser. That's it!

---

## 📖 Usage

1. Paste a YouTube video or playlist URL into the input box
2. Click **Fetch** — TuneGrab will load all available tracks
3. Select the tracks you want (or select all)
4. Choose your MP3 quality
5. Click **Download** and watch the progress
6. When done, your ZIP will automatically download

---

## 🗂️ Project Structure

```
tunegrab/
├── app.py          # Flask backend — fetching, downloading, converting, zipping
├── index.html      # Frontend UI
├── downloads/      # Temp folder (auto-created, auto-cleaned)
└── README.md
```

---

## ⚙️ API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/info` | POST | Fetch playlist/video metadata |
| `/api/download` | POST | Start a download job |
| `/api/status/<job_id>` | GET | Poll job progress |
| `/api/file/<job_id>` | GET | Download the completed ZIP |

---

## ⚠️ Disclaimer

TuneGrab is intended for **personal use only**. Downloading copyrighted content without permission may violate YouTube's Terms of Service and applicable laws. Only download content you have the right to access.

---

## 👤 Author

**MrNaNo** — N4N0 Staff

> Built for personal use. Use responsibly.

---
