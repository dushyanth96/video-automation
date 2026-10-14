"""5AM ideation: RSS (+optional Tavily) news -> NVIDIA LLM -> 5 ideas JSON -> Telegram.
Usage: python -m pipeline.ideate --out ideas/2026-10-14.json [--post-telegram]
"""
import argparse, datetime, json, os, re, sys, urllib.request, xml.etree.ElementTree as ET

try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass

from pipeline.nvidia_client import chat, ideate_model

RSS_FEEDS = [
    "https://hnrss.org/newest?q=AI+OR+LLM+OR+agent",
    "https://www.reddit.com/r/LocalLLaMA/hot/.rss",
    "https://github.com/trending?since=daily",  # HTML fallback, best-effort parse
]

def fetch_rss(url: str, limit: int = 8) -> list:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "video-automation/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", "ignore")
        root = ET.fromstring(raw)
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "")[:180]
            if title:
                out.append(title)
            if len(out) >= limit:
                break
        # Atom fallback
        if not out:
            for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
                t = e.findtext("{http://www.w3.org/2005/Atom}title") or ""
                if t:
                    out.append(t[:180])
                if len(out) >= limit:
                    break
        return out
    except Exception as e:
        print(f"[rss] {url} failed: {e}", file=sys.stderr)
        return []

def fetch_tavily(query: str = "AI developer tools LLM agents news today") -> list:
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        return []
    try:
        payload = json.dumps({"query": query, "max_results": 8, "topic": "news",
                              "time_range": "day"}).encode()
        req = urllib.request.Request("https://api.tavily.com/search", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        return [f"{x.get('title','')} — {x.get('content','')[:160]}" for x in data.get("results", [])]
    except Exception as e:
        print(f"[tavily] failed: {e}", file=sys.stderr)
        return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--post-telegram", action="store_true")
    ap.add_argument("--viral-file", default="viral_links.txt",
                    help="Optional file with IG Reel URLs/notes to remix as 6th idea source")
    args = ap.parse_args()

    headlines: list = []
    for f in RSS_FEEDS:
        headlines += fetch_rss(f)
    headlines += fetch_tavily()
    viral_notes = ""
    if os.path.exists(args.viral_file):
        viral_notes = open(args.viral_file, encoding="utf-8").read()[:2000]

    headlines = headlines[:20] or ["No live news fetched — use general AI dev-tools trends."]
    prompt = (f"TODAY'S SIGNALS:\n" + "\n".join(f"- {h}" for h in headlines)
              + (f"\n\nVIRAL IG REMIX NOTES:\n{viral_notes}" if viral_notes else "")
              + "\n\nReturn ONLY JSON: {\"ideas\": [{\"topic\": str, \"pillar\": \"Pillar 1|Pillar 2|Pillar 3\", "
                "\"hook\": str (Leo's Yo Alex! opener), \"why_viral\": str}]} — exactly 5 ideas.")
    raw = chat(ideate_model(), [
        {"role": "system", "content": "You pick viral tech-short topics for college builders. JSON only."},
        {"role": "user", "content": prompt},
    ], temperature=0.8)
    m = re.search(r"\{.*\}", raw, re.S)
    ideas = json.loads(m.group(0) if m else raw)

    day = datetime.date.today().isoformat()
    out = args.out or f"ideas/{day}.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(ideas, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Wrote {out}")

    if args.post_telegram:
        from pipeline.notify_telegram import send_ideas
        send_ideas(ideas, out)

if __name__ == "__main__":
    main()
