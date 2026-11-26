# invi

A Python CLI for summarizing social media data and exporting it to JSON and CSV.

## 60-second offline demo

Use Python 3.10–3.13. From the repository directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py --demo
```

Installing dependencies requires an internet connection. The demo itself needs no network,
browser, API keys or `.env` file. It runs the export and analytics pipeline on the
fictional profiles, posts and videos in `fixtures/demo_posts.json`.
Use `.venv\Scripts\activate` instead on Windows.

Sample output (excerpt from the demo):

```text
Offline demo: synthetic data only
Synthetic analytics report
  "total_scrapes": 3,
  "engagement_rate": "10.00%"
  "tweets_collected": 2,
  "videos_collected": 2,
  "total_views": 200,
  "synthetic_demo": true
```

The terminal prints the full report with Rich. The demo creates seven timestamped
files under the ignored `data/` directory: a JSON and CSV file for each platform,
plus `report_demo_<timestamp>_<unique-id>.json`. The report explicitly marks the data as synthetic.
All numbers and names in the demo are made up.

## Platform status

| Platform | Integration | Credentials and limitations |
| --- | --- | --- |
| YouTube | Official YouTube Data API v3 | Bring your own `YOUTUBE_API_KEY`; quota and API access apply. |
| Instagram | Unofficial profile scraping | May break when the site changes; requires browser support for its existing fallback. |
| Twitter/X | Unofficial search integration | May break when the service changes; requires your own `TWITTER_BEARER_TOKEN` and `WEBSCRAPING_AI_KEY`. |

The offline demo, dependency imports and live-mode dispatch with mocked responses
were tested locally. Actual live platform requests were not tested; their
availability is not guaranteed.

## Live usage

**Twitter/X credential sharing:** The integration sends `TWITTER_BEARER_TOKEN`
to the third-party proxy webscraping.ai, along with its proxy API key. The proxy
receives the bearer token in order to forward requests to Twitter/X. Configure
this integration only if you trust the proxy with those credentials; otherwise
leave the Twitter/X targets blank.

Copy `.env.example` to `.env` and set the credentials and targets for the
platforms you intend to use. Leave other platforms' targets blank.

```bash
python main.py --help
python main.py --platform youtube --target "your search query"
python main.py
python main.py --schedule
```

Without arguments, the CLI runs one cycle for configured targets. The
`--schedule` option repeats the cycle at `SCRAPE_INTERVAL_MINUTES` (default 60).
If any target fails, the cycle still attempts all independent targets and saves
a combined report with successful scrape counts, attempted and failed counts,
and details of failed targets. The CLI then exits with a non-zero status, including
in scheduled mode. Successful results are exported using `EXPORT_FORMAT=json`,
`csv` or `both` with unique filenames, and an analytics JSON report is saved.
CSV contains one row per top-level profile, video or post; nested profile posts
and comments are retained in JSON rather than expanded into CSV rows. Formula-like
text is escaped in CSV cells; JSON preserves the original values.

Instagram and Twitter/X HTTP requests use 30-second connection and read timeouts.
Chrome's security sandbox stays enabled by default; set `CHROME_NO_SANDBOX=true`
only if your browser environment requires disabling it.

## What the analytics computes

- Instagram: number of profiles and collected posts, total and average likes,
  and average likes per collected post divided by follower count (percentage).
- Twitter/X: collected post count, total and average likes and reshares.
- YouTube: collected video count, total views and likes, average views, and
  the most-viewed video in the collected results.
- Hashtags: case-insensitive frequency counts across collected posts.
- Sentiment: basic TextBlob polarity over non-empty post captions, with
  average polarity and positive, negative and neutral percentages.

These are summaries of the collected sample, not measurements of an entire
platform or changes over time. Sentiment does not analyze comments or video
descriptions and should not be treated as a reliable measure of public opinion.

## Development

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
```

Tests use synthetic data and do not require credentials or live platform access.
CI installs the dependencies and runs the tests and lint on Python 3.10, 3.11,
3.12 and 3.13.

## Responsible use

Respect platform terms, API quotas and people's privacy. Only collect data you
are permitted to access, use your own API keys, and keep credentials out of
version control.
