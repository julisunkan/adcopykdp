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

from models import db, Request, Setting, Usage, Admin, SocialToken
from utils.scraper import scrape_amazon
from utils.ai import generate_ad_copy, generate_email_copy
from utils import social as soc

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
            "twitter_api_key": "",
            "twitter_api_secret": "",
            "reddit_client_id": "",
            "reddit_client_secret": "",
            "facebook_app_id": "",
            "facebook_app_secret": "",
            "pinterest_app_id": "",
            "pinterest_app_secret": "",
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


# ─── Email AdCopy Routes ─────────────────────────────────────────────────────

@app.route("/generate/email", methods=["POST"])
def generate_email():
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
    email_type = data.get("email_type", "Promotional")
    tone = data.get("tone", "Professional")
    min_words = int(data.get("min_words", 50))
    max_words = int(data.get("max_words", 150))

    scraped_data = {}
    product_image = ""

    if url:
        include_reviews = get_setting("enable_reviews", "false") == "true"
        scraped, err = scrape_amazon(url, include_reviews=include_reviews)
        if not err:
            scraped_data = scraped
            product_image = scraped.get("image", "")

    final_title = title or scraped_data.get("title", "")
    final_description = description or scraped_data.get("description", "")
    reviews = scraped_data.get("reviews", [])

    if not final_title and not final_description:
        return jsonify({"error": "Please provide a product title or description."}), 400

    api_key = get_setting("groq_api_key", "")
    if not api_key:
        return jsonify({"error": "Groq API key not configured. Please contact the admin."}), 400

    try:
        result = generate_email_copy(
            api_key=api_key,
            title=final_title,
            description=final_description,
            keywords=keywords,
            target_audience=target_audience,
            email_type=email_type,
            tone=tone,
            min_words=min_words,
            max_words=max_words,
            product_url=url,
            product_image=product_image,
            reviews=reviews,
        )
    except Exception as e:
        return jsonify({"error": f"AI generation failed: {str(e)}"}), 500

    new_req = Request(url=url or "manual", result=json.dumps(result))
    db.session.add(new_req)
    db.session.commit()
    increment_usage(ip)

    return jsonify(result)


def build_email_html_export(result_data):
    """Build a standalone HTML string from email ad copy result."""
    product = result_data.get("product", {})
    subject_lines = result_data.get("subject_lines", [])
    preview_texts = result_data.get("preview_texts", [])
    short_bodies = result_data.get("short_bodies", [])
    long_bodies = result_data.get("long_bodies", [])
    ctas = result_data.get("ctas", [])

    items_html = lambda items: "".join(
        f'<p class="item">{i}</p>' for i in items
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Email Ad Copy – {product.get('title','')}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #222; }}
  h1 {{ color: #6c5ce7; }} h2 {{ color: #333; border-bottom: 2px solid #6c5ce7; padding-bottom: 6px; }}
  .item {{ background: #f9f9f9; border-left: 4px solid #6c5ce7; padding: 12px 16px; margin: 8px 0; border-radius: 4px; }}
  .product-img {{ max-width: 200px; border-radius: 8px; margin-bottom: 16px; }}
  .cta {{ display: inline-block; background: #6c5ce7; color: #fff; padding: 4px 10px; border-radius: 20px; margin: 4px; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>Email Ad Copy</h1>
{"<img class='product-img' src='" + product.get('image','') + "' alt='Product'>" if product.get('image') else ""}
<h2>{product.get('title','')}</h2>
{"<p><a href='" + product.get('url','') + "'>View on Amazon</a></p>" if product.get('url') else ""}
<h2>Subject Lines</h2>{items_html(subject_lines)}
<h2>Preview Texts</h2>{items_html(preview_texts)}
<h2>Short Email Bodies</h2>{items_html(short_bodies)}
<h2>Long Email Bodies</h2>{items_html(long_bodies)}
<h2>CTAs</h2><div>{"".join(f"<span class='cta'>{c}</span>" for c in ctas)}</div>
</body></html>"""
    return html


@app.route("/export/email/html", methods=["POST"])
def export_email_html():
    data = request.get_json(force=True)
    html = build_email_html_export(data)
    buf = io.BytesIO(html.encode("utf-8"))
    buf.seek(0)
    return send_file(buf, mimetype="text/html", as_attachment=True, download_name="email_ad_copy.html")


@app.route("/export/email/zip", methods=["POST"])
def export_email_zip():
    data = request.get_json(force=True)
    html = build_email_html_export(data)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("email_ad_copy.html", html)
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
    return send_file(zip_buf, mimetype="application/zip", as_attachment=True, download_name="email_ad_copy.zip")


# ─── Social Media Routes ─────────────────────────────────────────────────────

def get_session_id():
    """Return a stable session key, creating one if needed."""
    if "sid" not in session:
        import uuid
        session["sid"] = str(uuid.uuid4())
    return session["sid"]


def get_social_token(platform):
    """Fetch stored social token for the current session."""
    sid = session.get("sid")
    if not sid:
        return None
    return SocialToken.query.filter_by(session_id=sid, platform=platform).first()


def save_social_token(platform, access_token, username, access_token_secret=""):
    sid = get_session_id()
    tok = SocialToken.query.filter_by(session_id=sid, platform=platform).first()
    if tok:
        tok.access_token = access_token
        tok.access_token_secret = access_token_secret
        tok.username = username
    else:
        tok = SocialToken(
            session_id=sid, platform=platform,
            access_token=access_token,
            access_token_secret=access_token_secret,
            username=username,
        )
        db.session.add(tok)
    db.session.commit()


def get_callback_url(platform):
    base = request.host_url.rstrip("/")
    return f"{base}/social/callback/{platform}"


@app.route("/social/status")
def social_status():
    """Return JSON of which platforms are connected."""
    sid = session.get("sid")
    result = {}
    for p in ["twitter", "reddit", "facebook", "pinterest"]:
        tok = SocialToken.query.filter_by(session_id=sid, platform=p).first() if sid else None
        result[p] = {"connected": bool(tok), "username": tok.username if tok else None}
    return jsonify(result)


# ── Twitter ──────────────────────────────────────────────────────────────────

@app.route("/social/connect/twitter")
def social_connect_twitter():
    api_key = get_setting("twitter_api_key")
    api_secret = get_setting("twitter_api_secret")
    if not api_key or not api_secret:
        return jsonify({"error": "Twitter API credentials not configured in Admin."}), 400
    try:
        callback = get_callback_url("twitter")
        auth_url, req_token, req_token_secret = soc.twitter_get_request_token(api_key, api_secret, callback)
        session["tw_req_token"] = req_token
        session["tw_req_token_secret"] = req_token_secret
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/social/callback/twitter")
def social_callback_twitter():
    api_key = get_setting("twitter_api_key")
    api_secret = get_setting("twitter_api_secret")
    oauth_token = request.args.get("oauth_token")
    verifier = request.args.get("oauth_verifier")
    req_token_secret = session.get("tw_req_token_secret", "")
    try:
        access_token, access_token_secret, screen_name = soc.twitter_get_access_token(
            api_key, api_secret, oauth_token, req_token_secret, verifier
        )
        save_social_token("twitter", access_token, f"@{screen_name}", access_token_secret)
    except Exception as e:
        return f"<script>window.opener&&window.opener.postMessage({{social:'twitter',error:'{e}'}},'*');window.close();</script>"
    return "<script>window.opener&&window.opener.postMessage({social:'twitter',ok:true},'*');window.close();</script>"


@app.route("/social/disconnect/twitter")
def social_disconnect_twitter():
    sid = session.get("sid")
    if sid:
        SocialToken.query.filter_by(session_id=sid, platform="twitter").delete()
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/social/post/twitter", methods=["POST"])
def social_post_twitter():
    tok = get_social_token("twitter")
    if not tok:
        return jsonify({"error": "Twitter not connected."}), 401
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided."}), 400
    api_key = get_setting("twitter_api_key")
    api_secret = get_setting("twitter_api_secret")
    try:
        result = soc.twitter_post(api_key, api_secret, tok.access_token, tok.access_token_secret, text)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Reddit ───────────────────────────────────────────────────────────────────

@app.route("/social/connect/reddit")
def social_connect_reddit():
    client_id = get_setting("reddit_client_id")
    if not client_id:
        return jsonify({"error": "Reddit credentials not configured in Admin."}), 400
    import secrets
    state = secrets.token_hex(16)
    session["reddit_state"] = state
    callback = get_callback_url("reddit")
    return redirect(soc.reddit_auth_url(client_id, callback, state))


@app.route("/social/callback/reddit")
def social_callback_reddit():
    state = request.args.get("state")
    code = request.args.get("code")
    error = request.args.get("error")
    if error or state != session.get("reddit_state"):
        return "<script>window.opener&&window.opener.postMessage({social:'reddit',error:'Auth failed or denied'},'*');window.close();</script>"
    client_id = get_setting("reddit_client_id")
    client_secret = get_setting("reddit_client_secret")
    callback = get_callback_url("reddit")
    try:
        access_token, username = soc.reddit_get_access_token(client_id, client_secret, code, callback)
        save_social_token("reddit", access_token, f"u/{username}")
    except Exception as e:
        return f"<script>window.opener&&window.opener.postMessage({{social:'reddit',error:'{e}'}},'*');window.close();</script>"
    return "<script>window.opener&&window.opener.postMessage({social:'reddit',ok:true},'*');window.close();</script>"


@app.route("/social/disconnect/reddit")
def social_disconnect_reddit():
    sid = session.get("sid")
    if sid:
        SocialToken.query.filter_by(session_id=sid, platform="reddit").delete()
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/social/post/reddit", methods=["POST"])
def social_post_reddit():
    tok = get_social_token("reddit")
    if not tok:
        return jsonify({"error": "Reddit not connected."}), 401
    data = request.get_json(force=True)
    subreddit = (data.get("subreddit") or "").strip().lstrip("r/")
    title = (data.get("title") or "").strip()
    text = (data.get("text") or "").strip()
    if not subreddit or not title:
        return jsonify({"error": "Subreddit and title are required."}), 400
    try:
        url = soc.reddit_post(tok.access_token, subreddit, title, text)
        return jsonify({"ok": True, "url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Facebook ─────────────────────────────────────────────────────────────────

@app.route("/social/connect/facebook")
def social_connect_facebook():
    app_id = get_setting("facebook_app_id")
    if not app_id:
        return jsonify({"error": "Facebook credentials not configured in Admin."}), 400
    callback = get_callback_url("facebook")
    return redirect(soc.facebook_auth_url(app_id, callback))


@app.route("/social/callback/facebook")
def social_callback_facebook():
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        return "<script>window.opener&&window.opener.postMessage({social:'facebook',error:'Auth failed or denied'},'*');window.close();</script>"
    app_id = get_setting("facebook_app_id")
    app_secret = get_setting("facebook_app_secret")
    callback = get_callback_url("facebook")
    try:
        access_token, name = soc.facebook_get_access_token(app_id, app_secret, code, callback)
        save_social_token("facebook", access_token, name)
    except Exception as e:
        return f"<script>window.opener&&window.opener.postMessage({{social:'facebook',error:'{e}'}},'*');window.close();</script>"
    return "<script>window.opener&&window.opener.postMessage({social:'facebook',ok:true},'*');window.close();</script>"


@app.route("/social/disconnect/facebook")
def social_disconnect_facebook():
    sid = session.get("sid")
    if sid:
        SocialToken.query.filter_by(session_id=sid, platform="facebook").delete()
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/social/post/facebook", methods=["POST"])
def social_post_facebook():
    tok = get_social_token("facebook")
    if not tok:
        return jsonify({"error": "Facebook not connected."}), 401
    data = request.get_json(force=True)
    message = (data.get("text") or "").strip()
    link = (data.get("link") or "").strip()
    if not message:
        return jsonify({"error": "No message provided."}), 400
    try:
        post_id = soc.facebook_post(tok.access_token, message, link)
        return jsonify({"ok": True, "post_id": post_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Pinterest ─────────────────────────────────────────────────────────────────

@app.route("/social/connect/pinterest")
def social_connect_pinterest():
    app_id = get_setting("pinterest_app_id")
    if not app_id:
        return jsonify({"error": "Pinterest credentials not configured in Admin."}), 400
    callback = get_callback_url("pinterest")
    return redirect(soc.pinterest_auth_url(app_id, callback))


@app.route("/social/callback/pinterest")
def social_callback_pinterest():
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        return "<script>window.opener&&window.opener.postMessage({social:'pinterest',error:'Auth failed or denied'},'*');window.close();</script>"
    app_id = get_setting("pinterest_app_id")
    app_secret = get_setting("pinterest_app_secret")
    callback = get_callback_url("pinterest")
    try:
        access_token, username = soc.pinterest_get_access_token(app_id, app_secret, code, callback)
        save_social_token("pinterest", access_token, f"@{username}")
        # Store boards too
        boards = soc.pinterest_get_boards(access_token)
        import json
        session["pinterest_boards"] = boards
    except Exception as e:
        return f"<script>window.opener&&window.opener.postMessage({{social:'pinterest',error:'{e}'}},'*');window.close();</script>"
    return "<script>window.opener&&window.opener.postMessage({social:'pinterest',ok:true},'*');window.close();</script>"


@app.route("/social/disconnect/pinterest")
def social_disconnect_pinterest():
    sid = session.get("sid")
    if sid:
        SocialToken.query.filter_by(session_id=sid, platform="pinterest").delete()
        db.session.commit()
    session.pop("pinterest_boards", None)
    return jsonify({"ok": True})


@app.route("/social/pinterest/boards")
def social_pinterest_boards():
    tok = get_social_token("pinterest")
    if not tok:
        return jsonify({"boards": []})
    boards = session.get("pinterest_boards") or []
    if not boards:
        try:
            boards = soc.pinterest_get_boards(tok.access_token)
            session["pinterest_boards"] = boards
        except Exception:
            pass
    return jsonify({"boards": boards})


@app.route("/social/post/pinterest", methods=["POST"])
def social_post_pinterest():
    tok = get_social_token("pinterest")
    if not tok:
        return jsonify({"error": "Pinterest not connected."}), 401
    data = request.get_json(force=True)
    board_id = (data.get("board_id") or "").strip()
    title = (data.get("title") or "").strip()
    description = (data.get("text") or "").strip()
    link = (data.get("link") or "").strip()
    image_url = (data.get("image") or "").strip()
    if not board_id:
        return jsonify({"error": "Please select a board."}), 400
    try:
        pin_id = soc.pinterest_post(tok.access_token, board_id, title, description, link, image_url)
        return jsonify({"ok": True, "pin_id": pin_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        # Social credentials
        for key in ["twitter_api_key", "twitter_api_secret",
                    "reddit_client_id", "reddit_client_secret",
                    "facebook_app_id", "facebook_app_secret",
                    "pinterest_app_id", "pinterest_app_secret"]:
            val = request.form.get(key, "")
            if val:  # only overwrite if provided (don't clear with empty)
                set_setting(key, val)
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
