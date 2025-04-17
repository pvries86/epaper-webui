# ePaper Web UI

A Flask-based web interface to upload or generate images for your Waveshare ePaper display.

Supports:
- Uploading and previewing images
- Real-time contrast, sharpness, and green bias adjustment
- Text overlay (with positioning and styling)
- Image resizing modes: pad or crop
- Image generation from prompt using Hugging Face FLUX.1-dev

---

## 🚀 Features

- Web-based upload interface with live canvas preview
- Overlay text (custom position, size, and color)
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

The model used is: `black-forest-labs/FLUX.1-dev`

---

## 🔧 Optional: Systemd Setup for Auto-start

Create a file at `/etc/systemd/system/epaper-webui.service`:
```
[Unit]
Description=ePaper Web UI Flask App
After=network.target

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
