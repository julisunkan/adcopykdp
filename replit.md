# KDP AdCopy Generator (PWA)

A full-stack web application for generating high-converting Amazon KDP ad copy using Groq AI.

## Stack
- **Backend**: Python Flask + SQLAlchemy
- **Database**: SQLite (database.db)
- **AI**: Groq API (llama3-70b-8192)
- **Scraping**: requests + BeautifulSoup4
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks)

## Social Media Autoposting
- **Connect & Autopost bar** on main page — OAuth popup flow for all 4 platforms
- **Twitter/X**: OAuth 1.0a via requests-oauthlib; posts tweets (280 char limit enforced)
- **Reddit**: OAuth 2.0; posts text submissions with subreddit + title fields
- **Facebook**: OAuth 2.0 Graph API; posts to user's feed
- **Pinterest**: OAuth 2.0 v5 API; creates pins with board selection (boards auto-loaded)
- **Post Modal**: platform picker, quick-select generated copy, Reddit/Pinterest extra fields, char counter for Twitter, error handling, loading state
- **Admin settings**: 8 social credential fields (API key/secret per platform), redirect URIs shown per-platform
- **SocialToken DB model**: tokens stored per session ID; connect/disconnect endpoints per platform
- Tokens stored in `SocialToken` table keyed by Flask `session["sid"]`
- OAuth callbacks return postMessage to opener window then self-close

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
