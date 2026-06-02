# Sift

A local ArXiv research digest that runs entirely on your machine. It fetches papers on topics you care about, summarizes them with a local HuggingFace model, clusters them by topic, and delivers a daily digest as a macOS menu bar notification and an in-app reader.

The summarizer works offline after the first model download. You do still need to be online to fetch papers.

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

> **Note:** Running Sift as a Python script (above) is currently more stable and recommended over using the released packaged builds.

The first time you run it, a setup wizard opens. It detects your hardware and suggests a model, but you can override it. It asks for your topics, how often you want digests, and how many papers per digest. When you click "Download Models & Start", it pulls the model weights from HuggingFace and launches the app.

After setup, Sift sits in your menu bar. Click "Fetch Now" to run a digest immediately.

---

## Adding and removing topics

Open Preferences from the menu bar icon. Type a topic in the box and click Add, or select one and click Remove. Changes take effect on the next fetch.

---

## Switching models

Open Preferences, change the model dropdown, and save. Sift downloads the new model if it is not already cached.

---

## ArXiv API limits and rate limiting

Sift fetches papers using the [ArXiv API](https://arxiv.org/help/api/index). ArXiv enforces rate limits on automated requests.

- **Between topics:** Sift waits at least 5 seconds between requests for different topics, in line with ArXiv's terms of service.
- **HTTP 429 (rate limited):** If ArXiv rate limits your IP, Sift will wait 2 minutes and retry, then 5 minutes and retry again. If it is still blocked after that, the fetch for that topic is skipped and an error is logged.
- **Persistent blocks:** ArXiv occasionally blocks IPs for extended periods (hours or more). If you see repeated 429 errors across multiple runs, wait a while before trying again — there is nothing Sift can do to clear an IP-level block. Running too many fetches in a short window is the most common cause.

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

## Contributing

Contributions are welcome. Some things that would be genuinely useful:

- Better cluster labeling strategies
- Windows support
- More model profiles
- WKWebView native reader panel improvements

Open an issue or pull request on GitHub.

---

## License

Apache-2.0 license
