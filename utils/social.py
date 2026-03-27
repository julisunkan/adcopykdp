"""
Social media OAuth and posting utilities.
Supports: Twitter/X, Reddit, Facebook, Pinterest
"""
import requests
from requests_oauthlib import OAuth1Session


# ── Twitter / X ───────────────────────────────────────────────────────────────

TWITTER_REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
TWITTER_AUTHORIZE_URL     = "https://api.twitter.com/oauth/authorize"
TWITTER_ACCESS_TOKEN_URL  = "https://api.twitter.com/oauth/access_token"
TWITTER_VERIFY_URL        = "https://api.twitter.com/1.1/account/verify_credentials.json"
TWITTER_TWEET_URL         = "https://api.twitter.com/2/tweets"


def twitter_get_request_token(api_key, api_secret, callback_url):
    """Step 1: get a request token and return auth URL + token data."""
    oauth = OAuth1Session(api_key, client_secret=api_secret, callback_uri=callback_url)
    resp = oauth.fetch_request_token(TWITTER_REQUEST_TOKEN_URL)
    auth_url = oauth.authorization_url(TWITTER_AUTHORIZE_URL)
    return auth_url, resp.get("oauth_token"), resp.get("oauth_token_secret")


def twitter_get_access_token(api_key, api_secret, oauth_token, oauth_token_secret, verifier):
    """Step 2: exchange verifier for access token."""
    oauth = OAuth1Session(
        api_key, client_secret=api_secret,
        resource_owner_key=oauth_token,
        resource_owner_secret=oauth_token_secret,
        verifier=verifier,
    )
    tokens = oauth.fetch_access_token(TWITTER_ACCESS_TOKEN_URL)
    return tokens.get("oauth_token"), tokens.get("oauth_token_secret"), tokens.get("screen_name")


def twitter_post(api_key, api_secret, access_token, access_token_secret, text):
    """Post a tweet (Twitter API v2)."""
    oauth = OAuth1Session(
        api_key, client_secret=api_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )
    resp = oauth.post(TWITTER_TWEET_URL, json={"text": text[:280]})
    data = resp.json()
    if resp.status_code not in (200, 201):
        raise RuntimeError(data.get("detail") or data.get("title") or "Twitter post failed")
    return data


# ── Reddit ────────────────────────────────────────────────────────────────────

REDDIT_AUTH_URL  = "https://www.reddit.com/api/v1/authorize"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_ME_URL    = "https://oauth.reddit.com/api/v1/me"
REDDIT_SUBMIT    = "https://oauth.reddit.com/api/submit"
REDDIT_UA        = "KDPAdCopy/1.0 by KDPAdCopyApp"


def reddit_auth_url(client_id, redirect_uri, state):
    return (
        f"{REDDIT_AUTH_URL}?client_id={client_id}&response_type=code"
        f"&state={state}&redirect_uri={redirect_uri}"
        f"&duration=permanent&scope=submit+identity"
    )


def reddit_get_access_token(client_id, client_secret, code, redirect_uri):
    resp = requests.post(
        REDDIT_TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        headers={"User-Agent": REDDIT_UA},
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(data.get("error", "Reddit auth failed"))
    # Get username
    me = requests.get(REDDIT_ME_URL, headers={
        "Authorization": f"Bearer {data['access_token']}",
        "User-Agent": REDDIT_UA,
    }).json()
    return data["access_token"], me.get("name", "unknown")


def reddit_post(access_token, subreddit, title, text):
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": REDDIT_UA}
    resp = requests.post(REDDIT_SUBMIT, headers=headers, data={
        "kind": "self", "sr": subreddit,
        "title": title[:300], "text": text,
        "resubmit": True, "nsfw": False,
    })
    data = resp.json()
    # Reddit returns a list of two responses; check for errors
    try:
        errors = data.get("json", {}).get("errors", [])
        if errors:
            raise RuntimeError(str(errors))
        url = data.get("json", {}).get("data", {}).get("url", "")
    except Exception as e:
        raise RuntimeError(f"Reddit post error: {e}")
    return url


# ── Facebook ──────────────────────────────────────────────────────────────────

FB_AUTH_URL  = "https://www.facebook.com/v19.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FB_ME_URL    = "https://graph.facebook.com/v19.0/me"
FB_FEED_URL  = "https://graph.facebook.com/v19.0/me/feed"


def facebook_auth_url(app_id, redirect_uri):
    scope = "pages_manage_posts,pages_read_engagement,publish_to_groups,user_posts"
    return (
        f"{FB_AUTH_URL}?client_id={app_id}&redirect_uri={redirect_uri}"
        f"&scope={scope}&response_type=code"
    )


def facebook_get_access_token(app_id, app_secret, code, redirect_uri):
    resp = requests.get(FB_TOKEN_URL, params={
        "client_id": app_id, "client_secret": app_secret,
        "code": code, "redirect_uri": redirect_uri,
    })
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(data.get("error", {}).get("message", "Facebook auth failed"))
    token = data["access_token"]
    me = requests.get(FB_ME_URL, params={"access_token": token, "fields": "name"}).json()
    return token, me.get("name", "unknown")


def facebook_post(access_token, message, link=""):
    payload = {"message": message, "access_token": access_token}
    if link:
        payload["link"] = link
    resp = requests.post(FB_FEED_URL, data=payload)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Facebook post failed"))
    return data.get("id", "")


# ── Pinterest ─────────────────────────────────────────────────────────────────

PIN_AUTH_URL  = "https://www.pinterest.com/oauth/"
PIN_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
PIN_ME_URL    = "https://api.pinterest.com/v5/user_account"
PIN_BOARDS    = "https://api.pinterest.com/v5/boards"
PIN_PINS      = "https://api.pinterest.com/v5/pins"


def pinterest_auth_url(app_id, redirect_uri):
    return (
        f"{PIN_AUTH_URL}?response_type=code&client_id={app_id}"
        f"&redirect_uri={redirect_uri}&scope=pins:write,boards:read,user_accounts:read"
    )


def pinterest_get_access_token(app_id, app_secret, code, redirect_uri):
    resp = requests.post(PIN_TOKEN_URL,
        auth=(app_id, app_secret),
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(data.get("message", "Pinterest auth failed"))
    token = data["access_token"]
    me = requests.get(PIN_ME_URL, headers={"Authorization": f"Bearer {token}"}).json()
    return token, me.get("username", "unknown")


def pinterest_get_boards(access_token):
    resp = requests.get(PIN_BOARDS, headers={"Authorization": f"Bearer {access_token}"})
    data = resp.json()
    return [{"id": b["id"], "name": b["name"]} for b in data.get("items", [])]


def pinterest_post(access_token, board_id, title, description, link, image_url=""):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "link": link,
    }
    if image_url:
        payload["media_source"] = {"source_type": "image_url", "url": image_url}
    else:
        payload["media_source"] = {"source_type": "image_url", "url": "https://via.placeholder.com/600x400"}
    resp = requests.post(PIN_PINS, headers=headers, json=payload)
    data = resp.json()
    if resp.status_code not in (200, 201):
        raise RuntimeError(data.get("message", "Pinterest post failed"))
    return data.get("id", "")
