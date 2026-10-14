"""SEO pack for YT Shorts + IG Reels from script.json — viral-optimized.
Usage: python -m pipeline.seo --script scripts/job.json --out seo/job.json [--caption-out captions/job.txt]
Always writes output: tries NVIDIA LLM first, falls back to offline viral template.
"""
import argparse, json, os, re
try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass

NICHE_TAGS = ["#ai", "#artificialintelligence", "#llm", "#aiagents", "#devtools",
              "#coding", "#programming", "#softwareengineer", "#buildinpublic",
              "#tech", "#techtok", "#learntocode", "#mcp", "#vectordb", "#ollama"]
PILLAR_TAGS = {
    "Pillar 1": ["#aitools", "#openai", "#localllm", "#ainews"],
    "Pillar 2": ["#terminal", "#docker", "#opensource", "#backend"],
    "Pillar 3": ["#hackathon", "#mvp", "#students", "#placements"],
}

def build_fallback(script: dict) -> dict:
    topic = script.get("topic", "AI dev short")
    pillar = script.get("pillar", "Pillar 1")
    hook = (script.get("dialogue", [{}])[0].get("text", "Yo Alex!") if script.get("dialogue") else "Yo Alex!")
    extra = PILLAR_TAGS.get(pillar, PILLAR_TAGS["Pillar 1"])
    tags = NICHE_TAGS + extra
    if len(topic) > 60:
        yt_title = topic[:57].rsplit(" ", 1)[0] + "..."
    else:
        yt_title = topic
    yt_desc = (f"{hook}\n{topic}\nFull roadmap + templates in bio link.\n"
               f"\n#shorts #ai #coding")
    ig_cap = (f"🔥 {topic}\n\n"
              f"👉 Stop grinding syntax. Start building systems.\n"
              f"👉 Vector DBs + Local LLMs + MCP = 2026 stack.\n"
              f"👉 Roadmap + starter templates in bio link.\n\n"
              f"Follow for daily builder shorts 🚀\n\n" + " ".join(tags[:22]))
    return {
        "youtube_title": yt_title[:60],
        "youtube_description": yt_desc,
        "youtube_tags": [t.lstrip("#") for t in tags[:15]],
        "instagram_caption": ig_cap,
        "first_comment": "Which stack are YOU learning in 2026? 👇 Roadmap is in bio.",
        "thumbnail_text": "SYNTAX IS DEAD",
        "keywords": [topic, pillar, "AI Engineer Roadmap 2026"],
        "_fallback": True,
    }

def extract_json(raw: str) -> dict:
    text = raw.strip()
    # strip markdown fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    # balanced-brace scan from first { to handle truncation safely
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model output")
    depth, end = 0, -1
    in_str, esc = False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    if end == -1:
        raise ValueError("truncated JSON in model output")
    return json.loads(text[start:end])

def build_llm(script: dict, max_tokens: int = 2500) -> dict:
    from pipeline.nvidia_client import chat, ideate_model
    raw = chat(ideate_model(), [
        {"role": "system", "content": (
            "You are a viral Shorts/Reels SEO expert for AI coding niche. "
            "Write scroll-stopping, high-CTR copy with emojis, curiosity gap, "
            "and niche hashtags that rank. JSON ONLY, no markdown.")},
        {"role": "user", "content":
         f"Script: {json.dumps(script)[:3000]}\nReturn ONLY JSON with keys: "
         "youtube_title (<=60 chars, curiosity hook, no clickbait lies), "
         "youtube_description (line1 hook <=100 chars, line2 value, line3 CTA 'Full roadmap + templates in bio', "
         "then exactly hashtags: #shorts #ai #coding + 3 niche tags), "
         "youtube_tags (array of 15 lowercase keyword strings, no #, mix broad+niche: ai agents, mcp, vector database, etc.), "
         "instagram_caption (HOOK line with 🔥, blank line, 3 value bullets 👉, CTA bio link, 'Follow for daily builder shorts 🚀', "
         "then 20-22 hashtags mixing reach tags #ai #tech #coding with niche #mcp #vectordb #localllm #devtools), "
         "first_comment (engagement question + bio CTA), "
         "thumbnail_text (<=4 words, ALL CAPS, curiosity), "
         "keywords (array of 5 search phrases)."},
    ], temperature=0.6, max_tokens=max_tokens)
    seo = extract_json(raw)
    t = seo.get("youtube_title", "")
    if len(t) > 60:
        seo["youtube_title"] = t[:57].rsplit(" ", 1)[0] + "..."
    return seo

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--caption-out", default="")
    args = ap.parse_args()
    script = json.load(open(args.script, encoding="utf-8"))
    seo = None
    for attempt, budget in enumerate((2500, 4000)):
        try:
            seo = build_llm(script, max_tokens=budget)
            seo.pop("_fallback", None)
            print("SEO via NVIDIA LLM [OK]")
            break
        except Exception as e:
            print(f"LLM SEO attempt {attempt} failed ({e}).")
    if seo is None:
        print("Using viral fallback template.")
        seo = build_fallback(script)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(seo, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Wrote {args.out}")
    if args.caption_out:
        os.makedirs(os.path.dirname(args.caption_out) or ".", exist_ok=True)
        cap = (f"YT TITLE:\n{seo.get('youtube_title','')}\n\nYT DESCRIPTION:\n{seo.get('youtube_description','')}\n\n"
               f"YT TAGS:\n{', '.join(seo.get('youtube_tags', []))}\n\nIG CAPTION:\n{seo.get('instagram_caption','')}\n\n"
               f"FIRST COMMENT:\n{seo.get('first_comment','')}\n\nTHUMBNAIL:\n{seo.get('thumbnail_text','')}")
        open(args.caption_out, "w", encoding="utf-8").write(cap)
        print(f"Wrote {args.caption_out}")

if __name__ == "__main__":
    main()
