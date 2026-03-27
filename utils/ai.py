import json
import re
from groq import Groq


def generate_ad_copy(
    api_key,
    title,
    description,
    bullets,
    keywords,
    target_audience,
    platform,
    tone,
    min_words,
    max_words,
    product_url="",
    product_image="",
    reviews=None,
    prompt_template=None,
):
    """Call Groq API and return structured ad copy JSON."""
    client = Groq(api_key=api_key)

    bullet_text = "\n".join(f"- {b}" for b in bullets) if bullets else "N/A"
    review_text = ""
    if reviews:
        review_text = "\nCustomer review snippets:\n" + "\n".join(f"- {r}" for r in reviews)

    if not prompt_template:
        prompt_template = DEFAULT_PROMPT

    prompt = prompt_template.format(
        title=title or "N/A",
        description=description or "N/A",
        bullets=bullet_text,
        keywords=keywords or "N/A",
        target_audience=target_audience or "general readers",
        platform=platform,
        tone=tone,
        min_words=min_words,
        max_words=max_words,
        long_max=max_words * 2,
        product_url=product_url or "N/A",
        product_image=product_image or "",
        review_text=review_text,
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content

    # Extract JSON from the response safely
    data = extract_json(raw)
    if data is None:
        raise ValueError(f"Could not parse JSON from AI response:\n{raw[:500]}")

    # Ensure product fields are populated
    if "product" not in data:
        data["product"] = {}
    data["product"].setdefault("title", title or "")
    data["product"].setdefault("image", product_image or "")
    data["product"].setdefault("url", product_url or "")

    return data


def extract_json(text):
    """Try to extract a JSON object from a string."""
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find JSON block in markdown code fence
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Try to find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return None


EMAIL_PROMPT = """You are a world-class email marketing copywriter specializing in Amazon KDP books.

Product Information:
- Title: {title}
- Description: {description}
- Keywords: {keywords}
- Target Audience: {target_audience}
- Email Type: {email_type}
- Tone: {tone}
- Product URL: {product_url}
{review_text}

Word count requirements:
- Short email body: between {min_words} and {max_words} words
- Long email body: between {max_words} and {long_max} words

Write high-converting email copy with compelling subject lines, engaging preview text, persuasive body copy, and strong calls to action.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "product": {{
    "title": "{title}",
    "image": "{product_image}",
    "url": "{product_url}"
  }},
  "subject_lines": ["subject1", "subject2", "subject3", "subject4", "subject5"],
  "preview_texts": ["preview1", "preview2", "preview3"],
  "short_bodies": ["short email body 1", "short email body 2"],
  "long_bodies": ["long email body 1", "long email body 2"],
  "ctas": ["CTA 1", "CTA 2", "CTA 3", "CTA 4"]
}}"""


def generate_email_copy(
    api_key,
    title,
    description,
    keywords,
    target_audience,
    email_type,
    tone,
    min_words,
    max_words,
    product_url="",
    product_image="",
    reviews=None,
):
    """Call Groq API and return structured email ad copy JSON."""
    client = Groq(api_key=api_key)

    review_text = ""
    if reviews:
        review_text = "\nCustomer review snippets:\n" + "\n".join(f"- {r}" for r in reviews)

    prompt = EMAIL_PROMPT.format(
        title=title or "N/A",
        description=description or "N/A",
        keywords=keywords or "N/A",
        target_audience=target_audience or "general readers",
        email_type=email_type,
        tone=tone,
        min_words=min_words,
        max_words=max_words,
        long_max=max_words * 2,
        product_url=product_url or "N/A",
        product_image=product_image or "",
        review_text=review_text,
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content

    data = extract_json(raw)
    if data is None:
        raise ValueError(f"Could not parse JSON from AI response:\n{raw[:500]}")

    if "product" not in data:
        data["product"] = {}
    data["product"].setdefault("title", title or "")
    data["product"].setdefault("image", product_image or "")
    data["product"].setdefault("url", product_url or "")

    return data


DEFAULT_PROMPT = """You are a world-class Amazon KDP marketing copywriter.

Product Information:
- Title: {title}
- Description: {description}
- Key Features/Bullets:
{bullets}
- Keywords: {keywords}
- Target Audience: {target_audience}
- Platform: {platform}
- Tone: {tone}
- Product URL: {product_url}
{review_text}

Word count requirements:
- Short ads: between {min_words} and {max_words} words
- Long ads: between {max_words} and {long_max} words

Generate compelling ad copy using emotional triggers, strong hooks, and clear benefits.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "product": {{
    "title": "{title}",
    "image": "{product_image}",
    "url": "{product_url}"
  }},
  "headlines": ["headline1", "headline2", "headline3", "headline4", "headline5"],
  "hooks": ["hook1", "hook2", "hook3"],
  "short_ads": ["short ad 1 text", "short ad 2 text", "short ad 3 text"],
  "long_ads": ["long ad 1 text", "long ad 2 text"],
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""
