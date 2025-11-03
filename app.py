import os
from flask import Flask, render_template, request, send_from_directory, jsonify
from dotenv import load_dotenv

from video_builder import build_video_from_story, build_batch_videos

load_dotenv()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "outputs"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/create")
def create_single():
    """Create one short video from the form."""
    story = request.form.get("story", "").strip()
    deity = request.form.get("deity", "Murugan").strip() or "Murugan"
    lang = request.form.get("lang", "ta").strip() or "ta"
    duration = int(request.form.get("duration", "20") or 20)

    out_name = "out.mp4"
    out_path = os.path.join(app.config["UPLOAD_FOLDER"], out_name)

    res = build_video_from_story(
        story_text=story,
        deity=deity,
        voice_lang=lang,
        target_duration=duration,
        out_path=out_path,
    )
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "Unknown error")}), 400

    return jsonify({"ok": True, "file": out_name})


@app.post("/batch")
def create_batch():
    """Create many chapter videos from JSON."""
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    proj = payload.get("project", {})
    title = proj.get("title", "Project")
    lang = proj.get("lang", "ta")
    deity = proj.get("deity", "Murugan")
    chapters = proj.get("chapters", [])

    out_dir = os.path.join(app.config["UPLOAD_FOLDER"], title.replace(" ", "_"))
    os.makedirs(out_dir, exist_ok=True)

    res = build_batch_videos(chapters, deity=deity, voice_lang=lang, out_dir=out_dir)
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "Batch failed")}), 400

    return jsonify(
        {
            "ok": True,
            "project": res["project_dir"],
            "episodes": res["episodes"],
            "playlist_text": res["playlist_text"],
        }
    )


@app.get("/download/<path:filename>")
def download(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
