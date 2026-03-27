# KDP AdCopy Generator (PWA)

A full-stack web application for generating high-converting Amazon KDP ad copy using Groq AI.

## Stack
- **Backend**: Python Flask + SQLAlchemy
- **Database**: SQLite (database.db)
- **AI**: Groq API (llama3-70b-8192)
- **Scraping**: requests + BeautifulSoup4
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks)

## Features
- Amazon product URL scraper (title, description, bullets, image, reviews)
- AI ad copy generation: headlines, hooks, short ads, long ads, keywords
- Platform targeting: Amazon, Facebook, Instagram
- Tone selection: Emotional, Professional, Urgent
- Configurable word counts (short & long ads)
- Export as HTML or ZIP (with product image)
- Copy-to-clipboard for all ad items
- Per-IP daily usage limit
- Admin panel at /admin (session auth)
- Full PWA: manifest.json, service worker, installable

## Project Structure
- `app.py` — Flask app, routes, init logic
- `models.py` — SQLAlchemy models (Request, Setting, Usage, Admin)
- `utils/scraper.py` — Amazon scraper
- `utils/ai.py` — Groq AI integration
- `templates/` — Jinja2 templates
- `static/styles.css` — Stylesheet
- `static/app.js` — Frontend logic + PWA
- `static/manifest.json` — PWA manifest
- `static/service-worker.js` — Offline caching

## Admin
- URL: /admin/login
- Default credentials: admin / admin
- Set Groq API key, daily limit, enable review scraping, custom prompt

## Running
```bash
python3 -m gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```
