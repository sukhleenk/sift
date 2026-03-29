# Sift

A local ArXiv research digest that runs entirely on your machine. It fetches papers on topics you care about, summarizes them with a local HuggingFace model, clusters them by topic, and delivers a daily digest as a macOS menu bar notification and an in-app reader.

No cloud APIs. No subscriptions. Works offline after the first model download.

Supports macOS (menu bar) and Linux (system tray).

---

## Requirements

- Python 3.11 or later
- pip
- macOS 12+ or Linux x86_64
- 4-16 GB free disk space depending on the model you pick

---

## Installation

```bash
git clone https://github.com/your-username/sift.git
cd sift
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running

```bash
python main.py
```

The first time you run it, a setup wizard opens. It detects your hardware and suggests a model, but you can override it. It asks for your topics, how often you want digests, and how many papers per digest. When you click "Download Models & Start", it pulls the model weights from HuggingFace and launches the app.

After setup, Sift sits in your menu bar. Click "Fetch Now" to run a digest immediately.

---

## Adding and removing topics

Open Preferences from the menu bar icon. Type a topic in the box and click Add, or select one and click Remove. Changes take effect on the next fetch.

---

## Switching models

Open Preferences, change the model dropdown, and save. Sift downloads the new model if it is not already cached.

---

## Login auto-start

### macOS

```bash
cp com.sift.app.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sift.app.plist
```

To stop it from launching at login:
```bash
launchctl unload ~/Library/LaunchAgents/com.sift.app.plist
```

### Linux

```bash
mkdir -p ~/.config/autostart
cp sift.desktop ~/.config/autostart/
```

Edit the `Exec=` line in the file to point to your Python interpreter and `main.py`.

---

## Building for distribution

### macOS DMG

```bash
pip install pyinstaller
brew install create-dmg
bash build_mac.sh
```

Output: `dist/Sift.dmg`. The script also prints optional notarization steps at the end.

### Linux AppImage

```bash
pip install pyinstaller
# install appimagetool from https://github.com/AppImage/AppImageKit/releases
bash build_linux.sh
chmod +x dist/Sift-x86_64.AppImage
```

---

## Model reference

| Hardware | Summarization model | Embedding model |
|---|---|---|
| Apple Silicon 8 GB | sshleifer/distilbart-cnn-6-6 | all-MiniLM-L6-v2 |
| Apple Silicon 16 GB | sshleifer/distilbart-cnn-12-6 | all-MiniLM-L6-v2 |
| Apple Silicon 32 GB+ | facebook/bart-large-cnn | all-mpnet-base-v2 |
| Linux CPU only | sshleifer/distilbart-cnn-6-6 | all-MiniLM-L6-v2 |
| Linux GPU under 8 GB | sshleifer/distilbart-cnn-12-6 | all-MiniLM-L6-v2 |
| Linux GPU 8-16 GB | facebook/bart-large-cnn | all-mpnet-base-v2 |
| Linux GPU 16 GB+ | google/pegasus-large | all-mpnet-base-v2 |

You can override any of these in the wizard or in Preferences at any time.

---

## Project layout

```
sift/
├── main.py
├── app/
│   ├── db.py            # SQLite storage
│   ├── hardware.py      # hardware detection and model selection
│   ├── wizard.py        # first-run setup wizard
│   ├── fetcher.py       # ArXiv API client
│   ├── embedder.py      # sentence-transformers wrapper
│   ├── clusterer.py     # k-means clustering and TF-IDF labeling
│   ├── summarizer.py    # HuggingFace summarization
│   ├── renderer.py      # Jinja2 HTML digest rendering
│   ├── pipeline.py      # fetch/embed/cluster/summarize/render orchestration
│   ├── scheduler.py     # APScheduler digest scheduling
│   ├── menubar.py       # macOS menu bar (rumps)
│   ├── tray_linux.py    # Linux system tray (pystray)
│   ├── preferences.py   # preferences window
│   └── notifier.py      # system notifications
├── templates/
│   └── digest.html.j2   # digest HTML template
├── assets/
│   ├── icon.png
│   └── icon_active.png
├── requirements.txt
├── sift.spec
├── build_mac.sh
├── build_linux.sh
├── com.sift.app.plist
└── sift.desktop
```

---

## Contributing

Contributions are welcome. Some things that would be genuinely useful:

- Better cluster labeling strategies
- Windows support
- More model profiles
- WKWebView native reader panel improvements

Open an issue or pull request on GitHub.

---

## License

MIT
