"""Upload to YouTube Shorts. Needs google-api-python-client + google-auth.
Setup: python pipeline/get_yt_token.py  (one-time, saves YT_REFRESH_TOKEN to .env)
Usage: python -m pipeline.upload_yt --video output/dialogue_reel.mp4 --seo seo/job.json
"""
import argparse, json, os
try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--seo", default="")
    ap.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    args = ap.parse_args()
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise SystemExit("pip install google-api-python-client google-auth-httplib2 — see README 2.5")

    seo = json.load(open(args.seo, encoding="utf-8")) if args.seo and os.path.exists(args.seo) else {}
    creds = Credentials(None, refresh_token=os.getenv("YT_REFRESH_TOKEN"),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.getenv("YT_CLIENT_ID"), client_secret=os.getenv("YT_CLIENT_SECRET"))
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": seo.get("youtube_title", "AI Dev Short #shorts")[:100],
                        "description": seo.get("youtube_description", ""),
                        "tags": seo.get("youtube_tags", [])[:15], "categoryId": "28"},
            "status": {"privacyStatus": args.privacy, "madeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(args.video, mimetype="video/mp4", resumable=True))
    resp = req.execute()
    print(f"https://youtube.com/shorts/{resp['id']}")

if __name__ == "__main__":
    main()
