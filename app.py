import os
import time
from datetime import datetime
from pathlib import Path
from flask import (
    Flask, render_template, request, jsonify,
    send_from_directory, abort
)

# Your video builder functions
from video_builder import (
    build_video_from_story,
    build_batch_videos
)

# -----------------------------------------------------------------------------
# Flask setup
# -----------------------------------------------------------------------------
app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")

# Output folder
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Defaults from env
DEFAULT_IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "local")
DEFAULT_VOICE_LANG = os.getenv("VOICE_LANG", "ta")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _now_tag() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

def _get_data() -> dict:
    """
    Accept both JSON and form-encoded payloads without error.
    """
    data = request.get_json(silent=True)
    if not data:
        data = request.form.to_dict(flat=True)
    if not isinstance(data, dict):
        data = {}
    # strip strings
    clean = {}
    for k, v in data.items():
        if isinstance(v, str):
            clean[k] = v.strip()
        else:
            clean[k] = v
    return clean

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    """
    Render the main page.
    """
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create_single():
    """
    Create a single short video from form/JSON fields:
      - story: str (required)
      - deity: str (optional)
      - duration: int (optional)
      - voice_lang: str (optional; default from env)
    Returns JSON {"ok":True, "file": "/download/<filename>"} or {"ok":False, "error": "..."}
    """
    data = _get_data()

    story = data.get("story", "")
    if not story:
        return jsonify({"ok": False, "error": "Missing story"}), 400

    deity = data.get("deity", "Generic") or "Generic"
    voice_lang = data.get("voice_lang", DEFAULT_VOICE_LANG) or DEFAULT_VOICE_LANG

    try:
        duration = int(data.get("duration", 20))
    except Exception:
        duration = 20

    # unique filename
    fname = f"out_{_now_tag()}.mp4"
    out_path = str(OUTPUT_DIR / fname)

    res = build_video_from_story(
        story_text=story,
        deity=deity,
        voice_lang=voice_lang,
        target_duration=duration,
        out_path=out_path,
    )

    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "Unknown error")}), 500

    return jsonify({"ok": True, "file": f"/download/{fname}", "path": fname})


@app.route("/create-batch", methods=["POST"])
def create_batch():
    """
    Build multiple chapter videos.
    JSON expected:
      {
        "deity": "Murugan",
        "voice_lang": "ta",
        "chapters": [
          {"title":"Ch 1", "story":"...", "duration": 24},
          ...
        ]
      }
    Returns: project info + list of episodes
    """
    data = _get_data()
    chapters = data.get("chapters")
    if not chapters or not isinstance(chapters, list):
        return jsonify({"ok": False, "error": "Missing or invalid chapters[]"}), 400

    deity = data.get("deity", "Generic") or "Generic"
    voice_lang = data.get("voice_lang", DEFAULT_VOICE_LANG) or DEFAULT_VOICE_LANG

    project_dir = OUTPUT_DIR / f"project_{_now_tag()}"
    project_dir.mkdir(parents=True, exist_ok=True)

    res = build_batch_videos(
        chapters=chapters,
        deity=deity,
        voice_lang=voice_lang,
        out_dir=str(project_dir),
    )

    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "Unknown error")}), 500

    # Add helpful download URLs
    for ep in res.get("episodes", []):
        if ep.get("ok") and ep.get("file"):
            ep["download"] = f"/download/{project_dir.name}/{ep['file']}"

    res["project_downloads"] = {
        "folder": f"/download/{project_dir.name}",
        "playlist": f"/download/{project_dir.name}/playlist.txt",
    }
    return jsonify(res)


@app.route("/download/<path:filename>", methods=["GET"])
def download_file(filename: str):
    """
    Serve files from outputs/ safely.
    Supports both single files, and /download/<project>/<file>.
    """
    # Normalize & prevent path traversal
    file_path = OUTPUT_DIR / filename
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except Exception:
        abort(404)

    if file_path.is_dir():
        # If a directory is requested, show a simple listing (optional)
        try:
            listing = sorted(p.name for p in file_path.iterdir())
        except Exception:
            listing = []
        return jsonify({"ok": True, "dir": filename, "files": listing})

    if not file_path.exists():
        abort(404)

    return send_from_directory(
        directory=str(file_path.parent),
        path=file_path.name,
        as_attachment=True
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "healthy"})


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Render supplies PORT env var
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
