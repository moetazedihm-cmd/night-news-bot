import os
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests
import anthropic

FEEDS = {
    "BBC Middle East": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "BBC Persian": "https://feeds.bbci.co.uk/persian/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Times of Israel": "https://www.timesofisrael.com/feed/",
    "IRNA English": "https://en.irna.ir/rss",
}

KEYWORDS = [
    "iran", "tehran", "irgc", "hezbollah", "houthi", "israel", "gaza",
    "lebanon", "syria", "iraq", "yemen", "red sea", "nuclear", "sanction",
    "ایران", "تهران", "سپاه", "اسرائیل", "غزه", "لبنان", "سوریه",
    "عراق", "یمن", "تحریم", "هسته‌ای", "هسته ای",
]

HOURS_BACK = 26
MAX_ITEMS = 60
MODEL = "claude-sonnet-5-5"

PROMPT = """You are a news-briefing assistant. Below are raw news items
(source, title, summary) from the last 24 hours.

Write a nightly briefing in Persian (Farsi) about: Iran's conflict and
tensions with Western countries, plus major Middle East developments.

Rules:
- 8 to 10 headlines, most important first.
- Each: one short bold headline + one sentence of context + (source).
- Where sources disagree (Western vs Iranian vs regional), say so
  explicitly and attribute the claim.
- Do not state unverified claims as fact.
- Only use the items given. Do not invent anything.
- No intro or outro. Use Telegram-friendly Markdown (*bold*).

ITEMS:
{items}
"""


def fetch_items():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    items = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[warn] {source}: {e}")
            continue
        for e in feed.entries:
            t = e.get("published_parsed") or e.get("updated_parsed")
            if t and datetime.fromtimestamp(time.mktime(t), timezone.utc) < cutoff:
                continue
            title = e.get("title", "")
            summary = e.get("summary", "")[:300]
            text = f"{title} {summary}".lower()
            if any(k in text for k in KEYWORDS):
                items.append(f"[{source}] {title} — {summary}")
    return items[:MAX_ITEMS]


def summarize(items):
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": PROMPT.format(items="\n".join(items))}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i in range(0, len(text), 4000):
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text[i:i + 4000],
                  "parse_mode": "Markdown"},
            timeout=30,
        )
        if not r.ok:
            requests.post(
                url,
                json={"chat_id": chat_id, "text": text[i:i + 4000]},
                timeout=30,
            )


def main():
    items = fetch_items()
    if not items:
        send_telegram("امشب خبر مرتبطی پیدا نشد.")
        return
    send_telegram(summarize(items))


if __name__ == "__main__":
    main()
