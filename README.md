# Social Media Scraping & Analytics System

An automated web scraping system targeting social media platforms (Instagram, Twitter/X, YouTube) for structured data extraction, enabling downstream analytics and intelligent workflows.

## Architecture

```
invi/
├── main.py              # CLI entry point
├── config.py            # Centralized configuration (.env-based)
├── scrapers/
│   ├── base.py          # Abstract base scraper (stealth browser, retry logic)
│   ├── instagram.py     # Instagram profile & post extraction
│   ├── twitter.py       # Twitter/X search via guest-token API
│   └── youtube.py       # YouTube Data API v3 integration
├── models/
│   └── schemas.py       # Structured data models (ScrapedPost, ScrapedProfile, etc.)
├── storage/
│   └── exporter.py      # Export to JSON, CSV, and MongoDB
├── analytics/
│   └── analyzer.py      # Engagement metrics, sentiment analysis, trend detection
├── scheduler/
│   └── runner.py        # Automated recurring scrape orchestration
└── data/                # Output directory (git-ignored)
```

## Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/Maddy824/invi.git && cd invi

# 2. Create a virtual environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your API keys and target settings
```

## Usage

```bash
# Run a full scrape cycle across all configured platforms
python main.py

# Scrape a single platform
python main.py --platform instagram --target natgeo
python main.py --platform youtube  --target "machine learning"
python main.py --platform twitter  --target "python programming"

# Run on a recurring schedule (interval from .env)
python main.py --schedule
```

## Features

- **Multi-platform scraping** — Instagram, Twitter/X, YouTube with a unified interface
- **Structured data extraction** — Normalized data models for posts, profiles, videos, comments
- **Stealth browsing** — Selenium stealth with proxy support to avoid detection
- **Automated scheduling** — Configurable interval-based recurring scrapes
- **Export pipelines** — JSON, CSV, and MongoDB output
- **Analytics engine** — Engagement rates, sentiment analysis (TextBlob), hashtag trends
- **Rich CLI** — Pretty-printed tables and colored logging via Rich

## Tech Stack

- **Python 3.10+**
- **Selenium + selenium-stealth** — Browser automation
- **requests-html / BeautifulSoup4** — HTTP scraping & HTML parsing
- **Google API Client** — YouTube Data API v3
- **pymongo** — MongoDB integration
- **pandas** — Data manipulation
- **TextBlob** — Sentiment analysis
- **schedule** — Task scheduling
- **Rich** — Terminal UI
