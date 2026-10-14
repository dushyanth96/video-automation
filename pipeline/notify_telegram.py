"""Telegram CMS + approval sender. No extra deps (urllib only).
Sends: 5 ideas list, script preview, approval with R2 watch URL + SEO.
"""
import json, os, urllib.request, urllib.parse
try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass

def _send(text: str, buttons: list | None = None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[telegram] skipped (keys missing). Message was:\n" + text)
        return
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        print(r.read().decode()[:200])

def send_ideas(ideas: dict, src_path: str = ""):
    items = ideas.get("ideas", []) if isinstance(ideas, dict) else []
    lines = ["🔥 <b>5 topics today</b> — reply /select_1..5"]
    kb = []
    for i, it in enumerate(items[:5], 1):
        lines.append(f"\n<b>{i}. {it.get('topic','')}</b>\n{it.get('pillar','')} — <i>{it.get('hook','')}</i>\nWhy: {it.get('why_viral','')}")
        kb.append([{"text": f"🎬 Select {i}", "callback_data": f"select_{i}"}])
    lines.append(f"\n<small>{src_path}</small>")
    _send("\n".join(lines)[:4000], kb or None)

def send_approval(video_url: str, seo_path: str = "", script_path: str = "", job_id: str = ""):
    seo = {}
    if seo_path and os.path.exists(seo_path):
        seo = json.load(open(seo_path, encoding="utf-8"))
    caption = (f"✅ <b>Video ready — approve?</b>\n🎥 Watch: {video_url}\n"
               f"\n📺 YT: {seo.get('youtube_title','')}\n📝 {seo.get('instagram_caption','')[:300]}")
    kb = [[{"text": "🚀 Upload Now", "callback_data": f"upload_now:{job_id}"},
           {"text": "🕕 Schedule 6PM", "callback_data": f"schedule:{job_id}"}]]
    _send(caption[:4000], kb)

def send_posted(yt_url: str, ig_status: str):
    _send(f"🎉 <b>Posted!</b>\nYouTube: {yt_url}\nInstagram: {ig_status}")

if __name__ == "__main__":
    import sys
    _send(" ".join(sys.argv[1:]) or "Telegram OK ✅")
