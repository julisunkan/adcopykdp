import os
import json
import zipfile
import hashlib
import io
import requests as req_lib
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    session,
    redirect,
    url_for,
    send_file,
    flash,
)

from models import db, Request, Setting, Usage, Admin
from utils.scraper import scrape_amazon
from utils.ai import generate_ad_copy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kdp-adcopy-secret-2024")

# SQLite database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_setting(key, default=""):
    s = Setting.query.get(key)
    return s.value if s else default


def set_setting(key, value):
    s = Setting.query.get(key)
    if s:
        s.value = value
    else:
        s = Setting(key=key, value=value)
        db.session.add(s)
    db.session.commit()


def get_client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()


def check_usage_limit(ip):
    """Returns True if the IP is under the daily limit."""
    limit = int(get_setting("daily_limit", "10"))
    today = str(date.today())
    usage = Usage.query.filter_by(ip=ip, date=today).first()
    if usage is None:
        return True
    return usage.count < limit


def increment_usage(ip):
    today = str(date.today())
    usage = Usage.query.filter_by(ip=ip, date=today).first()
    if usage:
        usage.count += 1
    else:
        usage = Usage(ip=ip, date=today, count=1)
        db.session.add(usage)
    db.session.commit()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─── Initialize DB & seed defaults ──────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        # Seed defaults
        defaults = {
            "groq_api_key": "",
            "daily_limit": "10",
            "enable_reviews": "false",
            "prompt_template": "",
        }
        for k, v in defaults.items():
            if not Setting.query.get(k):
                db.session.add(Setting(key=k, value=v))
        # Default admin account
        if not Admin.query.first():
            pw_hash = hashlib.sha256("admin".encode()).hexdigest()
            db.session.add(Admin(username="admin", password=pw_hash))
        db.session.commit()


# ─── Main Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    ip = get_client_ip()

    if not check_usage_limit(ip):
        limit = get_setting("daily_limit", "10")
        return jsonify({"error": f"Daily limit of {limit} requests reached. Try again tomorrow."}), 429

    data = request.get_json(force=True)

    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    keywords = (data.get("keywords") or "").strip()
    target_audience = (data.get("target_audience") or "").strip()
    platform = data.get("platform", "Amazon")
    tone = data.get("tone", "Professional")
    min_words = int(data.get("min_words", 30))
    max_words = int(data.get("max_words", 100))

    scraped_data = {}
    product_image = ""

    # Scrape if URL provided
    if url:
        include_reviews = get_setting("enable_reviews", "false") == "true"
        scraped, err = scrape_amazon(url, include_reviews=include_reviews)
        if not err:
            scraped_data = scraped
            product_image = scraped.get("image", "")

    # Manual inputs override scraped data
    final_title = title or scraped_data.get("title", "")
    final_description = description or scraped_data.get("description", "")
    final_bullets = scraped_data.get("bullets", [])
    reviews = scraped_data.get("reviews", [])

    if not final_title and not final_description:
        return jsonify({"error": "Please provide a product title or description."}), 400

    api_key = get_setting("groq_api_key", "")
    if not api_key:
        return jsonify({"error": "Groq API key not configured. Please contact the admin."}), 400

    prompt_template = get_setting("prompt_template", "") or None

    try:
        result = generate_ad_copy(
            api_key=api_key,
            title=final_title,
            description=final_description,
            bullets=final_bullets,
            keywords=keywords,
            target_audience=target_audience,
            platform=platform,
            tone=tone,
            min_words=min_words,
            max_words=max_words,
            product_url=url,
            product_image=product_image,
            reviews=reviews,
            prompt_template=prompt_template,
        )
    except Exception as e:
        return jsonify({"error": f"AI generation failed: {str(e)}"}), 500

    # Save to DB
    new_req = Request(url=url or "manual", result=json.dumps(result))
    db.session.add(new_req)
    db.session.commit()

    increment_usage(ip)

    return jsonify(result)


# ─── Export Routes ───────────────────────────────────────────────────────────

def build_html_export(result_data):
    """Build a standalone HTML string from the ad copy result."""
    product = result_data.get("product", {})
    headlines = result_data.get("headlines", [])
    hooks = result_data.get("hooks", [])
    short_ads = result_data.get("short_ads", [])
    long_ads = result_data.get("long_ads", [])
    keywords = result_data.get("keywords", [])

    items_html = lambda items, tag="p": "".join(
        f'<{tag} class="item">{i}</{tag}>' for i in items
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ad Copy – {product.get('title','')}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #222; }}
  h1 {{ color: #e47911; }} h2 {{ color: #333; border-bottom: 2px solid #e47911; padding-bottom: 6px; }}
  .item {{ background: #f9f9f9; border-left: 4px solid #e47911; padding: 12px 16px; margin: 8px 0; border-radius: 4px; }}
  .product-img {{ max-width: 200px; border-radius: 8px; margin-bottom: 16px; }}
  .kw {{ display: inline-block; background: #e47911; color: #fff; padding: 4px 10px; border-radius: 20px; margin: 4px; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>KDP Ad Copy</h1>
{"<img class='product-img' src='" + product.get('image','') + "' alt='Product'>" if product.get('image') else ""}
<h2>{product.get('title','')}</h2>
{"<p><a href='" + product.get('url','') + "'>View on Amazon</a></p>" if product.get('url') else ""}
<h2>Headlines</h2>{items_html(headlines)}
<h2>Hooks</h2>{items_html(hooks)}
<h2>Short Ads</h2>{items_html(short_ads)}
<h2>Long Ads</h2>{items_html(long_ads)}
<h2>Keywords</h2><div>{"".join(f"<span class='kw'>{k}</span>" for k in keywords)}</div>
</body></html>"""
    return html


@app.route("/export/html", methods=["POST"])
def export_html():
    data = request.get_json(force=True)
    html = build_html_export(data)
    buf = io.BytesIO(html.encode("utf-8"))
    buf.seek(0)
    return send_file(buf, mimetype="text/html", as_attachment=True, download_name="ad_copy.html")


@app.route("/export/zip", methods=["POST"])
def export_zip():
    data = request.get_json(force=True)
    html = build_html_export(data)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ad_copy.html", html)

        # Download product image if available
        image_url = (data.get("product") or {}).get("image", "")
        if image_url:
            try:
                img_resp = req_lib.get(image_url, timeout=8)
                if img_resp.status_code == 200:
                    ext = image_url.split(".")[-1].split("?")[0] or "jpg"
                    zf.writestr(f"product_image.{ext}", img_resp.content)
            except Exception:
                pass

    zip_buf.seek(0)
    return send_file(zip_buf, mimetype="application/zip", as_attachment=True, download_name="ad_copy.zip")


# ─── Admin Routes ────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        admin = Admin.query.filter_by(username=username, password=pw_hash).first()
        if admin:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    if request.method == "POST":
        set_setting("groq_api_key", request.form.get("groq_api_key", ""))
        set_setting("daily_limit", request.form.get("daily_limit", "10"))
        set_setting("enable_reviews", "true" if request.form.get("enable_reviews") else "false")
        set_setting("prompt_template", request.form.get("prompt_template", ""))
        flash("Settings saved.", "success")

    settings = {
        "groq_api_key": get_setting("groq_api_key"),
        "daily_limit": get_setting("daily_limit", "10"),
        "enable_reviews": get_setting("enable_reviews", "false"),
        "prompt_template": get_setting("prompt_template"),
    }
    total_requests = Request.query.count()
    today_str = str(date.today())
    today_requests = Usage.query.filter_by(date=today_str).with_entities(
        db.func.sum(Usage.count)
    ).scalar() or 0

    return render_template(
        "admin_dashboard.html",
        settings=settings,
        total_requests=total_requests,
        today_requests=today_requests,
    )


@app.route("/admin/requests")
@admin_required
def admin_requests():
    reqs = Request.query.order_by(Request.created_at.desc()).limit(100).all()
    parsed = []
    for r in reqs:
        try:
            result_data = json.loads(r.result)
        except Exception:
            result_data = {}
        parsed.append({
            "id": r.id,
            "url": r.url,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "title": (result_data.get("product") or {}).get("title", "N/A"),
        })
    return render_template("admin_requests.html", requests=parsed)


# ─── Entry point ─────────────────────────────────────────────────────────────

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
