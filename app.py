import os
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from video_builder import build_video_from_story, build_batch_videos
from pathlib import Path
from datetime import datetime

app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Default settings
DEFAULT_VOICE_LANG = os.getenv("VOICE_LANG", "ta")

def _now_tag():
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

def _get_data():
    """Handles both form and JSON input safely"""
    data = request.get_json(silent=True)
    if not data:
        data = request.form.to_dict(flat=True)
    return data or {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create_video():
    data = _get_data()
    story = data.get("story", "").strip()
    deity = data.get("deity", "Generic").strip()
    voice_lang = data.get("voice_lang", DEFAULT_VOICE_LANG).strip()
    duration = int(data.get("duration", 20))

    if not story:
        return jsonify({"ok": False, "error": "Missing story"}), 400

    filename = f"out_{_now_tag()}.mp4"
    out_path = str(OUTPUT_DIR / filename)

    result = build_video_from_story(
        story_text=story,
        deity=deity,
        voice_lang=voice_lang,
        target_duration=duration,
        out_path=out_path,
    )

    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Unknown error")}), 500

    return jsonify({"ok": True, "file": f"/download/{filename}"})

@app.route("/download/<path:filename>")
def download_file(filename):
    file_path = OUTPUT_DIR / filename
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except Exception:
        abort(404)
    if not file_path.exists():
        abort(404)
    return send_from_directory(directory=str(file_path.parent), path=file_path.name, as_attachment=True)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
