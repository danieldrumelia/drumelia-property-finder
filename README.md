# Drumelia Property Finder

Private Drumelia web portal for natural-language property searches.

Team members log in, type a request such as:

```text
renovated beachfront apartments under 5 million
duplex penthouses from 1-3 million with less than 3 bedrooms in Marbella
frontline beach villas under 3.5 million
```

The app scrapes the registered real estate websites, filters the listings, and emails a formatted report to the logged-in user.

## Features

- Private login with one account per team member.
- Natural-language search parsing for property type, location, price, bedrooms, and features.
- Strict matching for important phrases such as `duplex penthouse` and `frontline beach`.
- Playwright scraping with one scraper module per website.
- HTML email reports with Drumelia styling.
- Safe concurrent report limit, configurable with `CUSTOM_REPORT_MAX_CONCURRENT_JOBS`.
- Docker-ready deployment for cloud hosting.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
```

Edit `.env` with your Outlook SMTP credentials and portal users.

## Run Locally

```bash
real-estate-monitor report-portal
```

Open:

```text
http://127.0.0.1:8001
```

## Environment

Important values:

```bash
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=daniel@drumelia.com
EMAIL_PASSWORD=your_outlook_password_or_app_password
EMAIL_FROM=daniel@drumelia.com
EMAIL_USE_TLS=true

WEB_AUTH_ENABLED=true
WEB_USERS=daniel@drumelia.com:1234567,artur@drumelia.com:1234567

CUSTOM_REPORT_MAX_CONCURRENT_JOBS=2
SCRAPER_HEADLESS=true
SCRAPER_TIMEOUT_MS=60000
SCRAPER_MAX_PAGES=0
SCRAPER_RETRIES=4
```

`EMAIL_TO` is not used for custom portal requests. Reports are sent to the email address used to log in.

## Deployment

This app needs a long-running Python/Docker web service because each report launches Playwright browser scraping.

Good fits:

- Render web service
- Railway Docker service
- Fly.io Docker app

Vercel is not ideal for the scraper backend because serverless functions have execution limits and are not designed for long Playwright scraping jobs. A future lightweight frontend could be hosted on Vercel, but the scraper/report backend should run on a container host.

The included `render.yaml` defines a Render web service using the Dockerfile.
