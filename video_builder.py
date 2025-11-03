import os, io, textwrap, math, random, tempfile, base64, requests
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
)
from gtts import gTTS
from imageio_ffmpeg import get_ffmpeg_exe

# Make sure MoviePy finds ffmpeg on Render/hosted envs
os.environ["IMAGEIO_FFMPEG_EXE"] = get_ffmpeg_exe()

IMG_W, IMG_H = 1080, 1920
FPS = 24

# ---------- Scene splitter ----------
def split_story_into_scenes(story: str, max_chars=140) -> List[str]:
    story = " ".join(story.split())
    sentences = [s.strip() for s in story.replace("\n", " ").split(".") if s.strip()]
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
def generate_image(prompt: str, provider: str | None = None):
    provider = provider or os.getenv("IMAGE_PROVIDER", "openai")
    # Local placeholder (no API needed)
    if provider == "local":
        img = Image.new("RGB", (IMG_W, IMG_H), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        draw.text((40, 40), prompt[:60] + "…", fill=(230, 230, 230))
        return img

    # URL provider (optional)
    if provider == "url":
        resp = requests.get(prompt, timeout=30)
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        return img.resize((IMG_W, IMG_H))

    # OpenAI images (optional)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # fallback if no key: act like local
        img = Image.new("RGB", (IMG_W, IMG_H), (25, 25, 25))
        ImageDraw.Draw(img).text((40, 40), prompt[:60] + "…", fill=(200, 200, 200))
        return img

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": "gpt-image-1", "prompt": prompt, "size": "1024x1792"}
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers=headers, json=data, timeout=120
    )
    r.raise_for_status()
    b64 = r.json()["data"][0]["b64_json"]
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    return img.resize((IMG_W, IMG_H))

# ---------- Text-to-speech ----------
def tts_to_mp3_path(text: str, lang: str) -> str:
    path = tempfile.mktemp(suffix=".mp3")
    gTTS(text=text, lang=lang).save(path)
    return path

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
        draw.multiline_text((cx+dx, cy+dy), caption, anchor="mm", align="center",
                            fill=(0,0,0), font=font, spacing=6)
    draw.multiline_text((cx, cy), caption, anchor="mm", align="center",
                        fill=(255,255,255), font=font, spacing=6)
    return img

# ---------- BGM ----------
def pick_bgm_path():
    bgm_dir = os.path.join("assets", "bgm")
    if not os.path.isdir(bgm_dir):
        return None
    files = [f for f in os.listdir(bgm_dir)
             if f.lower().endswith((".mp3", ".wav", ".m4a"))]
    if not files:
        return None
    return os.path.join(bgm_dir, random.choice(files))

# ---------- Single video ----------
def build_video_from_story(
    story_text: str,
    deity: str = "Generic",
    voice_lang: str = "ta",
    target_duration: int = 20,
    out_path: str = "outputs/out.mp4",
) -> Dict:
    try:
        scenes = split_story_into_scenes(story_text)
        per_scene = max(3, min(6, math.floor(target_duration / max(1, len(scenes)))))

        # images + captions
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

        # voiceover
        voice_mp3 = tts_to_mp3_path(" ".join(scenes), lang=voice_lang)
        voice = AudioFileClip(voice_mp3)
        if voice.duration > video.duration:
            voice = voice.subclip(0, video.duration)

        # background music
        bgm_path = pick_bgm_path()
        if bgm_path:
            music = AudioFileClip(bgm_path).volumex(0.35)
            if music.duration < video.duration:
                loops = int(math.ceil(video.duration / music.duration))
                music = concatenate_videoclips([music] * loops).subclip(0, video.duration).audio_fadeout(0.5)
            else:
                music = music.subclip(0, video.duration).audio_fadeout(0.5)
            audio = CompositeAudioClip([music, voice.volumex(1.0)])
        else:
            audio = voice

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
    try:
        for idx, ch in enumerate(chapters, start=1):
            title = ch.get("title", f"Chapter {idx}")
            story = ch.get("story", "").strip()
            duration = int(ch.get("duration", 24))
            fname = f"chapter-{idx:02d}.mp4"
            out_path = os.path.join(out_dir, fname)

            res = build_video_from_story(
                story, deity=deity, voice_lang=voice_lang,
                target_duration=duration, out_path=out_path
            )
            results.append({"chapter": idx, "title": title, **res, "file": fname})
            playlist_lines.append(f"Ep {idx}: {title} – {fname}")

        desc_path = os.path.join(out_dir, "playlist.txt")
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(playlist_lines))

        return {"ok": True, "project_dir": os.path.basename(out_dir),
                "episodes": results, "playlist_text": "\n".join(playlist_lines)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
