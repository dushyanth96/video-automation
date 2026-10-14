"""Shared NVIDIA NIM client (OpenAI-compatible). Free models via build.nvidia.com."""
import os
import json
import urllib.request

from pipeline.env import load_project_env
load_project_env()

BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

SYSTEM_PROMPT = os.getenv("SCRIPT_SYSTEM_PROMPT", """You are an automated dialogue engine generating 45-second viral tech shorts scripts.
[CORE NICHE & IDENTITY] Niche: Conversational AI Engineering, Dev Tools & Modern Builder Tech. Format: Back-and-forth dialogue between two college best friends over gameplay.
[CONTENT PILLARS] Pillar 1 - Modern AI & LLM Updates. Pillar 2 - Pragmatic Developer Workflows. Pillar 3 - Student-to-Builder Playbooks.
[CHARACTERS] Leo: chaotic experimenter, panicky, fast/informal/blunt. Alex: cracked builder, relaxed/sharp/practical.
[CRITICAL SCRIPT RULES] 1. First item MUST begin with Leo saying "Yo Alex!" 2. Exactly 110-135 total words. 3. Max 15 words per turn. 4. ARC: 0-5s panic rumor / 5-20s myth-bust / 20-35s practical tool / 35-45s lazy Q + roast.
[CARD RULES] Also output exactly 2 overlay "cards" shown on screen when their trigger phrase is spoken. Card 1 = INSIGHT moment: trigger = 2-5 word phrase copied EXACTLY from Alex's myth-bust line; headlines restate the technical truth (<=8 words each). Card 2 = CTA moment: trigger = 2-5 word phrase copied EXACTLY from the final line; headlines = resource/roadmap offer. Badge texts <=4 words, footers <=7 words.
Output ONLY valid JSON: {"topic": str, "pillar": str, "dialogue": [{"speaker": "Leo"|"Alex", "text": str}], "cards": [{"trigger": str, "badge_icon": str(emoji), "badge_text": str, "headline_top": str, "headline_hl": str, "headline_sub": str, "footer_left": str, "footer_badge": str}]}""")

def chat(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1500) -> str:
    api_key = os.getenv("NVIDIA_NIM_API_KEY", "")
    if not api_key:
        raise RuntimeError("NVIDIA_NIM_API_KEY missing. See README section 2 + .env.example")
    # Primary + fallbacks: some free endpoints get congested and hang — try next.
    # gpt-oss-20b is fastest + strict JSON; nemotron-super is higher quality backup.
    candidates = [model]
    for fb in ("openai/gpt-oss-20b", "nvidia/nemotron-3-super-120b-a12b",
               "z-ai/glm-5.3-flash", "moonshotai/kimi-k3"):
        if fb not in candidates:
            candidates.append(fb)
    last_err: Exception | None = None
    for m in candidates:
        try:
            return _chat_once(api_key, m, messages, temperature, max_tokens)
        except Exception as e:
            last_err = e
            print(f"[nvidia] {m} failed ({type(e).__name__}), trying next...", flush=True)
    raise RuntimeError(f"All NVIDIA models failed. Last error: {last_err}")

def _chat_once(api_key: str, model: str, messages: list, temperature: float, max_tokens: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=int(os.getenv("NVIDIA_TIMEOUT", "60"))) as r:
        data = json.loads(r.read().decode())
    msg = data["choices"][0]["message"]
    # Reasoning models are nondeterministic: sometimes the JSON lands in
    # content, sometimes only in reasoning_content. Prefer whichever has a {.
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    if "{" in content:
        return content
    if "{" in reasoning:
        return reasoning
    combined = (content + "\n" + reasoning).strip()
    if "{" in combined:
        return combined
    raise RuntimeError(f"{model} returned no JSON object")

def ideate_model() -> str:
    return os.getenv("NVIDIA_IDEATE_MODEL", "openai/gpt-oss-20b")

def script_model() -> str:
    return os.getenv("NVIDIA_SCRIPT_MODEL", "openai/gpt-oss-20b")
