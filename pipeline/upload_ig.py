"""Upload Reel to Instagram via Meta Graph API (2-step: container -> publish).
Requires public video URL (R2_PUBLIC_URL) — IG fetches from Meta servers.
Usage: python -m pipeline.upload_ig --video-url https://videos.../renders/x.mp4 --seo seo/job.json
"""
import argparse, json, os, time, urllib.request, urllib.parse
try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass

GRAPH = "https://graph.facebook.com/v21.0"

def call(path: str, params: dict, method: str = "POST") -> dict:
    data = urllib.parse.urlencode(params).encode() if method == "POST" else None
    url = f"{GRAPH}{path}" + (f"?{urllib.parse.urlencode(params)}" if method == "GET" else "")
    req = urllib.request.Request(url, data=data, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-url", required=True)
    ap.add_argument("--seo", default="")
    args = ap.parse_args()
    token = os.getenv("META_LONG_LIVED_TOKEN", "")
    ig_id = os.getenv("IG_BUSINESS_ID", "")
    if not token or not ig_id:
        raise SystemExit("META_LONG_LIVED_TOKEN / IG_BUSINESS_ID missing — see README 2.6")
    seo = json.load(open(args.seo, encoding="utf-8")) if args.seo and os.path.exists(args.seo) else {}
    caption = seo.get("instagram_caption", "New build drop 🚀 #ai #devtools")
    c = call(f"/{ig_id}/media", {"media_type": "REELS", "video_url": args.video_url,
                                 "caption": caption, "share_to_feed": "true",
                                 "access_token": token})
    cid = c["id"]
    for _ in range(30):
        st = call(f"/{cid}", {"fields": "status_code", "access_token": token}, "GET")
        if st.get("status_code") == "FINISHED":
            break
        time.sleep(10)
    pub = call(f"/{ig_id}/media_publish", {"creation_id": cid, "access_token": token})
    print(f"IG published: {pub.get('id')}")

if __name__ == "__main__":
    main()
