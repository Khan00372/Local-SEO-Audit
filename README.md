# 🔍 Local SEO Audit Tool

A **free, open-source** web app that runs a comprehensive local SEO audit on any website in seconds — no account required.

![Local SEO Audit Tool Screenshot](https://via.placeholder.com/800x450/18181f/6366f1?text=Local+SEO+Audit+Tool)

---

## ✨ Features

Audits across **10 categories** with **50+ individual checks**:

| Category | What's Checked |
|---|---|
| 🔒 SSL / HTTPS | HTTPS availability, HTTP→HTTPS redirect, certificate expiry |
| 🏷️ Meta Tags | Title length, meta description, viewport, canonical, robots, Open Graph |
| 📋 Structured Data | LocalBusiness JSON-LD schema — name, address, phone, geo, hours |
| 📍 NAP Consistency | Phone & address detection, footer NAP, contact page links |
| 🗺️ Google Signals | Maps embed, Analytics, Search Console verification, GBP links |
| ⚡ Page Speed | Response time, page size, compression, caching, lazy loading, alt text |
| 📱 Mobile | Viewport meta, click-to-call links, touch icons, favicon |
| 📝 Content | H1/H2 tags, word count, internal/external links |
| ⚙️ Technical | robots.txt, sitemap.xml, 404 handling, WWW canonicalization |
| ⭐ Social & Reviews | Social links, Yelp, review schema, visible star ratings |

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.9+
- pip

### Install & Run

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/local-seo-audit.git
cd local-seo-audit

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open your browser at **http://localhost:5000**

---

## 🌐 Deploy to Render (Free)

1. Fork this repo to your GitHub account
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set these values:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
   - **Environment:** Python 3
5. Click **Deploy** — done!

---

## 🌐 Deploy to Heroku

```bash
# Install Heroku CLI, then:
heroku create your-seo-audit-app
git push heroku main
heroku open
```

---

## 🌐 Deploy to Railway

1. Click **Deploy on Railway** or connect your GitHub repo at [railway.app](https://railway.app)
2. Railway auto-detects the Python app and uses the `Procfile`
3. Your app is live in ~2 minutes

---

## 📁 Project Structure

```
local-seo-audit/
├── app.py              # Flask backend — all audit logic
├── requirements.txt    # Python dependencies
├── Procfile            # Gunicorn startup command for deployment
├── README.md
├── templates/
│   └── index.html      # Single-page HTML template
└── static/
    ├── css/
    │   └── style.css   # Dark-mode UI styles
    └── js/
        └── main.js     # Frontend logic & results rendering
```

---

## 🔧 How It Works

1. User enters a URL → frontend POSTs to `/audit`
2. Flask fetches the page and runs 10 parallel audit modules
3. Each module returns items with `pass`, `warn`, or `fail` status
4. A weighted scoring algorithm produces an overall score (0–100) and letter grade
5. Results rendered dynamically in the browser — no page reload

### Audit Module Architecture

Each audit module is a pure function:
```python
def check_something(soup, url, html) -> dict:
    return {
        "name": "Category Name",
        "items": [
            {"label": "Check name", "status": "pass|warn|fail", "detail": "explanation"}
        ]
    }
```

Adding a new module is as simple as writing a function and appending it to the `sections` list in the `/audit` route.

---

## 🤝 Contributing

PRs welcome! Ideas for improvements:
- Add more schema types (FAQ, BreadcrumbList)
- Check Core Web Vitals via PageSpeed API
- Export results as PDF
- Add bulk URL audit mode
- Add historical audit tracking (with a DB)

---

## 📄 License

MIT License — free for personal and commercial use.

---

## ⭐ Support

If this tool helped you, please star the repo!
