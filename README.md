# ePaper Web UI

A lightweight Flask-based web interface for uploading, previewing, and displaying images on Waveshare Spectra 6 e-Paper displays (800x480), with support for contrast/sharpness adjustments, green color biasing, and text overlays.

## Features

- Upload and preview images in real-time
- Adjustable contrast, sharpness, and green bias
- Smart resizing with pad or crop mode
- Optional overlay text with position, size, and color control
- IP address auto-displayed on startup
- Responsive web UI with live canvas preview
- Runs as a `systemd` service for automatic startup on boot

## Hardware Requirements

- Raspberry Pi (tested on Pi 3 and 4)
- Waveshare 7.3" e-Paper HAT (Spectra 6)
- SPI enabled on Raspberry Pi

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/epaper-webui.git
cd epaper-webui
```

### 2. Install Dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-flask python3-pil git
pip3 install -r requirements.txt
```

### 3. Enable SPI (if not already)

```bash
sudo raspi-config nonint do_spi 0
```

### 4. Set Up as a systemd Service

Create `/etc/systemd/system/epaper-webui.service`:

```ini
[Unit]
Description=ePaper Web UI Flask App
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/epaper-webui/app.py
WorkingDirectory=/home/pi/epaper-webui
User=pi
Restart=always
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
```

Replace `/home/pi/epaper-webui` with your actual path if different.

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable epaper-webui
sudo systemctl start epaper-webui
```

## Usage

- Visit `http://<your-pi-ip>:5000`
- Upload an image
- Adjust image settings
- Optionally add overlay text
- Click “Send to Display”

The IP address of the Raspberry Pi will be shown on the ePaper screen automatically at boot.

## Screenshots

*(Add screenshots of the web interface and display output here)*

## TODO

- Multi-line text overlays
- Font selection
- QR code overlay
- Image rotation
- Persistent history

## License

MIT License.
