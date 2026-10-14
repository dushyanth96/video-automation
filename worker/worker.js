/**
 * Automation-studio Worker: Telegram webhook + GH dispatch + schedule queue.
 * KV namespace binding: VIDEO_JOBS
 * Secrets: TELEGRAM_BOT_TOKEN, GH_PAT, GH_OWNER, GH_REPO
 * Deploy: cd worker && npx wrangler deploy
 */
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === "/telegram-webhook" && req.method === "POST") {
      const update = await req.json();
      const cb = update.callback_query;
      if (!cb) return Response.json({ ok: true });
      const [action, jobId] = String(cb.data || "").split(":");
      const job = jobId ? await env.VIDEO_JOBS.get(jobId, "json") : null;
      if (action.startsWith("select")) {
        const idx = action.split("_")[1];
        await dispatch(env, "render-video", { job_id: `${today()}-${idx}`, idea_index: idx });
        await tg(env, `🎬 Rendering idea ${idx}… watch here when done.`);
      } else if (action === "upload_now" && job) {
        await dispatch(env, "upload-video", { job_id: jobId, video_key: job.video_key });
        await tg(env, `🚀 Uploading ${jobId} now…`);
      } else if (action === "schedule" && job) {
        job.scheduled_for = "18:00 IST today";
        await env.VIDEO_JOBS.put(jobId, JSON.stringify(job));
        await tg(env, `🕕 Scheduled ${jobId} for 6PM IST (cron will dispatch upload).`);
      }
      return Response.json({ ok: true });
    }
    if (url.pathname === "/register-job" && req.method === "POST") {
      const body = await req.json(); // {job_id, video_key, video_url}
      await env.VIDEO_JOBS.put(body.job_id, JSON.stringify(body));
      return Response.json({ ok: true });
    }
    return new Response("automation-studio worker ok", { status: 200 });
  },
  // 6PM IST cron -> dispatch due scheduled uploads (set wrangler [triggers] crons = ["30 12 * * *"])
  async scheduled(_event, env) {
    const { keys } = await env.VIDEO_JOBS.list();
    for (const k of keys) {
      const job = await env.VIDEO_JOBS.get(k.name, "json");
      if (job?.scheduled_for && !job?.uploaded) {
        await dispatch(env, "upload-video", { job_id: k.name, video_key: job.video_key });
        job.uploaded = true;
        await env.VIDEO_JOBS.put(k.name, JSON.stringify(job));
      }
    }
  },
};

function today() { return new Date().toISOString().slice(0, 10); }

async function dispatch(env, type, payload) {
  await fetch(`https://api.github.com/repos/${env.GH_OWNER}/${env.GH_REPO}/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GH_PAT}`, Accept: "application/vnd.github+json" },
    body: JSON.stringify({ event_type: type, client_payload: payload }),
  });
}
async function tg(env, text) {
  // chat id stored as secret TG_CHAT_ID
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text }),
  });
}
