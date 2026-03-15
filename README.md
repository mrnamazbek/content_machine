<div align="center">

# Content Machine

### Automated AI-Powered Content Pipeline

*Discover trends. Generate content. Post automatically.*

---

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![n8n](https://img.shields.io/badge/n8n-EA4B71?style=for-the-badge&logo=n8n&logoColor=white)](https://n8n.io)

</div>

---

## What is this?

An automated pipeline that runs 24/7 and does the work for you:

```
Find Trends → Discover Videos → Download → Edit → Write Caption → Post
```

It finds what's trending, grabs viral short videos, makes them unique,
writes captions with AI, and posts them to TikTok and Instagram —
all on autopilot.

---

## How it works

```
                         ┌─────────────────┐
                         │   CRON / n8n    │
                         │  (every 6 hrs)  │
                         └────────┬────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │                             │
              ┌─────▼─────┐                ┌─────▼─────┐
              │ Perplexity │                │  yt-dlp   │
              │  (trends)  │                │ (search)  │
              └─────┬─────┘                └─────┬─────┘
                    │                             │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Download Video    │
                    │      (yt-dlp)       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Process (FFmpeg)   │
                    │  zoom · contrast ·  │
                    │  saturation · speed  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Generate Caption   │
                    │  OpenAI / Claude    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Upload to Social  │
                    │  TikTok · Instagram │
                    │    (Playwright)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Collect Analytics  │
                    │  views · likes ·    │
                    │  comments · shares  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  AI Strategy Report │
                    │  (daily analysis)   │
                    └─────────────────────┘
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone git@github.com:mrnamazbek/content_machine.git
cd content_machine
cp .env.example .env
```

Edit `.env` — add your API keys and credentials.

### 2. Run with Docker

```bash
docker compose up -d
```

Three services start:
- **PostgreSQL** — database (port 5432)
- **n8n** — workflow automation (port 5678)
- **App** — API + pipeline (port 8000)

### 3. First-time social login

```bash
# Opens a browser — log in manually, press Enter when done
docker compose exec app python main.py login-tiktok
docker compose exec app python main.py login-instagram
```

### 4. Run the pipeline

```bash
docker compose exec app python main.py run-pipeline
```

That's it. Videos will be discovered, processed, and ready to post.

---

## Commands

All commands follow the same simple pattern:

```bash
python main.py <command>
```

| Command | What it does |
|---|---|
| `run-pipeline` | Full pipeline: trends → videos → edit → captions |
| `discover` | Find trending topics via Perplexity AI |
| `find` | Search for viral videos |
| `download` | Download discovered videos |
| `process` | Edit videos with FFmpeg |
| `generate-captions` | Write captions with AI |
| `upload --platform tiktok` | Post to TikTok |
| `upload --platform instagram` | Post to Instagram |
| `collect-analytics` | Gather performance data |
| `optimize` | AI analysis of what works best |
| `login-tiktok` | Save TikTok session |
| `login-instagram` | Save Instagram session |

---

## Project Structure

```
content_machine/
│
├── scrapers/               — Find and download content
│   ├── discover_trends.py     Perplexity API → trending topics
│   ├── find_videos.py         yt-dlp search → viral videos
│   └── download.py            yt-dlp → download to disk
│
├── processing/             — Make videos unique
│   └── edit_video.py          FFmpeg: zoom, contrast, speed
│
├── ai/                     — AI-powered generation
│   ├── generate_caption.py    OpenAI / Claude → captions
│   └── strategy.py            Daily performance analysis
│
├── upload/                 — Post to social media
│   ├── base_uploader.py       Shared Playwright logic
│   ├── upload_tiktok.py       TikTok automation
│   └── upload_instagram.py    Instagram automation
│
├── analytics/              — Track performance
│   └── metrics.py             Scrape views, likes, comments
│
├── database/               — Data storage
│   ├── schema.sql             PostgreSQL tables
│   └── db.py                  Connection pool + queries
│
├── config/                 — Configuration
│   └── settings.py            All settings from .env
│
├── workflows/              — Automation
│   └── n8n_workflow.json      n8n workflow (import to UI)
│
├── main.py                 — CLI (run any step)
├── api_server.py           — FastAPI (for n8n triggers)
├── docker-compose.yml      — Docker setup
├── Dockerfile
├── .env.example            — Environment template
└── DEPLOY.md               — Deployment guide
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11 |
| **API** | FastAPI |
| **Database** | PostgreSQL 16 |
| **AI** | OpenAI GPT-4o-mini, Claude 3.5 Haiku, Perplexity Sonar |
| **Video** | FFmpeg, yt-dlp |
| **Automation** | Playwright, n8n |
| **Deploy** | Docker, Railway |

---

## Content Niches

Pre-configured for:

- **Gym Discipline** — workout motivation, consistency
- **Engineer Life** — daily life of a developer
- **Coding Mindset** — programming focus, deep work
- **Football Motivation** — competitive sports energy

Change niches anytime in `.env`:
```env
NICHES=gym discipline,engineer life,coding mindset,football motivation
```

---

## API Endpoints

The FastAPI server exposes these endpoints for n8n or external tools:

```
GET  /health              → service health check
GET  /status              → pipeline video counts
POST /trigger/discover    → start trend discovery
POST /trigger/find        → find viral videos
POST /trigger/download    → download videos
POST /trigger/process     → process with FFmpeg
POST /trigger/generate    → generate captions
POST /trigger/upload      → upload to platform
POST /trigger/analytics   → collect metrics
POST /trigger/optimize    → run AI strategy
```

Interactive docs at `http://localhost:8000/docs`

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for full Railway deployment guide.

Quick version:
1. Push to GitHub
2. Connect to Railway
3. Add PostgreSQL service
4. Set environment variables
5. Done — auto-deploys on every `git push`

---

## Security

- API keys and passwords live only in `.env` (gitignored)
- Playwright sessions saved locally in `auth/` (gitignored)
- All API calls use retry logic with exponential backoff
- Videos deduplicated by URL (database unique constraint)
- No credentials are ever hardcoded in source code

---

<div align="center">

Built by **Namazbek Bekzhanov**

*Automate the grind. Focus on what matters.*

</div>
