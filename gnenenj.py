import asyncio
import edge_tts
import os
import subprocess
import re
import imageio_ffmpeg

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

DIALOGUE = [
    {"speaker": "A", "voice": "en-US-GuyNeural", "text": "Bro, how are people landing coding interviews without grinding 500 LeetCode questions?"},
    {"speaker": "B", "voice": "en-US-ChristopherNeural", "text": "Because grinding randomly is a waste of time. You only need five core algorithm patterns."},
    {"speaker": "A", "voice": "en-US-GuyNeural", "text": "Wait, which patterns?"},
    {"speaker": "B", "voice": "en-US-ChristopherNeural", "text": "Two Pointers, Sliding Window, and Fast and Slow Pointers. I put the full cheat sheet in the vault link."}
]

GAMEPLAY_BG = "background/gameplay.mp4"
CHAR_A_PNG = "assests/char_a.png"
CHAR_B_PNG = "assests/char_b.png"
OUTPUT_VIDEO = "output/dialogue_reel.mp4"

# Set distance of character base from bottom (520px leaves clean room for bottom captions)
CHAR_Y_OFFSET = 520

def get_audio_duration(file_path):
    """Accurately reads the duration of an audio file using FFmpeg."""
    cmd = [FFMPEG_PATH, "-i", file_path]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0

def format_ass_time(seconds):
    """Formats float seconds into ASS timestamp H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs -= 100
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def split_into_word_chunks(text, chunk_size=3):
    """Splits a sentence into 3 to 4 word chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        if chunks and len(chunk) == 1:
            chunks[-1].extend(chunk)
        else:
            chunks.append(chunk)
    return [" ".join(c) for c in chunks]

async def generate_dialogue_audio():
    os.makedirs("temp", exist_ok=True)
    
    # Clean 0.25s silence pause
    pause_file = "temp/pause.wav"
    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "lavfi",
        "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "0.25", "-c:a", "pcm_s16le", pause_file
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    audio_wav_list = []
    speaker_timings = {"A": [], "B": []}
    dialogue_events = []
    current_time = 0.0

    print("Generating speech with anti-click audio processing...")
    for i, line in enumerate(DIALOGUE):
        raw_mp3 = f"temp/raw_{i}.mp3"
        clean_wav = f"temp/clean_{i}.wav"

        communicate = edge_tts.Communicate(line["text"], line["voice"])
        await communicate.save(raw_mp3)

        raw_duration = get_audio_duration(raw_mp3)
        fade_out_start = max(0.0, raw_duration - 0.015)

        # Filters: 15ms fade-in/out to remove edge clicks, 48kHz resampling, and soft limiter to stop clipping
        audio_filters = (
            f"aresample=48000,volume=0.92,alimiter=limit=0.95,"
            f"afade=t=in:ss=0:d=0.015,afade=t=out:st={fade_out_start:.3f}:d=0.015"
        )

        subprocess.run([
            FFMPEG_PATH, "-y", "-i", raw_mp3,
            "-af", audio_filters,
            "-c:a", "pcm_s16le", clean_wav
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        duration = get_audio_duration(clean_wav)
        speaker = line["speaker"]
        style_name = "SpeakerA" if speaker == "A" else "SpeakerB"

        line_start = current_time
        line_end = current_time + duration
        speaker_timings[speaker].append((line_start, line_end))

        # 3-4 word chunked captions
        chunks = split_into_word_chunks(line["text"], chunk_size=3)
        total_words = len(line["text"].split())
        
        chunk_t = line_start
        for chunk in chunks:
            chunk_word_count = len(chunk.split())
            chunk_duration = duration * (chunk_word_count / total_words)
            chunk_end = chunk_t + chunk_duration

            dialogue_events.append(
                f"Dialogue: 0,{format_ass_time(chunk_t)},{format_ass_time(chunk_end)},{style_name},,0,0,0,,{chunk.upper()}"
            )
            chunk_t = chunk_end

        audio_wav_list.append(clean_wav)
        audio_wav_list.append(pause_file)
        current_time = line_end + 0.25

    # ASS subtitles: locked to 1080x1920 canvas, placed right at bottom (MarginV=210)
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SpeakerA,Arial,60,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,40,40,210,1
Style: SpeakerB,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,40,40,210,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_path = "temp/captions.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(dialogue_events))

    # Concat clean WAV audio
    concat_list = "temp/wav_list.txt"
    with open(concat_list, "w") as f:
        for file in audio_wav_list:
            f.write(f"file '{os.path.abspath(file)}'\n")

    combined_audio = "temp/combined_voiceover.wav"
    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c:a", "pcm_s16le", combined_audio
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return combined_audio, ass_path, speaker_timings

def build_enable_expr(intervals):
    if not intervals:
        return "0"
    return "+".join([f"between(t,{start:.2f},{end:.2f})" for start, end in intervals])

def assemble_video(audio_path, ass_path, speaker_timings):
    os.makedirs("output", exist_ok=True)
    
    enable_a = build_enable_expr(speaker_timings["A"])
    enable_b = build_enable_expr(speaker_timings["B"])
    clean_ass = ass_path.replace("\\", "/").replace(":", "\\:")


   # Character A is placed HIGHER UP (H-h-640), Character B is LOWER DOWN (H-h-450)
    # Slowed down from 2.8 to 1.2 with a gentle 10px breathing float
    bounce_a_y = "H-h-700-10*abs(sin(2*PI*1.2*t))"   # Character A (Higher Up)
    bounce_b_y = "H-h-400-10*abs(sin(2*PI*1.2*t))"   # Character B (Lower Down)

    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];"
        "[1:v]scale=-2:650:flags=lanczos[char1];"
        "[2:v]scale=-2:650:flags=lanczos[char2];"
        f"[bg][char1]overlay=60:'{bounce_a_y}':enable='{enable_a}'[tmp];"
        f"[tmp][char2]overlay=W-w-60:'{bounce_b_y}':enable='{enable_b}'[v_chars];"
        f"[v_chars]subtitles='{clean_ass}'[outv]"
    )

    cmd = [
        FFMPEG_PATH, "-y",
        "-stream_loop", "-1", "-i", GAMEPLAY_BG,
        "-loop", "1", "-i", CHAR_A_PNG,
        "-loop", "1", "-i", CHAR_B_PNG,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "3:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ]

    print("Rendering video with animated speaking characters...")
    subprocess.run(cmd, check=True)
    print(f"Video saved at: {OUTPUT_VIDEO}")

async def main():
    audio_path, ass_path, speaker_timings = await generate_dialogue_audio()
    assemble_video(audio_path, ass_path, speaker_timings)

if __name__ == "__main__":
    asyncio.run(main())