import os
import uuid
import json
from flask import Flask, render_template, request, send_from_directory, jsonify
from dotenv import load_dotenv
from video_builder import build_video_from_story, build_batch_videos

load_dotenv()
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

# Single video route
@app.route("/create", methods=["POST"])
def create():
    data = request.form
    story = data.get("story", "").strip()
    deity = data.get("deity", "Generic")
    lang = data.get("lang", os.getenv("VOICE_LANG", "ta"))
    duration = int(data.get("duration", 20))

    if not story:
        return jsonify({"ok": False, "error": "Please paste a story."}), 400

    out_name = f"{deity.lower()}_{uuid.uuid4().hex[:8]}.mp4"
    out_path = os.path.join("outputs", out_name)

    result = build_video_from_story(
        story_text=story,
        deity=deity,
        voice_lang=lang,
        target_duration=duration,
        out_path=out_path,
    )

    if not result["ok"]:
        return jsonify(result), 500

    return jsonify({"ok": True, "file": out_name})

# Chapter-wise batch creation
@app.route("/create_batch", methods=["POST"])
def create_batch():
    payload = request.get_json(force=True)
    project = payload.get("project")
    if not project or not project.get("chapters"):
        return jsonify({"ok": False, "error": "Missing project.chapters"}), 400

    title = project.get("title", f"Project-{uuid.uuid4().hex[:6]}")
    deity = project.get("deity", "Generic")
    lang = project.get("lang", os.getenv("VOICE_LANG", "ta"))

    # Output directory per project
    proj_slug = "".join([c.lower() if c.isalnum() else "-" for c in title]).strip('-')
    out_dir = os.path.join("outputs", proj_slug)
    os.makedirs(out_dir, exist_ok=True)

    result = build_batch_videos(
        chapters=project["chapters"],
        deity=deity,
        voice_lang=lang,
        out_dir=out_dir
    )

    return jsonify(result)

@app.route('/download/<path:filename>')
def download_file(filename):
    # supports both single files and chapter files under outputs/*
    base = 'outputs'
    fpath = os.path.join(base, filename)
    if os.path.isdir(fpath):
        return jsonify({"ok": False, "error": "Cannot download a directory"}), 400
    directory = os.path.dirname(fpath) if os.path.dirname(fpath) else base
    file = os.path.basename(fpath)
    return send_from_directory(directory, file, as_attachment=True)

if __name__ == "__main__":
    os.makedirs("outputs", exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
