import os, io, textwrap, math, random, tempfile, base64
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
)
from gtts import gTTS
from pydub import AudioSegment
from imageio_ffmpeg import get_ffmpeg_exe
AudioSegment.converter = get_ffmpeg_exe()

IMG_W, IMG_H = 1080, 1920
FPS = 24

# ---------- Scene splitter ----------

def split_story_into_scenes(story: str, max_chars=140) -> List[str]:
    story = " ".join(story.split())
    sentences = [s.strip() for s in story.replace("\n", " ").split('.') if s.strip()]
    scenes, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= max_chars:
            buf = (buf + " " + s).strip()
        else:
            if buf: scenes.append(buf)
            buf = s
    if buf: scenes.append(buf)
    return scenes[:10]  # cap scenes for Shorts

# ---------- Image generation ----------

def generate_image(prompt: str, provider: str = None):
    provider = provider or os.getenv("IMAGE_PROVIDER", "openai")
    if provider == "local":
        img = Image.new("RGB", (IMG_W, IMG_H), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        draw.text((40, 40), prompt[:60]+"…", fill=(230,230,230))
        return img

    if provider == "url":
        resp = requests.get(prompt, timeout=30)
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        return img.resize((IMG_W, IMG_H))

    # default: openai images
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Or set IMAGE_PROVIDER=local")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": "gpt-image-1", "prompt": prompt, "size": "1024x1792"}
    r = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=data, timeout=120)
    r.raise_for_status()
    b64 = r.json()["data"][0]["b64_json"]
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    return img.resize((IMG_W, IMG_H))

# ---------- Text-to-speech ----------

def tts_to_wav(text: str, lang: str) -> AudioSegment:
    tts = gTTS(text=text, lang=lang)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmpmp3 = f.name
    tts.save(tmpmp3)
    audio = AudioSegment.from_file(tmpmp3)
    os.remove(tmpmp3)
    return audio.set_frame_rate(44100).set_channels(2)

# ---------- Utilities ----------

def wrap_caption(text: str, width=22):
    return "\n".join(textwrap.wrap(text, width))

def add_text_overlay(pil_img, caption: str):
    img = pil_img.copy()
    draw = ImageDraw.Draw(img)
    try:
        font_path = os.path.join("assets", "fonts", "NotoSansTamil-SemiBold.ttf")
        font = ImageFont.truetype(font_path, 60)
    except Exception:
        font = ImageFont.load_default()

    cx, cy = IMG_W // 2, int(IMG_H * 0.82)
    for dx, dy in [(-2,-2), (2,2), (-2,2), (2,-2)]:
        draw.multiline_text((cx+dx, cy+dy), caption, anchor="mm", align="center", fill=(0,0,0), font=font, spacing=6)
    draw.multiline_text((cx, cy), caption, anchor="mm", align="center", fill=(255,255,255), font=font, spacing=6)
    return img

# ---------- BGM ----------

def pick_bgm():
    bgm_dir = os.path.join("assets", "bgm")
    if not os.path.isdir(bgm_dir) or not os.listdir(bgm_dir):
        return None
    path = os.path.join(bgm_dir, random.choice(os.listdir(bgm_dir)))
    return AudioSegment.from_file(path).set_frame_rate(44100).set_channels(2) - 12

# ---------- Single video ----------

def build_video_from_story(story_text: str, deity: str = "Generic", voice_lang: str = "ta", target_duration: int = 20, out_path: str = "outputs/out.mp4") -> Dict:
    try:
        scenes = split_story_into_scenes(story_text)
        per_scene = max(3, min(6, math.floor(target_duration / max(1, len(scenes)))))

        narration = tts_to_wav(" ".join(scenes), lang=voice_lang)
        bgm = pick_bgm()

        clips = []
        for s in scenes:
            prompt = f"{deity} devotional portrait, temple, flowers, cinematic lighting, 9:16"
            pil = generate_image(prompt)
            caption = wrap_caption(s, 22)
            pil = add_text_overlay(pil, caption)

            clip = ImageClip(pil).set_duration(per_scene)
            clip = clip.resize(lambda t: 1 + 0.03 * t).set_position("center")
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")

        narr_wav = narration[: int(video.duration * 1000)]
        narr_clip_path = tempfile.mktemp(suffix=".mp3")
        narr_wav.export(narr_clip_path, format="mp3")
        narr = AudioFileClip(narr_clip_path)

        if bgm:
            loops = math.ceil(video.duration * 1000 / len(bgm))
            bgm_long = sum([bgm] * loops)
            bgm_long = bgm_long[: int(video.duration * 1000)] - 6
            bgm_path = tempfile.mktemp(suffix=".mp3")
            bgm_long.export(bgm_path, format="mp3")
            music = AudioFileClip(bgm_path).volumex(0.6)
            audio = CompositeAudioClip([music, narr.volumex(1.0)])
        else:
            audio = narr

        final = video.set_audio(audio)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        final.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac")
        return {"ok": True, "out_path": out_path}

    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------- Batch chapters ----------

def build_batch_videos(chapters: List[Dict], deity: str, voice_lang: str, out_dir: str) -> Dict:
    results = []
    playlist_lines = []
    for idx, ch in enumerate(chapters, start=1):
        title = ch.get("title", f"Chapter {idx}")
        story = ch.get("story", "").strip()
        duration = int(ch.get("duration", 24))
        fname = f"chapter-{idx:02d}.mp4"
        out_path = os.path.join(out_dir, fname)

        res = build_video_from_story(story, deity=deity, voice_lang=voice_lang, target_duration=duration, out_path=out_path)
        results.append({"chapter": idx, "title": title, **res, "file": os.path.join(os.path.basename(out_dir), fname)})

        playlist_lines.append(f"Ep {idx}: {title} — {fname}")

    desc_path = os.path.join(out_dir, "playlist.txt")
    with open(desc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(playlist_lines))

    return {"ok": True, "project_dir": os.path.basename(out_dir), "episodes": results, "playlist_text": "\n".join(playlist_lines)}
