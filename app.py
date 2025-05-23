#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import os, uuid, socket
from io import BytesIO
from waveshare_epd import epd7in3e
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

load_dotenv()

client = InferenceClient(
    provider="hf-inference",
    api_key=os.getenv("HF_API_KEY"),
)

UPLOAD_FOLDER = "uploads"
RESOLUTION    = (800, 480)          # for HF generation only

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

    tw, th = _measure_text(d, txt, fnt)
    positions = {
        "top-left": (10, 10),
        "top-right": (img.width - tw - 10, 10),
        "bottom-left": (10, img.height - th - 10),
        "bottom-right": (img.width - tw - 10, img.height - th - 10),
    }
    d.text(positions.get(pos, (10, 10)), txt, font=fnt, fill=color)
    return img

def send_to_display(pil, *, overlay=False, pos="top-left",
                    fsize=18, fcolor=(0, 0, 0), text=""):
    pil = pil.resize((epd.width, epd.height)).convert("RGB")
    if overlay and text:
        pil = draw_ip_overlay(pil, text, pos, fsize, fcolor)
    epd.init()
    epd.Clear()
    epd.display(epd.getbuffer(pil))
    epd.sleep()

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
        ol_pos     = request.form.get("overlay_position", "top-left")
        ol_size    = int(request.form.get("overlay_font_size", 18))
        ol_color_h = request.form.get("overlay_font_color", "#000000")
        ol_text    = request.form.get("overlay_text", "")
        r, g, b    = (int(ol_color_h[i : i + 2], 16) for i in (1, 3, 5))

        # canvas snapshot vs. user upload (keep both on disk)
        if file.filename == "processed.png":
            src_img = Image.open(BytesIO(file.read())).convert("RGB")
            save_name = f"upload_{uuid.uuid4().hex}.png"
            src_img.save(os.path.join(UPLOAD_FOLDER, save_name))
        else:
            save_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            path = os.path.join(UPLOAD_FOLDER, save_name)
            file.save(path)
            src_img = Image.open(path).convert("RGB")

        # nothing else to processóclient already handled it
        send_to_display(
            src_img,
            overlay=overlay,
            pos=ol_pos,
            fsize=ol_size,
            fcolor=(r, g, b),
            text=ol_text,
        )
        return "Image sent to e-Paper display successfully! <a href='/'>Back</a>"

    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    prompt = request.form.get("prompt", "A futuristic city")
    try:
        img   = client.text_to_image(
            prompt,
            model="black-forest-labs/FLUX.1-dev",
            width=RESOLUTION[0],
            height=RESOLUTION[1],
        )
        fname = f"flux_{uuid.uuid4().hex}.png"
        img.save(os.path.join(UPLOAD_FOLDER, fname))
        return jsonify({"filename": fname})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/uploads/<filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/list_uploads")
def list_uploads():
    return jsonify(sorted(os.listdir(UPLOAD_FOLDER)))

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
