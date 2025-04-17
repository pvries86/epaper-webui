from flask import Flask, request, render_template, send_from_directory, jsonify
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import os
import uuid
import socket
import base64
from io import BytesIO
from waveshare_epd import epd7in3e
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()

client = InferenceClient(
    provider="hf-inference",
    api_key=os.getenv("HF_API_KEY")
)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
RESOLUTION = (800, 480)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = 'Unavailable'
    finally:
        s.close()
    return IP

def draw_ip_overlay(img, text, position, font_size, font_color):
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    text_width, text_height = draw.textsize(text, font=font)

    if position == 'top-left':
        pos = (10, 10)
    elif position == 'top-right':
        pos = (img.width - text_width - 10, 10)
    elif position == 'bottom-left':
        pos = (10, img.height - text_height - 10)
    elif position == 'bottom-right':
        pos = (img.width - text_width - 10, img.height - text_height - 10)
    else:
        pos = (10, 10)

    # Optional shadow
    draw.text((pos[0] + 1, pos[1] + 1), text, font=font, fill=(0, 0, 0))
    draw.text(pos, text, font=font, fill=font_color)
    return img

def resize_and_fill(img, target_size=(800, 480), background_color=(255, 255, 255), pad_threshold=0.1, use_padding=True):
    img_ratio = img.width / img.height
    target_ratio = target_size[0] / target_size[1]

    if abs(img_ratio - target_ratio) < pad_threshold or not use_padding:
        img = img.copy()
        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            offset = (img.width - new_width) // 2
            box = (offset, 0, offset + new_width, img.height)
        else:
            new_height = int(img.width / target_ratio)
            offset = (img.height - new_height) // 2
            box = (0, offset, img.width, offset + new_height)
        img = img.crop(box)
        img = img.resize(target_size, Image.LANCZOS)
    else:
        if img_ratio > target_ratio:
            new_width = target_size[0]
            new_height = round(new_width / img_ratio)
        else:
            new_height = target_size[1]
            new_width = round(new_height * img_ratio)

        img = img.resize((new_width, new_height), Image.LANCZOS)
        background = Image.new("RGB", target_size, background_color)
        offset = ((target_size[0] - new_width) // 2, (target_size[1] - new_height) // 2)
        background.paste(img, offset)
        img = background

    return img

def apply_green_bias(img, green_bias_factor=1.3, green_min=100):
    pixels = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = pixels[x, y]
            if g > r * green_bias_factor and g > b * green_bias_factor and g > green_min:
                pixels[x, y] = (0, 255, 0)
    return img

def process_image(path, contrast=1.8, sharpness=1.0, green_bias_factor=1.3, green_min=100, use_padding=True):
    img = resize_and_fill(Image.open(path).convert("RGB"), use_padding=use_padding)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    img = apply_green_bias(img, green_bias_factor, green_min)
    processed_filename = f"processed_{uuid.uuid4().hex}.bmp"
    processed_path = os.path.join(PROCESSED_FOLDER, processed_filename)
    img.save(processed_path)
    return processed_path

def send_to_display(img_path, show_overlay=False, overlay_position='top-left', overlay_font_size=18, overlay_font_color=(0, 0, 0), overlay_text=""):
    img = Image.open(img_path).resize((epd.width, epd.height)).convert("RGB")
    if show_overlay and overlay_text:
        img = draw_ip_overlay(img, overlay_text, overlay_position, overlay_font_size, overlay_font_color)
    epd.display(epd.getbuffer(img))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['image']
        contrast = float(request.form.get('contrast', 1.8))
        sharpness = float(request.form.get('sharpness', 1.0))
        green_bias = float(request.form.get('green_bias', 1.3))
        use_padding = request.form.get('resizemode') == 'pad'

        show_overlay = request.form.get('show_overlay') == 'on'
        overlay_position = request.form.get('overlay_position', 'top-left')
        overlay_font_size = int(request.form.get('overlay_font_size', 18))
        overlay_font_color = request.form.get('overlay_font_color', '#000000')
        overlay_text = request.form.get('overlay_text', '')

        r = int(overlay_font_color[1:3], 16)
        g = int(overlay_font_color[3:5], 16)
        b = int(overlay_font_color[5:7], 16)

        if file:
            filename = f"{uuid.uuid4().hex}_{file.filename}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            processed_path = process_image(path, contrast, sharpness, green_bias, use_padding=use_padding)
            send_to_display(processed_path, show_overlay, overlay_position, overlay_font_size, (r, g, b), overlay_text)
            return f"Image sent to e-Paper display successfully! <a href='/'>Back</a>"

    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    prompt = request.form.get("prompt", "A futuristic city")
    try:
        image = client.text_to_image(
            prompt,
            model="black-forest-labs/FLUX.1-dev",
            height=480,
            width=800
        )
        filename = f"flux_{uuid.uuid4().hex}.png"
        path = os.path.join(UPLOAD_FOLDER, filename)
        image.save(path)
        return jsonify({"filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/processed/<filename>')
def processed_file(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)

if __name__ == '__main__':
    epd = epd7in3e.EPD()
    epd.init()
    startup_img = Image.new("RGB", (epd.width, epd.height), (255, 255, 255))
    ip_text = get_ip()
    startup_img = draw_ip_overlay(startup_img, f"IP: {ip_text}", 'top-left', 24, (0, 0, 0))
    epd.display(epd.getbuffer(startup_img))
    app.run(host='0.0.0.0', port=5000, debug=False)

