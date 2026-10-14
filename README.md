# Video Automation Studio (Leo & Alex Shorts)

5AM IST ideation → Telegram topic picker → script → render → approval → YT Shorts + IG Reels. Videos stored on Cloudflare R2 with watch URLs.

## 1. How it runs

| Time | What | Where |
|---|---|---|
| 05:00 IST daily | `daily-ideate.yml` fetches news → NVIDIA LLM makes 5 ideas → Telegram | GitHub Actions |
| You tap `/select_3` | Worker dispatches `render.yml` (fresh run, waits days OK) | Cloudflare Worker |
| Auto | idea → 110–135 word script → SEO pack → `generate_dialogue_video.py --script` → R2 upload → Telegram approval with watch URL | `render.yml` |
| You tap Upload Now / Schedule 6PM | Worker dispatches `upload.yml` | `upload.yml` → YouTube + Instagram → Telegram links |

Why 3 workflows: each GH job caps at **6 hours**. Waiting for approval in the same job would timeout. Split render/upload + Worker KV queue avoids it.

## 2. Keys required — what + how to get (FREE where possible)

Copy `.env.example` to `.env` and fill. Then run `python scripts/setup_check.py`.

### 2.1 NVIDIA NIM (LLM for ideas + scripts) — FREE
1. Go to https://build.nvidia.com → Sign up (Developer account, phone verify).
2. Open any model → **Get API Key** → copy `nvapi-...` → `NVIDIA_NIM_API_KEY`.
3. Recommended free models (label must say **Free Endpoint**):
   - Default: `openai/gpt-oss-20b` (fast + strict JSON — verified working)
   - Quality backup: `nvidia/nemotron-3-super-120b-a12b` (auto-fallback in code)
   - Also tried: `z-ai/glm-5.3-flash`, `moonshotai/kimi-k3` (often congested/hang — kept as last-resort fallbacks).
4. Limits: ~1000 credits/mo, 40 req/min. If 404 → copy exact ID from catalog again.

### 2.2 News — Tavily (optional, FREE 1000/mo)
1. https://tavily.com → API key → `TAVILY_API_KEY`. Empty = RSS-only (HackerNews/Reddit) still works.

### 2.3 Telegram (you have this) — FREE
1. @BotFather → `/newbot` → `TELEGRAM_BOT_TOKEN`.
2. Send your bot a `Hi`. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` → `chat.id` → `TELEGRAM_CHAT_ID`.

### 2.4 Cloudflare R2 (video storage + watch URL) — free 10GB
1. dash.cloudflare.com → **R2 Object Storage** → Create bucket `videos-automation`.
2. Manage R2 API Tokens → Create (Object Read & Write) → `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`.
3. Bucket → Settings → Connect custom domain (e.g. `videos.yourdomain.com`) → `R2_PUBLIC_URL`. Needed for IG (Meta fetches video) + your preview link.
4. Same values go to GitHub Secrets + `.env`.

### 2.5 YouTube Shorts upload
1. console.cloud.google.com → New project → Enable **YouTube Data API v3** → OAuth consent (External) → Create **Desktop** client → `YT_CLIENT_ID`, `YT_CLIENT_SECRET`.
2. Run `python pipeline/get_yt_token.py` → approve → paste printed token as `YT_REFRESH_TOKEN`.

### 2.6 Instagram Reels via Meta (Business Suite API)
1. developers.facebook.com → Create App → add **Instagram Graph API** product.
2. Link FB Page + IG **Business/Creator** account (personal accounts don't work).
3. Graph Explorer → permissions `pages_show_list, instagram_basic, instagram_content_publish, pages_read_engagement` → generate token → Extend (60 days) → `META_LONG_LIVED_TOKEN`.
4. Note `IG_BUSINESS_ID` (`/{page-id}?fields=instagram_business_account`).

### 2.7 GitHub + Worker glue
- `GH_PAT`: GitHub → Settings → Developer settings → Fine-grained PAT → repo scope **Contents + Actions Read/Write** → for Worker dispatches.
- Worker: `cd worker && npm i -g wrangler && wrangler kv:namespace create VIDEO_JOBS` → paste id into `wrangler.toml` → `wrangler secret put TELEGRAM_BOT_TOKEN|TG_CHAT_ID|GH_PAT|GH_OWNER|GH_REPO` → `wrangler deploy`. Then set Telegram webhook: `https://api.telegram.org/bot<TOK>/setWebhook?url=https://<worker>/telegram-webhook`.
- Add **all `.env` keys** also under repo **Settings → Secrets and variables → Actions** (same names).

## 3. Edit your `.env` now

```powershell
notepad .env
python scripts/setup_check.py
```

Fill at minimum: `NVIDIA_NIM_API_KEY`, `TELEGRAM_*`, `R2_*`. YT/Meta can come later (uploads will skip until set).

## 4. Local test (no cloud needed)

```powershell
uv sync
python -m pipeline.expand_script --idea '{"topic":"MCP tools replace LangChain?","pillar":"Pillar 1"}' --out scripts/test.json
python generate_dialogue_video.py --script sample_script.json --output output/dialogue_reel.mp4 --no-rvc
```

Remove `--no-rvc` to use your Morty/Rick models (needs `models/` + torch, slower).

## 5. Viral IG remix

Add Reel URLs/notes to `viral_links.txt` (one per line). `pipeline/ideate.py` includes them as remix source in the 5 ideas.

## 6. Files

- `generate_dialogue_video.py --script X --output Y [--no-rvc]` — renderer (was hardcoded, now JSON-driven)
- `pipeline/`: `ideate, expand_script, seo, r2, notify_telegram, upload_yt, upload_ig, get_yt_token, nvidia_client`
- `.github/workflows/`: `daily-ideate.yml, render.yml, upload.yml`
- `worker/`: `worker.js + wrangler.toml` (Telegram webhook + 6PM schedule sweep)
- `sample_script.json`, `scripts/setup_check.py`, `viral_links.txt`
