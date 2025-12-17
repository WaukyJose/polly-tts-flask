from flask import Flask, request, send_file, jsonify, render_template
import boto3
import uuid
import os
import hashlib
import time

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


# Directory to store temp audio files (absolute path, fixed)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


def cleanup_old_audio(folder, max_age_seconds=186400):  # 24 hours
    now = time.time()
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if os.path.isfile(path):
            if now - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)


# Initialize Polly client
polly = boto3.client("polly", region_name="us-east-1")


# ---- Health check (important for debugging & deployment)
@app.route("/ping", methods=["GET"])
def ping():
    return "OK", 200


@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()

    if not data or "text" not in data:
        return jsonify({"error": "Text is required"}), 400

    cleanup_old_audio(AUDIO_DIR)
    text = data["text"]
    voice = data.get("voice", "Amy")
    engine = data.get("engine", "neural")
    is_ssml = data.get("ssml", False)

    cache_key = f"{text}|{voice}|{engine}|{is_ssml}"
    hash_id = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    filename = os.path.join(AUDIO_DIR, f"{hash_id}.mp3")

    # Return cached audio if it already exists
    if os.path.exists(filename):
        return send_file(filename, mimetype="audio/mpeg", as_attachment=False)

    try:
        response = polly.synthesize_speech(
            Text=text,
            TextType="ssml" if is_ssml else "text",
            VoiceId=voice,
            Engine=engine,
            OutputFormat="mp3",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    with open(filename, "wb") as f:
        f.write(response["AudioStream"].read())

    return send_file(filename, mimetype="audio/mpeg", as_attachment=False)


if __name__ == "__main__":
    app.run(debug=True)
