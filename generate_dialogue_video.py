import asyncio
import edge_tts
import argparse
import json
import os
import subprocess
import re
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

try:
    from pipeline.env import load_project_env
    load_project_env()
except Exception:
    pass

# ==========================================
# 0. PYTORCH 2.6+ RVC COMPATIBILITY PATCH (optional — only needed for RVC)
# ==========================================
try:
    import torch

    _orig_torch_load = torch.load
    def _safe_torch_load(*args, **kwargs):
        kwargs["weights_only"] = False
        return _orig_torch_load(*args, **kwargs)
    torch.load = _safe_torch_load

    try:
        import fairseq.data.dictionary
        torch.serialization.add_safe_globals([fairseq.data.dictionary.Dictionary])
    except Exception:
        pass
except ImportError:
    torch = None  # RVC unavailable; --no-rvc / base-audio fallback still works

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# ==========================================
# 1. SETTINGS & VOCAL TUNING
# ==========================================
# Tune Leo's pitch here: (+4 to +6 gives Morty's high-pitch comedic tone)
LEO_PITCH_SHIFT = -4
RICK_PITCH_SHIFT = -2

# Pitch algorithm on CPU: 'pm' (Parselmouth) is clean and artifact-free on CPU
F0_METHOD = "pm"  

# Snappy Reels speed (+18%)
SPEED_RATE = "+18%"
SPEAKER_PAUSE_DURATION = "0.20"

def resolve_model_path(base_name):
    candidates = [
        f"models/{base_name}.pth",
        f"models/{base_name.capitalize()}.pth",
        f"models/{base_name.lower()}.pth"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

def resolve_index_path(base_name):
    candidates = [
        f"models/{base_name}.index",
        f"models/{base_name.capitalize()}.index",
        f"models/{base_name.lower()}.index"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

MORTY_MODEL = resolve_model_path("morty")
MORTY_INDEX = resolve_index_path("morty")

RICK_MODEL = resolve_model_path("rick")
RICK_INDEX = resolve_index_path("rick")

VOICE_LEO_BASE = "en-US-GuyNeural"
VOICE_ALEX_BASE = "en-US-BrianNeural"

# NVIDIA Magpie voices (used with --tts nvidia; same NVIDIA_NIM_API_KEY)
VOICE_LEO_NVIDIA = os.getenv("NVIDIA_TTS_VOICE_LEO", "Magpie-Multilingual.EN-US.Jason.Happy")
VOICE_ALEX_NVIDIA = os.getenv("NVIDIA_TTS_VOICE_ALEX", "Magpie-Multilingual.EN-US.Jason")

# ==========================================
# 2. DIALOGUE SCRIPT (default; override with --script script.json)
# ==========================================
# Expected script.json schema (matches your system_prompt):
# {
#   "topic": "...",
#   "pillar": "Pillar 1 | Pillar 2 | Pillar 3",
#   "dialogue": [{"speaker": "Leo"|"Alex", "text": "..."}],
#   "cards": {"INSIGHT": {...}, "CTA": {...}}  # optional, falls back to CARD_*_DATA
# }
DEFAULT_DIALOGUE = [
    {
        "speaker": "A",
        "name": "Leo",
        "voice": VOICE_LEO_BASE,
        "rvc_model": MORTY_MODEL,
        "rvc_index": MORTY_INDEX,
        "pitch_shift": LEO_PITCH_SHIFT,
        "text": "Yo Alex! Did you see the news?"
    },
    {
        "speaker": "A",
        "name": "Leo",
        "voice": VOICE_LEO_BASE,
        "rvc_model": MORTY_MODEL,
        "rvc_index": MORTY_INDEX,
        "pitch_shift": LEO_PITCH_SHIFT,
        "text": "AI agents just built an entire SaaS app in ten minutes! Are junior devs cooked?"
    },
    {
        "speaker": "B",
        "name": "Alex",
        "voice": VOICE_ALEX_BASE,
        "rvc_model": RICK_MODEL,
        "rvc_index": RICK_INDEX,
        "pitch_shift": RICK_PITCH_SHIFT,
        "text": "Relax Leo! Writing basic syntax is dead, but understanding systems is not."
    },
    {
        "speaker": "A",
        "name": "Leo",
        "voice": VOICE_LEO_BASE,
        "rvc_model": MORTY_MODEL,
        "rvc_index": MORTY_INDEX,
        "pitch_shift": LEO_PITCH_SHIFT,
        "text": "Wait, what does that even mean?"
    },
    {
        "speaker": "B",
        "name": "Alex",
        "voice": VOICE_ALEX_BASE,
        "rvc_model": RICK_MODEL,
        "rvc_index": RICK_INDEX,
        "pitch_shift": RICK_PITCH_SHIFT,
        "text": "AI can spit out boilerplate, but it cannot architect production databases!",
        "show_card": "INSIGHT",
        "card_duration": 2.6
    },
    {
        "speaker": "A",
        "name": "Leo",
        "voice": VOICE_LEO_BASE,
        "rvc_model": MORTY_MODEL,
        "rvc_index": MORTY_INDEX,
        "pitch_shift": LEO_PITCH_SHIFT,
        "text": "Bro, so what should we actually learn in 2026?"
    },
    {
        "speaker": "B",
        "name": "Alex",
        "voice": VOICE_ALEX_BASE,
        "rvc_model": RICK_MODEL,
        "rvc_index": RICK_INDEX,
        "pitch_shift": RICK_PITCH_SHIFT,
        "text": "Master Vector Databases, Local LLMs, and MCP Tool Calling."
    },
    {
        "speaker": "B",
        "name": "Alex",
        "voice": VOICE_ALEX_BASE,
        "rvc_model": RICK_MODEL,
        "rvc_index": RICK_INDEX,
        "pitch_shift": RICK_PITCH_SHIFT,
        "text": "I put the complete 2026 AI Engineer Roadmap..."
    },
    {
        "speaker": "B",
        "name": "Alex",
        "voice": VOICE_ALEX_BASE,
        "rvc_model": RICK_MODEL,
        "rvc_index": RICK_INDEX,
        "pitch_shift": RICK_PITCH_SHIFT,
        "text": "and all starter templates in the bio link!",
        # CTA Card triggers right on this punchline:
        "show_card": "CTA"
    }
]

# Active dialogue (replaced by --script at runtime)
DIALOGUE = DEFAULT_DIALOGUE

CARD_1_DATA = {
    "badge_icon": "🤖",
    "badge_text": "THE 2026 AI SHIFT",
    "badge_color": (14, 165, 233),
    "headline_top": "SYNTAX WRITING IS DEAD",
    "headline_hl": "= AGENTS ARE THE NEW META",
    "headline_sub": "Stop learning for loops. Learn system architecture.",
    "hl_color": (56, 189, 248),
    "footer_left": "SKILLS THAT WON'T BE AUTOMATED ↓",
    "footer_badge": "SWIPE FOR ROADMAP →"
}

CARD_2_DATA = {
    "badge_icon": "⚡",
    "badge_text": "AI DEVELOPER TOOLKIT",
    "badge_color": (16, 185, 129),
    "headline_top": "2026 AI ENGINEER ROADMAP",
    "headline_hl": "AGENT WORKFLOWS & TEMPLATES",
    "headline_sub": "Vector DBs • Local LLM Setup • MCP Protocols",
    "hl_color": (52, 211, 153),
    "footer_left": "COMPLETE PDF ROADMAP + SOURCE CODE",
    "footer_badge": "RESOURCE #12 IN BIO"
}

GAMEPLAY_BG = "background/gameplay.mp4"
CHAR_A_PNG = "assests/char_a.png"
CHAR_B_PNG = "assests/char_b.png"
OUTPUT_VIDEO = "output/dialogue_reel.mp4"

# ==========================================
# 3. RVC VOICE CONVERTER ENGINE (ANTI-DELAY)
# ==========================================
_rvc_engine = None

def get_rvc_engine():
    global _rvc_engine
    if _rvc_engine is None:
        try:
            from rvc_python.infer import RVCInference
            print("Initializing RVC Engine on CPU...")
            _rvc_engine = RVCInference(device="cpu")
        except Exception as e:
            print(f"[RVC Init Error] {e}")
    return _rvc_engine

def apply_rvc_voice(input_wav, output_wav, model_path, index_path=None, pitch=0):
    """Converts audio and strips RVC leading silence so audio never lags behind captions."""
    if not os.path.exists(model_path):
        print(f"[Warning] Model file '{model_path}' not found. Using base audio.")
        import shutil
        shutil.copyfile(input_wav, output_wav)
        return

    rvc = get_rvc_engine()
    if rvc is None:
        import shutil
        shutil.copyfile(input_wav, output_wav)
        return

    temp_raw_rvc = output_wav + ".raw.wav"
    try:
        print(f"Converting to character voice: {os.path.basename(model_path)} (pitch={pitch})...")
        rvc.load_model(model_path, index_path=index_path)
        
        # Safe index handling: if index file doesn't exist, index_rate must be 0 to avoid metallic buzz
        effective_index_rate = 0.35 if index_path and os.path.exists(index_path) else 0.0

        rvc.set_params(
            f0up_key=pitch,
            f0method=F0_METHOD,
            index_rate=effective_index_rate,
            filter_radius=3,
            rms_mix_rate=0.25,
            protect=0.50
        )
        rvc.infer_file(input_wav, temp_raw_rvc)

        # 1. silenceremove strips RVC's leading silence (fixes the delay/sync drift)
        # 2. Resamples to standard 44.1kHz stereo to eliminate sample-rate buzz
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", temp_raw_rvc,
            "-ar", "44100", "-ac", "2",
            "-af", "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB,volume=0.92,highpass=f=60,lowpass=f=12000",
            "-c:a", "pcm_s16le", output_wav
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if os.path.exists(temp_raw_rvc):
            os.remove(temp_raw_rvc)

    except Exception as e:
        print(f"[RVC Error] Conversion failed ({e}). Falling back to base audio.")
        import shutil
        shutil.copyfile(input_wav, output_wav)

# ==========================================
# 4. CARD DESIGN ENGINE
# ==========================================
def get_font(size, bold=False):
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()

CARD_COLOR_THEMES = [
    {"badge_color": (14, 165, 233), "hl_color": (56, 189, 248)},    # blue (insight)
    {"badge_color": (16, 185, 129), "hl_color": (52, 211, 153)},    # green (cta)
    {"badge_color": (168, 85, 247), "hl_color": (192, 132, 252)},   # purple
    {"badge_color": (249, 115, 22), "hl_color": (253, 186, 116)},   # orange
]

def draw_pro_card(data, output_path):
    # Fill defaults so AI-written cards only need text fields
    theme = CARD_COLOR_THEMES[0]
    data = {**{"badge_icon": "⚡", "badge_text": "NOTE",
               "headline_top": "", "headline_hl": "",
               "headline_sub": "", "footer_left": "",
               "footer_badge": "BIO LINK ↓",
               "badge_color": theme["badge_color"],
               "hl_color": theme["hl_color"]}, **data}
    os.makedirs("temp", exist_ok=True)
    W, H = 960, 430
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=32, fill=(12, 14, 20, 248), outline=(48, 56, 76, 255), width=3)
    draw.ellipse([40, 30, 56, 46], fill=(255, 95, 86))
    draw.ellipse([66, 30, 82, 46], fill=(255, 189, 46))
    draw.ellipse([92, 30, 108, 46], fill=(39, 201, 63))

    f_badge = get_font(24, bold=True)
    b_color = data["badge_color"]
    b_w = 400
    # Solid pill (alpha fills are unreliable across Pillow versions) + white text
    # works whether the compositor blends or not.
    draw.rounded_rectangle([W - b_w - 40, 20, W - 40, 56], radius=16, fill=b_color)
    bx = W - b_w - 20
    try:
        emoji_font = ImageFont.truetype(r"C:\Windows\Fonts\seguiemj.ttf", 24)
    except Exception:
        try:
            emoji_font = ImageFont.truetype("seguiemj.ttf", 24)
        except Exception:
            emoji_font = None
    if emoji_font:
        try:
            draw.text((bx, 24), data["badge_icon"] + " ", font=emoji_font,
                      fill=(255, 255, 255), embedded_color=True)
            bx += draw.textlength(data["badge_icon"] + " ", font=emoji_font)
        except Exception:
            pass
    draw.text((bx, 24), data["badge_text"], font=f_badge, fill=(255, 255, 255))

    f_head = get_font(46, bold=True)
    draw.text((45, 95), data["headline_top"], font=f_head, fill=(255, 255, 255))
    draw.text((45, 155), data["headline_hl"], font=f_head, fill=data["hl_color"])
    
    f_subline = get_font(32, bold=False)
    draw.text((45, 220), data["headline_sub"], font=f_subline, fill=(203, 213, 225))

    draw.line([(45, H - 75), (W - 45, H - 75)], fill=(35, 42, 58), width=2)
    f_foot = get_font(26, bold=True)
    draw.text((45, H - 54), data["footer_left"], font=f_foot, fill=(148, 163, 184))
    
    f_pill = get_font(22, bold=True)
    draw.rounded_rectangle([W - 330, H - 64, W - 45, H - 20], radius=12, fill=(16, 185, 129, 40), outline=(16, 185, 129, 210), width=2)
    draw.text((W - 315, H - 54), data["footer_badge"], font=f_pill, fill=(52, 211, 153))

    im.save(output_path)
    return output_path

# ==========================================
# 5. AUDIO & TIMING UTILITIES
# ==========================================
def get_audio_duration(file_path):
    cmd = [FFMPEG_PATH, "-i", file_path]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0

def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs -= 100
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def split_line_into_timed_chunks(text, line_start, line_duration, target_chunk_size=3):
    words = text.split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), target_chunk_size):
        chunk = words[i:i + target_chunk_size]
        if chunks and len(chunk) == 1:
            chunks[-1].extend(chunk)
        else:
            chunks.append(chunk)

    num_chunks = len(chunks)
    chunk_dur = line_duration / num_chunks
    result = []
    for idx, c in enumerate(chunks):
        s_t = line_start + (idx * chunk_dur)
        e_t = line_start + ((idx + 1) * chunk_dur)
        result.append((s_t, e_t, " ".join(c).upper()))
    return result

async def generate_dialogue_audio(tts_mode="edge"):
    # tts_mode="offline": no network — synth timing-estimated tone audio per line
    # (validates captions/cards/compositing when Bing blocks edge-tts). Not for publish.
    os.makedirs("temp", exist_ok=True)
    
    pause_file = "temp/pause.wav"
    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-t", SPEAKER_PAUSE_DURATION, "-c:a", "pcm_s16le", pause_file
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    audio_wav_list = []
    speaker_timings = {"A": [], "B": []}
    dialogue_events = []
    card_intervals = []
    current_time = 0.0

    print("Synthesizing speech with anti-delay synchronization...")
    edge_blocked = False  # auto-fallback: first edge 403 switches rest to NVIDIA voices
    for i, line in enumerate(DIALOGUE):
        raw_mp3 = f"temp/raw_{i}.mp3"
        base_wav = f"temp/base_{i}.wav"
        char_wav = f"temp/char_{i}.wav"

        def _synth_nvidia():
            from pipeline.nvidia_tts import (
                synth, VOICE_LEO, VOICE_ALEX,
                TEMPO_LEO, TEMPO_ALEX, PITCH_LEO, PITCH_ALEX,
            )
            nvidia_voice = VOICE_LEO if line["speaker"] == "A" else VOICE_ALEX
            tempo = TEMPO_LEO if line["speaker"] == "A" else TEMPO_ALEX
            pitch = PITCH_LEO if line["speaker"] == "A" else PITCH_ALEX
            n_words = len(line["text"].split())
            print(f"  [nvidia-tts] {line['name']}: {line['text'][:50]}...")
            # Retry once if TTS returns clipped audio (too short for word count)
            for tts_try in range(2):
                synth(line["text"], nvidia_voice, raw_mp3)  # raw_mp3 reused as temp wav holder
                filters = []
                if abs(pitch - 1.0) > 0.01:
                    # Higher pitch, then restore natural pacing
                    filters.append(f"asetrate=44100*{pitch},aresample=44100,atempo={1.0 / pitch}")
                filters.append(f"atempo={tempo}")
                filters.append("aresample=44100")
                # 0.35s tail pad: natural decay + guards mux/encoder trimming last word
                filters.append("apad=pad_dur=0.35")
                subprocess.run([
                    FFMPEG_PATH, "-y", "-i", raw_mp3,
                    "-af", ",".join(filters),
                    "-ac", "2", "-c:a", "pcm_s16le", base_wav
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                got = get_audio_duration(base_wav) - 0.35
                if got >= n_words * 0.22 or tts_try == 1:
                    if tts_try == 1 and got < n_words * 0.22:
                        print(f"  [warn] line audio short ({got:.1f}s for {n_words}w), keeping anyway")
                    break
                print(f"  [nvidia-tts] clipped ({got:.1f}s), re-synthing...")

        # 1. Base TTS Audio
        if tts_mode == "offline":
            est = max(1.2, len(line["text"].split()) * 0.38)  # ~160wpm estimate
            freq = 220 if line["speaker"] == "A" else 175
            subprocess.run([
                FFMPEG_PATH, "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={est:.2f}",
                "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", base_wav
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif tts_mode == "nvidia" or edge_blocked:
            _synth_nvidia()
        else:
            try:
                communicate = edge_tts.Communicate(line["text"], line["voice"], rate=SPEED_RATE)
                await communicate.save(raw_mp3)
            except Exception as e:
                print(f"  [edge-tts blocked: {type(e).__name__}] "
                      f"switching line {i} onwards to NVIDIA voices...")
                edge_blocked = True
                _synth_nvidia()
            else:
                subprocess.run([
                    FFMPEG_PATH, "-y", "-i", raw_mp3,
                    "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", base_wav
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. RVC Voice Model Transformation
        apply_rvc_voice(
            input_wav=base_wav,
            output_wav=char_wav,
            model_path=line["rvc_model"],
            index_path=line.get("rvc_index"),
            pitch=line.get("pitch_shift", 0)
        )

        duration = get_audio_duration(char_wav)
        speaker = line["speaker"]
        style_name = "SpeakerA" if speaker == "A" else "SpeakerB"

        line_start = current_time
        line_end = current_time + duration
        speaker_timings[speaker].append((line_start, line_end))

        # Check for card triggers (AI trigger-word cards first, legacy INSIGHT/CTA second)
        if line.get("card"):
            card_data = dict(line["card"])
            theme = CARD_COLOR_THEMES[card_data.pop("_theme", 0) % len(CARD_COLOR_THEMES)]
            card_data.setdefault("badge_color", theme["badge_color"])
            card_data.setdefault("hl_color", theme["hl_color"])
            idx = len(card_intervals)
            c_path = draw_pro_card(card_data, f"temp/card_{idx}.png")
            if i == len(DIALOGUE) - 1:
                card_end = None  # final CTA card persists to end of video
            else:
                card_end = min(line_end, line_start + line.get("card_duration", 2.8))
            card_intervals.append([c_path, line_start, card_end])
            print(f"  [card] '{card_data.get('trigger', '')}' spoken at {line_start:.1f}s -> card_{idx}.png")
        elif line.get("show_card") == "INSIGHT":
            c1_path = draw_pro_card(CARD_1_DATA, "temp/card_insight.png")
            card_end = min(line_end, line_start + line.get("card_duration", 2.6))
            card_intervals.append([c1_path, line_start, card_end])
        elif line.get("show_card") == "CTA":
            c2_path = draw_pro_card(CARD_2_DATA, "temp/card_cta.png")
            card_intervals.append([c2_path, line_start, None])

        # Bounded 3-word kinetic captions
        clean_text = line["text"].replace("...", "").replace("  ", " ")
        timed_chunks = split_line_into_timed_chunks(clean_text, line_start, duration, target_chunk_size=3)
        for s_t, e_t, chunk_str in timed_chunks:
            dialogue_events.append(
                f"Dialogue: 0,{format_ass_time(s_t)},{format_ass_time(e_t)},{style_name},,0,0,0,,{chunk_str}"
            )

        audio_wav_list.append(char_wav)
        audio_wav_list.append(pause_file)
        current_time = line_end + float(SPEAKER_PAUSE_DURATION)

    total_duration = current_time

    for c in card_intervals:
        if c[2] is None:
            c[2] = total_duration

    # High Subtitles: MarginV=290
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SpeakerA,Arial,60,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,40,40,290,1
Style: SpeakerB,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,40,40,290,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_path = "temp/captions.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(dialogue_events))

    concat_list = "temp/wav_list.txt"
    with open(concat_list, "w") as f:
        for file in audio_wav_list:
            f.write(f"file '{os.path.abspath(file)}'\n")

    combined_audio = "temp/combined_voiceover.wav"
    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c:a", "pcm_s16le", combined_audio
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return combined_audio, ass_path, speaker_timings, card_intervals, total_duration

def build_enable_expr(intervals):
    if not intervals:
        return "0"
    return "+".join([f"between(t,{start:.2f},{end:.2f})" for start, end in intervals])

# ==========================================
# 6. FINAL COMPOSITING ENGINE
# ==========================================
def assemble_video(audio_path, ass_path, speaker_timings, card_intervals, total_duration):
    os.makedirs("output", exist_ok=True)
    
    enable_a = build_enable_expr(speaker_timings["A"])
    enable_b = build_enable_expr(speaker_timings["B"])
    clean_ass = ass_path.replace("\\", "/").replace(":", "\\:")

    bounce_a_y = "H-h-640-10*abs(sin(2*PI*1.4*t))"
    bounce_b_y = "H-h-450-10*abs(sin(2*PI*1.4*t))"

    card_inputs = []
    filter_parts = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];",
        "[1:v]scale=-2:650:flags=lanczos[char1];",
        "[2:v]scale=-2:650:flags=lanczos[char2];"
    ]
    
    last_v = "bg"
    for idx, (c_path, c_start, c_end) in enumerate(card_intervals):
        input_idx = 3 + idx
        card_inputs.extend(["-loop", "1", "-i", c_path])
        filter_parts.append(f"[{input_idx}:v]scale=960:-2:flags=lanczos[card_{idx}];")
        next_v = f"bg_c{idx}"
        filter_parts.append(
            f"[{last_v}][card_{idx}]overlay=(W-w)/2:140:enable='between(t,{c_start:.2f},{c_end:.2f})'[{next_v}];"
        )
        last_v = next_v

    filter_parts.append(f"[{last_v}][char1]overlay=60:'{bounce_a_y}':enable='{enable_a}'[tmp];")
    filter_parts.append(f"[tmp][char2]overlay=W-w-60:'{bounce_b_y}':enable='{enable_b}'[v_chars];")
    filter_parts.append(f"[v_chars]subtitles='{clean_ass}'[outv]")

    filter_complex = "".join(filter_parts)
    audio_idx = 3 + len(card_intervals)

    cmd = [
        FFMPEG_PATH, "-y",
        "-stream_loop", "-1", "-i", GAMEPLAY_BG,
        "-loop", "1", "-i", CHAR_A_PNG,
        "-loop", "1", "-i", CHAR_B_PNG,
        *card_inputs,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ]

    print("Rendering video with anti-delay synchronization...")
    subprocess.run(cmd, check=True)
    print(f"Done! Final video generated at: {OUTPUT_VIDEO}")

def load_script_file(path):
    """Load pipeline script.json -> DIALOGUE list. Supports both engine and LLM schema.
    AI cards: script["cards"] = [{"trigger": "phrase spoken in one line", ...text fields}].
    A card is shown while the line containing its trigger is spoken."""
    global DIALOGUE, CARD_1_DATA, CARD_2_DATA
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Allow {"dialogue": [...]} (LLM schema) or raw list
    items = data.get("dialogue", data) if isinstance(data, dict) else data
    raw_cards = data.get("cards", []) if isinstance(data, dict) else []
    if isinstance(raw_cards, dict):
        # Legacy {"INSIGHT": {...}, "CTA": {...}} format
        if "INSIGHT" in raw_cards:
            CARD_1_DATA.update(raw_cards["INSIGHT"])
        if "CTA" in raw_cards:
            CARD_2_DATA.update(raw_cards["CTA"])
        ai_cards = []
    else:
        ai_cards = [c for c in raw_cards if isinstance(c, dict) and c.get("trigger")]
    dialogue = []
    for i, item in enumerate(items):
        speaker_raw = str(item.get("speaker", "Leo")).strip()
        is_leo = speaker_raw.lower().startswith("leo") or speaker_raw == "A"
        text = item["text"]
        # 1. AI trigger-word cards (preferred): trigger phrase spoken in this line
        matched_card = None
        for ci, card in enumerate(ai_cards):
            if str(card["trigger"]).strip().lower() in text.lower():
                matched_card = {**card, "_theme": ci % len(CARD_COLOR_THEMES)}
                break
        show_card = item.get("show_card")
        if matched_card:
            pass  # handled below via "card" key
        elif not show_card and isinstance(items, list) and not ai_cards:
            # 2. Legacy fallback only when script has no AI cards at all
            if i == 4:
                show_card = "INSIGHT"
            if i == len(items) - 1:
                show_card = "CTA"
        dialogue.append({
            "speaker": "A" if is_leo else "B",
            "name": "Leo" if is_leo else "Alex",
            "voice": VOICE_LEO_BASE if is_leo else VOICE_ALEX_BASE,
            "rvc_model": MORTY_MODEL if is_leo else RICK_MODEL,
            "rvc_index": MORTY_INDEX if is_leo else RICK_INDEX,
            "pitch_shift": LEO_PITCH_SHIFT if is_leo else RICK_PITCH_SHIFT,
            "text": item["text"],
            **({"card": matched_card, "card_duration": 2.8} if matched_card else {}),
            **({"show_card": show_card} if show_card else {}),
            **({"card_duration": 2.6} if show_card == "INSIGHT" else {}),
        })
    n_ai = sum(1 for d in dialogue if d.get("card"))
    print(f"AI cards matched: {n_ai}/{len(ai_cards)} triggers spoken")
    DIALOGUE = dialogue
    total_words = sum(len(d["text"].split()) for d in dialogue)
    print(f"Loaded script: {path} | lines={len(dialogue)} words={total_words} (target 110-135)")
    return dialogue


async def main(script_path=None, output_path=None, tts_mode="edge"):
    global OUTPUT_VIDEO
    if script_path:
        load_script_file(script_path)
    if output_path:
        OUTPUT_VIDEO = output_path
    audio_path, ass_path, speaker_timings, card_intervals, total_duration = await generate_dialogue_audio(tts_mode)
    assemble_video(audio_path, ass_path, speaker_timings, card_intervals, total_duration)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dialogue Reel renderer (automation-studio ready)")
    parser.add_argument("--script", default=None, help="Path to script.json {topic,pillar,dialogue[]}")
    parser.add_argument("--output", default=None, help="Override output mp4 path")
    parser.add_argument("--no-rvc", action="store_true", help="Skip RVC, use edge-tts only (fast CI fallback)")
    parser.add_argument("--tts", default="edge", choices=["edge", "nvidia", "offline"],
                        help="edge: edge-tts Guy/BrianNeural, auto-falls-back to NVIDIA voices "
                             "if Microsoft blocks the request. "
                             "nvidia: Magpie Leo/Alex voices (uses NVIDIA key). "
                             "offline: synth tones, no network (pipeline test only)")
    args = parser.parse_args()
    if args.no_rvc:
        # Force fallback by pointing models to missing files
        MORTY_MODEL = "__disabled__"
        RICK_MODEL = "__disabled__"
    asyncio.run(main(script_path=args.script, output_path=args.output, tts_mode=args.tts))