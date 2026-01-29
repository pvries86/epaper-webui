# ePaper Web UI

A Flask-based web interface to upload or generate images for your Waveshare ePaper display.

Supports:
- Uploading, timestamping, and previewing images (manual uploads now auto-save to `uploads/` and appear in the dropdown)
- Real-time contrast / brightness / saturation / sharpness adjustment
- Text overlay (with positioning and styling)
- Image resizing modes: pad or crop
- Image generation from prompt using any configured Hugging Face model
- One-click deletion of uploaded/generate images directly from the UI

---

## 🚀 Features

- Web-based upload interface with live canvas preview
- Overlay text (custom position, size, and color)
- Timestamped filenames for deterministic ordering (e.g. `20260126-142211-cityscape-poster.png`)
- Dropdown model selector populated from `/hf_models`
- Delete button under “Images” card to remove the currently selected file
- Automatic display of device IP on boot
- Integration with Hugging Face for prompt-to-image generation

---

## 📦 Prerequisites

- Python 3.9+
- Flask
- Pillow
- python-dotenv
- huggingface_hub
- waveshare_epd driver (included locally)

Install dependencies:
```bash
pip install -r requirements.txt
```

### Requirements File Example:
```
flask
pillow
python-dotenv
huggingface_hub
```

---

## 🖼️ Usage

### Run the server
```bash
python3 app.py
```

Then go to `http://<your-ip>:5000` in your browser.

- **Uploads dropdown** - entries show `YYYY-MM-DD HH:MM - original_name`. Generated files are named `timestamp-subject-chip.png`, so you immediately know which concept/preset produced them, and the latest entry auto-selects after each run.
- **Delete selected image** - removes the highlighted upload (with a confirmation + progress state).
- **Manual uploads** - dragging/selecting a file immediately saves it (timestamped) to `uploads/` and refreshes the dropdown list, so you can send it or adjust it right away.

---

## 🤖 Generate Images from Prompt (Hugging Face)

1. Create a `.env` file in your project folder:
```
HF_API_KEY=your_huggingface_api_key_here
```

2. Or copy the example:
```bash
cp .env.example .env
```

The default model is: `stabilityai/stable-diffusion-xl-base-1.0`

> **Note:** `black-forest-labs/FLUX.1-dev` is no longer available. Verified working options:
> - `stabilityai/stable-diffusion-xl-base-1.0`
> - `stabilityai/stable-diffusion-3-medium-diffusers`
> - `black-forest-labs/FLUX.1-schnell`

Optional overrides (all read from `.env`):

- `HF_PROVIDER` - set to `replicate`, `fal-ai`, etc. when routing through another provider (defaults to `hf-inference`).
- `HF_MODEL` - fallback model id if you want to try a different checkpoint.
- `HF_WIDTH` / `HF_HEIGHT` - generation resolution in pixels; defaults to `800x480`.
- `HF_MODEL_CHOICES` - optional semicolon-separated list of `Label|model_id` entries. When present, the web UI shows a dropdown so you can pick the model per-generation (defaults to the supported models listed above).
- `/hf_models` response is also used to populate the UI selector, so you can hot-swap between curated checkpoints.

---

## 🔧 Optional: Systemd Setup for Auto-start

Create a file at `/etc/systemd/system/epaper-webui.service`:
```
[Unit]
Description=ePaper Web UI Flask App
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/epaper-webui/app.py
WorkingDirectory=/home/pi/epaper-webui
Restart=always
User=pi
Environment=HF_API_KEY=your_key_here

[Install]
WantedBy=multi-user.target
```

Then enable and start it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable epaper-webui
sudo systemctl start epaper-webui
```

On Raspberry Pi OS / Debian, also enable the wait-online helper so the service only launches after DHCP has finished:
```bash
sudo systemctl enable systemd-networkd-wait-online.service
```
If you use another network manager (e.g., dhcpcd, NetworkManager), enable its equivalent wait-online unit instead.

---

## 📁 Folder Structure

```
epaper-webui/
├── app.py
├── templates/
│   └── index.html
├── static/
├── uploads/
├── processed/
├── waveshare_epd/
├── .env.example
├── README.md
└── requirements.txt
```

---

## 🔐 Security

- Your API keys should go in a `.env` file (not committed)
- `.env` is excluded via `.gitignore`

---

## ✅ TODO / Roadmap

- [ ] Live filter previews with sliders
- [ ] Overlay font choices
- [ ] Batch image processing
- [ ] Schedule or rotate image sets

---

## 📜 License

MIT. See LICENSE file.

---

Made with ❤️ and pixels.
