
import html
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

#Current changes 
import html


#Page Configs
st.set_page_config(
    page_title="MarketIntel",
    page_icon="◼",
    layout="centered",
    initial_sidebar_state="expanded",
)

#UI/UX
st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        background: #000 !important;
        color: #fff !important;
    }
    
    .stApp {
        background: #000;
        color: #fff;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 920px;
    }

    h1, h2, h3 {
        color: #fff !important;
    }

    div[data-testid="stTextInput"] label p {
        color: #fff !important;
        font-weight: 500;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: #fff !important;
        opacity: 0.6;
    }

    div[data-testid="stTextInput"] input {
        background: #0f0f0f !important;
        color: #fff !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 0px !important;
        padding: 0.8rem 1rem !important;
    }

    .stButton button {
        background: #fff !important;
        color: #000 !important;
        border: none !important;
        border-radius: 14px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 700 !important;
    }

    .stButton button:hover {
        opacity: 0.95;
    }

    .card {
        background: #0f0f0f;
        border: 1px solid #222;
        border-radius: 20px;
        padding: 18px 18px;
        margin-bottom: 12px;
    }

    .muted {
        color: white;
        font-size: 20px;
        line-height: 1.55;
    }

    .label {
        color: #8f8f8f;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        margin-bottom: 6px;
    }

    .value {
        font-size: 1.35rem;
        font-weight: 700;
        line-height: 1.2;
    }

    .headline-title {
        font-size: 1.03rem;
        font-weight: 650;
        line-height: 1.35;
        margin-bottom: 8px;
    }

    .divider {
        border-top: 1px solid #222;
        margin: 16px 0;
    }

    .small {
        font-size: 0.86rem;
        color: #a7a7a7;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


#Ollama/Model Configs DO NOT TOUCH!
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL_ENV = os.getenv("OLLAMA_MODEL", "").strip()

MODEL_PREFERENCES = [
    DEFAULT_MODEL_ENV,
    "llama3.2",
    "llama3.1",
    "mistral",
    "phi3",
    "gemma3",
]

NEWS_MAX_ITEMS = 5
REQUEST_TIMEOUT = 12


# HELPERS
def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def fallback_articles(company: str) -> List[Dict[str, str]]:
    return [
        {
            "title": f"No live news found for {company}.",
            "description": "Fallback mode is active, so the interface still shows usable content.",
            "source": "System",
            "published_at": "",
            "link": "",
        },
        {
            "title": f"{company} remains a topic of market discussion.",
            "description": "Connect to the internet and try again for live Google News RSS headlines.",
            "source": "System",
            "published_at": "",
            "link": "",
        },
        {
            "title": f"Latest headline unavailable for {company} right now.",
            "description": "The app is working; only the news source returned no usable items.",
            "source": "System",
            "published_at": "",
            "link": "",
        },
    ]


def http_get_json(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[Dict[str, Any]]:
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


#News Fetching DO NOT TOUCH!
@st.cache_data(ttl=900, show_spinner=False)
def fetch_news(company: str) -> List[Dict[str, str]]:
    query = urllib.parse.quote_plus(company)
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        response = requests.get(
            rss_url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles: List[Dict[str, str]] = []

        for item in root.findall(".//item")[:NEWS_MAX_ITEMS]:
            title = strip_html(item.findtext("title", "") or "")
            description = strip_html(item.findtext("description", "") or "")
            link = (item.findtext("link", "") or "").strip()
            published_at = (item.findtext("pubDate", "") or "").strip()
            source = ""

            source_node = item.find("source")
            if source_node is not None and source_node.text:
                source = strip_html(source_node.text)
            if not source:
                source = "Google News"

            if not title and not description:
                continue

            articles.append(
                {
                    "title": title or description or "Untitled article",
                    "description": description or "No description available.",
                    "source": source,
                    "published_at": published_at,
                    "link": link,
                }
            )

        if articles:
            return articles

        return fallback_articles(company)

    except Exception:
        return fallback_articles(company)



#Ollama model detector
@st.cache_data(ttl=300, show_spinner=False)
def get_installed_ollama_models() -> List[str]:
    data = http_get_json(f"{OLLAMA_HOST}/api/tags")
    if not data:
        return []

    models = data.get("models", []) or []
    names: List[str] = []
    for model in models:
        name = (model.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def pick_model() -> str:
    installed = get_installed_ollama_models()
    installed_set = set(installed)

    for candidate in MODEL_PREFERENCES:
        if candidate and candidate in installed_set:
            return candidate

    if installed:
        return installed[0]

    return DEFAULT_MODEL_ENV or "llama3.2"


#Thoughts and Analysis
POSITIVE_WORDS = {
    "surge", "growth", "gain", "gains", "profit", "profits", "record", "beats",
    "beat", "upgrade", "upgraded", "strong", "rally", "wins", "win", "improves",
    "improved", "launch", "launches", "expands", "expansion", "robust", "positive",
}
NEGATIVE_WORDS = {
    "loss", "losses", "drop", "drops", "decline", "declines", "downgrade",
    "downgraded", "weak", "lawsuit", "probe", "investigation", "recall",
    "cuts", "cut", "slowdown", "pressure", "negative", "slump", "miss", "misses",
}


def rule_based_sentiment(texts: List[str]) -> Tuple[str, float]:
    score = 0
    for text in texts:
        lowered = text.lower()
        pos_hits = sum(1 for word in POSITIVE_WORDS if word in lowered)
        neg_hits = sum(1 for word in NEGATIVE_WORDS if word in lowered)
        score += pos_hits - neg_hits

    normalized = max(min(score / max(len(texts), 1), 1.0), -1.0)

    if normalized >= 0.15:
        tone = "Positive"
    elif normalized <= -0.15:
        tone = "Negative"
    else:
        tone = "Neutral"

    return tone, normalized


# Ollama analysis
def build_article_block(articles: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for idx, article in enumerate(articles, 1):
        title = article.get("title", "")
        description = article.get("description", "")
        source = article.get("source", "Unknown")
        published_at = article.get("published_at", "")
        lines.append(
            f"{idx}. {title}\n"
            f"   Source: {source}\n"
            f"   Date: {published_at or 'Unknown'}\n"
            f"   Snippet: {description}"
        )
    return "\n".join(lines)


def safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to extract the first JSON object from a messy response.
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def ollama_analyze(company: str, articles: List[Dict[str, str]]) -> Dict[str, Any]:
    model = pick_model()
    article_block = build_article_block(articles)

    system_prompt = (
        "You are a market intelligence analyst. "
        "Base your answer only on the provided headlines and snippets. "
        "Do not invent facts. Return strict JSON only."
    )

    user_prompt = f"""
Company: {company}

Articles:
{article_block}

Return a JSON object with exactly these keys:
- tone: one of "Positive", "Neutral", "Negative"
- score: a number from -1.0 to 1.0
- summary: a concise 3-5 sentence market intelligence summary
- drivers: an array of 3-5 short bullet-like strings explaining the main drivers
- risks: an array of 2-4 short strings
- opportunities: an array of 2-4 short strings
- keywords: an array of 3-6 short keywords or phrases

Rules:
- Use only the supplied news items.
- Do not include markdown.
- Do not include any keys other than the ones listed.
"""

    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": user_prompt,
        "format": {
            "type": "object",
            "properties": {
                "tone": {
                    "type": "string",
                    "enum": ["Positive", "Neutral", "Negative"],
                },
                "score": {
                    "type": "number",
                },
                "summary": {
                    "type": "string",
                },
                "drivers": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "opportunities": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["tone", "score", "summary", "drivers", "risks", "opportunities", "keywords"],
            "additionalProperties": False,
        },
        "stream": False,
        "keep_alive": "5m",
    }

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=45,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get("response", "")
        parsed = safe_json_loads(raw)

        if parsed and isinstance(parsed, dict):
            parsed["tone"] = str(parsed.get("tone", "Neutral"))
            parsed["score"] = safe_float(parsed.get("score", 0.0), 0.0)
            parsed["summary"] = str(parsed.get("summary", "")).strip()
            parsed["drivers"] = [str(x).strip() for x in (parsed.get("drivers") or []) if str(x).strip()]
            parsed["risks"] = [str(x).strip() for x in (parsed.get("risks") or []) if str(x).strip()]
            parsed["opportunities"] = [str(x).strip() for x in (parsed.get("opportunities") or []) if str(x).strip()]
            parsed["keywords"] = [str(x).strip() for x in (parsed.get("keywords") or []) if str(x).strip()]
            parsed["_model"] = model
            return parsed

    except Exception:
        pass

#Insurance in case no news found
    tone, score = rule_based_sentiment([a.get("title", "") + " " + a.get("description", "") for a in articles])
    latest = articles[0]["title"] if articles else f"No live headlines found for {company}."
    keywords = extract_keywords(articles, limit=5)

    return {
        "tone": tone,
        "score": score,
        "summary": (
            f"{company} is showing a {tone.lower()} news tone right now. "
            f"The latest headline is '{latest}'. "
            f"Track whether the same themes continue across the next few articles."
        ),
        "drivers": [
            f"Latest headline: {latest}",
            "Current coverage was condensed from the most recent available headlines.",
        ],
        "risks": [
            "News flow may change quickly as new headlines arrive.",
        ],
        "opportunities": [
            "Use the latest headlines to spot momentum or sentiment shifts early.",
        ],
        "keywords": keywords,
        "_model": model,
    }


def extract_keywords(articles: List[Dict[str, str]], limit: int = 5) -> List[str]:
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "about",
        "are", "was", "were", "will", "has", "have", "had", "new", "latest",
        "after", "over", "under", "than", "but", "not", "its", "their", "they",
        "been", "can", "may", "more", "most", "said", "says", "who", "what",
        "when", "where", "why", "how", "his", "her", "our", "your", "you",
        "company", "market", "news", "report", "reports", "headlines", "headline",
    }

    text = " ".join(
        f"{a.get('title', '')} {a.get('description', '')}" for a in articles
    ).lower()

    words = re.findall(r"[a-z][a-z'-]+", text)
    words = [w for w in words if len(w) > 3 and w not in stopwords]

    if not words:
        return []

    seen: List[str] = []
    for word in words:
        if word not in seen:
            seen.append(word)
        if len(seen) >= limit:
            break
    return seen



# UI/UX Components
def stat_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="card">
            <div class="label">{html.escape(label)}</div>
            <div class="value">{html.escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def article_card(article: Dict[str, str], is_latest: bool = False) -> None:
    title = html.escape(article.get("title", "Untitled"))
    description = html.escape(article.get("description", ""))
    source = html.escape(article.get("source", "Unknown source"))
    published_at = html.escape(article.get("published_at", ""))
    link = article.get("link", "").strip()

    latest_tag = '<div class="label">Latest headline</div>' if is_latest else ""

    link_html = ""
    if link:
        safe_link = html.escape(link)
        link_html = f'<div class="small" style="margin-top:10px;">Source link: <a href="{safe_link}" target="_blank" style="color:#fff;">Open article</a></div>'

    st.markdown(
        f"""
        <div class="card">
            {latest_tag}
            <div class="headline-title">{title}</div>
            <div class="muted">{description}</div>
            <div class="small" style="margin-top:10px;">{source}{f" • {published_at}" if published_at else ""}</div>
            {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# MarKintel app
st.title("MarKIntel")
st.markdown(
    '<div class="muted">A simple market intelligence app that turns live headlines into sentiment, keywords, and a local AI summary using Ollama.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Status")
    installed_models = get_installed_ollama_models()
    active_model = pick_model()

    st.markdown(
        f"""
        <div class="card">
            <div class="label">Ollama host</div>
            <div class="value" style="font-size:1rem;">{html.escape(OLLAMA_HOST)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if installed_models:
        st.markdown(
            f"""
            <div class="card">
                <div class="label">Installed models</div>
                <div class="muted">{html.escape(", ".join(installed_models))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="card">
                <div class="label">Installed models</div>
                <div class="muted">No models detected from /api/tags. The app will still try the default model name.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="card">
            <div class="label">Selected model</div>
            <div class="value" style="font-size:1rem;">{html.escape(active_model)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="muted">
        This app uses local Ollama for the summary layer. It does not need cloud AI keys.
        </div>
        """,
        unsafe_allow_html=True,
    )

company = st.text_input("Search anything you want", placeholder="How good is the Macbook Neo?")

analyze = st.button("Search")

if analyze:
    company = company.strip()

    if not company:
        st.markdown(
            '<div class="card"><div class="muted">Type a company name first.</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    with st.spinner("Fetching live headlines..."):
        articles = fetch_news(company)

    if not articles:
        articles = fallback_articles(company)

    with st.spinner("Generating local AI insight with Ollama..."):
        result = ollama_analyze(company, articles)

    tone = str(result.get("tone", "Neutral"))
    score = safe_float(result.get("score", 0.0), 0.0)
    summary = str(result.get("summary", "")).strip()
    drivers = result.get("drivers", []) or []
    risks = result.get("risks", []) or []
    opportunities = result.get("opportunities", []) or []
    keywords = result.get("keywords", []) or []

    if tone not in {"Positive", "Neutral", "Negative"}:
        tone = "Neutral"

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        stat_card("Thoughts", tone)
    with c2:
        stat_card("Score", f"{score:+.2f}")
    with c3:
        stat_card("Articles", str(len(articles)))

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.subheader("Latest headline")
    article_card(articles[0], is_latest=True)

    st.subheader("Top headlines")
    for article in articles:
        article_card(article, is_latest=True) #if turned to false headlines will not be rendered properly html will not run!

    st.subheader("MarKIntel's Analysis")
    st.markdown(
        f"""
        <div class="card">
            <div class="muted" style="white-space: pre-line;">{html.escape(summary or "No summary returned.")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if drivers:
        st.subheader("Main drivers")
        for item in drivers:
            st.markdown(
                f"""
                <div class="card">
                    <div class="muted">{html.escape(str(item))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    c4, c5, c6 = st.columns(3)
    with c4:
        stat_card("Positive keywords", str(len([k for k in keywords if k])))
    with c5:
        stat_card("Risks", str(len(risks)))
    with c6:
        stat_card("Opportunities", str(len(opportunities)))

    if keywords:
        st.subheader("Top keywords")
        st.markdown(
            f"""
            <div class="card">
                <div class="muted">{html.escape(", ".join(str(k) for k in keywords if str(k).strip()))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if risks:
        st.subheader("Risks")
        for item in risks:
            st.markdown(
                f"""
                <div class="card">
                    <div class="muted">{html.escape(str(item))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if opportunities:
        st.subheader("Opportunities")
        for item in opportunities:
            st.markdown(
                f"""
                <div class="card">
                    <div class="muted">{html.escape(str(item))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
