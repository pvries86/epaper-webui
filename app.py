#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import os, uuid, socket, re
from datetime import datetime
from io import BytesIO
try:
    from waveshare_epd import epd7in3e
except Exception as exc:
    epd7in3e = None
    EPD_IMPORT_ERROR = exc
else:
    EPD_IMPORT_ERROR = None
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

load_dotenv()


def _env_or_default(name, default=""):
    value = os.getenv(name)
    return value.strip() if value else default


def _int_env(name, fallback):
    try:
        return int(os.getenv(name, fallback))
    except (TypeError, ValueError):
        return fallback

HF_API_KEY  = os.getenv("HF_API_KEY")

SUPPORTED_MODELS = [
    {"id": "black-forest-labs/FLUX.1-schnell", "label": "FLUX.1 Schnell"},
    {"id": "stabilityai/stable-diffusion-xl-base-1.0", "label": "Stable Diffusion XL Base"},
    {"id": "stabilityai/stable-diffusion-3-medium-diffusers", "label": "Stable Diffusion 3 Medium"},
]
DEFAULT_MODEL_ID = SUPPORTED_MODELS[0]["id"]
CHIP_LABELS = {
    "poster",
    "typography",
    "landscape",
    "architecture",
    "product",
    "infographic",
    "portrait",
    "doodle",
}




def _parse_model_choices(default_model):
    raw = os.getenv("HF_MODEL_CHOICES")
    choices = []
    if raw:
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "|" in chunk:
                label, model = chunk.split("|", 1)
            else:
                label, model = chunk, chunk
            model = model.strip()
            if not model:
                continue
            label = label.strip() or model
            choices.append({"id": model, "label": label})
    if not choices:
        choices.append({"id": default_model, "label": default_model})
    # ensure default model is always first
    seen = set()
    ordered = []
    for entry in choices:
        mid = entry["id"]
        if mid in seen:
            continue
        seen.add(mid)
        ordered.append(entry)
    if default_model not in seen:
        ordered.insert(0, {"id": default_model, "label": default_model})
    return ordered

HF_PROVIDER = _env_or_default("HF_PROVIDER", "hf-inference")
HF_MODEL    = _env_or_default("HF_MODEL", DEFAULT_MODEL_ID)
MODEL_CHOICES = _parse_model_choices(HF_MODEL)
choice_map = {entry["id"]: entry for entry in MODEL_CHOICES}
for entry in SUPPORTED_MODELS:
    existing = choice_map.get(entry["id"])
    if existing:
        if existing.get("label") in (None, "", existing["id"]):
            existing["label"] = entry["label"]
        continue
    clone = {"id": entry["id"], "label": entry["label"]}
    MODEL_CHOICES.append(clone)
    choice_map[clone["id"]] = clone
MODEL_ID_LOOKUP = choice_map

client = InferenceClient(
    provider=HF_PROVIDER,
    api_key=HF_API_KEY,
)

UPLOAD_FOLDER = "uploads"
RESOLUTION    = (800, 480)          # for HF generation only
GEN_WIDTH     = _int_env("HF_WIDTH", RESOLUTION[0])
GEN_HEIGHT    = _int_env("HF_HEIGHT", RESOLUTION[1])

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def get_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except Exception:
        return "Unavailable"
    finally:
        sock.close()

def _measure_text(draw, txt, font):
    try:
        l, t, r, b = draw.textbbox((0, 0), txt, font=font)
        return r - l, b - t
    except AttributeError:
        return draw.textsize(txt, font=font)

def draw_ip_overlay(img, txt, pos, size, color):
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
        )
    except OSError:
        fnt = ImageFont.load_default()

    x, y = pos if isinstance(pos, tuple) else (10, 10)
    x = max(0, min(x, img.width))
    y = max(0, min(y, img.height))
    d.text((x, y), txt, font=fnt, fill=color)
    return img

def send_to_display(pil, *, overlay=False, pos=(10, 10),
                    fsize=18, fcolor=(0, 0, 0), text=""):
    pil = pil.resize((epd.width, epd.height)).convert("RGB")
    if overlay and text:
        pil = draw_ip_overlay(pil, text, pos, fsize, fcolor)
    epd.init()
    epd.Clear()
    epd.display(epd.getbuffer(pil))
    epd.sleep()

def timestamp_prefix() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def prompt_slug(text: str, fallback: str = "image") -> str:
    if not text:
        return fallback
    stripped = re.sub(r"\s+", " ", text).strip()
    stripped = stripped.replace("{", "").replace("}", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stripped.lower()).strip("-")
    if not slug:
        slug = fallback
    return slug[:40]

def cleaned_prompt_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

def subject_from_prompt(prompt: str) -> str:
    cleaned = cleaned_prompt_text(prompt).replace("—", "-")
    if not cleaned:
        return "subject"
    segments = [seg.strip() for seg in re.split(r"\s*-\s*", cleaned) if seg.strip()]
    for seg in segments:
        if not seg:
            continue
        normalized = re.sub(r"[^a-zA-Z0-9]+", " ", seg).strip().lower()
        if not normalized:
            continue
        if normalized in CHIP_LABELS:
            continue
        return seg
    return cleaned

def ensure_unique_filename(base_name: str) -> str:
    path = os.path.join(UPLOAD_FOLDER, base_name)
    if not os.path.exists(path):
        return base_name
    name, ext = os.path.splitext(base_name)
    counter = 1
    candidate = f"{name}_{counter}{ext}"
    while os.path.exists(os.path.join(UPLOAD_FOLDER, candidate)):
        counter += 1
        candidate = f"{name}_{counter}{ext}"
    return candidate

def resolve_upload_path(filename: str) -> str:
    if not filename:
        raise ValueError("Missing filename")
    root = os.path.abspath(UPLOAD_FOLDER)
    target = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
    if not target.startswith(root + os.sep) and target != root:
        raise ValueError("Invalid path")
    return target

# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("image")
        if not file:
            return "No file uploaded", 400

        # --------- overlay options (backend only if requested) ---------
        overlay    = request.form.get("show_overlay") == "on"
        ol_x       = int(request.form.get("overlay_x", 10))
        ol_y       = int(request.form.get("overlay_y", 10))
        ol_size    = int(request.form.get("overlay_font_size", 18))
        ol_color_h = request.form.get("overlay_font_color", "#000000")
        ol_text    = request.form.get("overlay_text", "")
        r, g, b    = (int(ol_color_h[i : i + 2], 16) for i in (1, 3, 5))

        # canvas snapshot vs. user upload (keep both on disk)
        if file.filename == "processed.png":
            src_img = Image.open(BytesIO(file.read())).convert("RGB")
        else:
            safe_name = secure_filename(file.filename) or "upload.png"
            save_name = ensure_unique_filename(f"{timestamp_prefix()}_{safe_name}")
            path = os.path.join(UPLOAD_FOLDER, save_name)
            file.save(path)
            src_img = Image.open(path).convert("RGB")

        # nothing else to process - client already handled it
        send_to_display(
            src_img,
            overlay=overlay,
            pos=(ol_x, ol_y),
            fsize=ol_size,
            fcolor=(r, g, b),
            text=ol_text,
        )
        return "Image sent to e-Paper display successfully! <a href='/'>Back</a>"

    return render_template("index.html")

@app.route("/upload_file", methods=["POST"])
def upload_file():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400
    safe_name = secure_filename(file.filename) or "upload.png"
    save_name = ensure_unique_filename(f"{timestamp_prefix()}_{safe_name}")
    path = os.path.join(UPLOAD_FOLDER, save_name)
    try:
        file.save(path)
    except OSError as exc:
        return jsonify({"error": f"Unable to save file: {exc}"}), 500
    return jsonify({"filename": save_name})

@app.route("/generate", methods=["POST"])
def generate():
    prompt_input = request.form.get("prompt", "A futuristic city")
    preset_name = request.form.get("preset_name", "custom")
    subject_name = request.form.get("subject_name", "")
    subject_source = subject_name or subject_from_prompt(prompt_input)
    slug_subject = prompt_slug(subject_source, fallback="")
    slug_preset = prompt_slug(preset_name, fallback="")
    prompt = prompt_input
    selected_model = request.form.get("model") or HF_MODEL
    model_id = selected_model if selected_model in MODEL_ID_LOOKUP else HF_MODEL
    try:
        generated = client.text_to_image(
            prompt,
            model=model_id,
            width=GEN_WIDTH,
            height=GEN_HEIGHT,
        )
        if isinstance(generated, bytes):
            img = Image.open(BytesIO(generated))
        else:
            img = generated
        name_parts = [timestamp_prefix()]
        if slug_subject:
            name_parts.append(slug_subject)
        if slug_preset:
            name_parts.append(slug_preset)
        base_name = "-".join(name_parts) + ".png"
        fname = ensure_unique_filename(base_name)
        img.save(os.path.join(UPLOAD_FOLDER, fname))
        return jsonify({"filename": fname})
    except Exception as e:
        app.logger.exception("Image generation failed")
        return jsonify({"error": str(e)}), 500

@app.route("/uploads/<filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/list_uploads")
def list_uploads():
    return jsonify(sorted(os.listdir(UPLOAD_FOLDER), reverse=True))

@app.route("/delete_upload", methods=["POST"])
def delete_upload():
    payload = request.get_json(silent=True) or {}
    filename = (payload.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "Filename required"}), 400
    try:
        path = resolve_upload_path(filename)
    except ValueError:
        return jsonify({"error": "Invalid filename"}), 400
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    try:
        os.remove(path)
    except OSError as exc:
        return jsonify({"error": f"Unable to delete file: {exc}"}), 500
    return jsonify({"success": True})

@app.route("/hf_models")
def hf_models():
    return jsonify({"models": MODEL_CHOICES, "default": HF_MODEL})

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    epd = epd7in3e.EPD()
    epd.init()

    startup = Image.new("RGB", (epd.width, epd.height), (255, 255, 255))
    draw_ip_overlay(startup, f"IP: {get_ip()}", "top-left", 24, (0, 0, 0))
    epd.display(epd.getbuffer(startup))

    app.run(host="0.0.0.0", port=5000, debug=False)
