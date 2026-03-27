import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_amazon(url, include_reviews=False):
    """Scrape title, description, bullets, image from an Amazon product page."""
    result = {
        "title": "",
        "description": "",
        "bullets": [],
        "image": "",
        "reviews": [],
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return result, f"Failed to fetch page: {e}"

    soup = BeautifulSoup(resp.text, "lxml")

    # Title
    title_el = soup.find(id="productTitle")
    if title_el:
        result["title"] = title_el.get_text(strip=True)

    # Product image
    img_el = soup.find(id="landingImage")
    if img_el:
        result["image"] = img_el.get("src") or img_el.get("data-old-hires") or ""

    # Description / feature bullets
    bullets_el = soup.find(id="feature-bullets")
    if bullets_el:
        items = bullets_el.find_all("span", class_="a-list-item")
        result["bullets"] = [i.get_text(strip=True) for i in items if i.get_text(strip=True)]

    # Editorial / book description
    desc_el = soup.find(id="bookDescription_feature_div")
    if not desc_el:
        desc_el = soup.find(id="productDescription")
    if desc_el:
        result["description"] = desc_el.get_text(separator=" ", strip=True)

    # Reviews (optional)
    if include_reviews:
        review_els = soup.select("span[data-hook='review-body'] span")
        result["reviews"] = [r.get_text(strip=True) for r in review_els[:5]]

    return result, None
