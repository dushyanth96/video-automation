"""Expand 1 idea -> strict Leo/Alex script JSON (110-135 words, Yo Alex! opener).
Usage: python -m pipeline.expand_script --idea '{"topic": "...", "pillar": "Pillar 1"}' --out scripts/job.json
"""
import argparse, json, os, re, sys

try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass
from pipeline.nvidia_client import chat, script_model, SYSTEM_PROMPT

def validate(script: dict) -> list:
    errs = []
    dlg = script.get("dialogue", [])
    if not dlg or not dlg[0].get("text", "").startswith("Yo Alex!"):
        errs.append("First line must start with 'Yo Alex!'")
    words = sum(len(d.get("text", "").split()) for d in dlg)
    if not (110 <= words <= 135):
        errs.append(f"Word count {words} not in 110-135")
    for d in dlg:
        if len(d.get("text", "").split()) > 15:
            errs.append(f"Turn too long (>15w): {d.get('text','')[:50]}")
        if d.get("speaker") not in ("Leo", "Alex"):
            errs.append(f"Bad speaker: {d.get('speaker')}")
    # Cards: exactly 2, each trigger must appear verbatim in some dialogue line
    cards = script.get("cards", [])
    if len(cards) != 2:
        errs.append(f"Need exactly 2 cards, got {len(cards)}")
    else:
        full_text = " ".join(d.get("text", "") for d in dlg).lower()
        for c in cards:
            trig = str(c.get("trigger", "")).strip().lower()
            if not trig or trig not in full_text:
                errs.append(f"Card trigger not spoken: {c.get('trigger', '')!r}")
            for k in ("badge_icon", "badge_text", "headline_top", "headline_hl",
                      "headline_sub", "footer_left", "footer_badge"):
                if not str(c.get(k, "")).strip():
                    errs.append(f"Card missing {k}: trigger={c.get('trigger', '')!r}")
                    break
    return errs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True, help="JSON string or @path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    idea_raw = open(args.idea[1:], encoding="utf-8").read() if args.idea.startswith("@") else args.idea
    idea = json.loads(idea_raw) if idea_raw.strip().startswith("{") else {"topic": idea_raw}

    script = {}
    for attempt in range(args.retries + 1):
        try:
            raw = chat(script_model(), [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Write the script for: {json.dumps(idea)}. JSON only."},
            ], temperature=0.5, max_tokens=3500)
        except Exception as e:
            print(f"[attempt {attempt}] LLM call failed: {e}", file=sys.stderr)
            continue
        try:
            from pipeline.seo import extract_json
            script = extract_json(raw)
        except Exception as e:
            print(f"[attempt {attempt}] JSON parse failed: {e}", file=sys.stderr)
            continue
        errs = validate(script)
        if not errs:
            break
        print(f"[attempt {attempt}] validation: {errs}", file=sys.stderr)
    else:
        print("[warn] using last attempt despite validation errors", file=sys.stderr)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(script, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Wrote {args.out} words={sum(len(d['text'].split()) for d in script.get('dialogue', []))}")

if __name__ == "__main__":
    main()
