 # Pi Face Greeter

A Raspberry Pi 5 face recognition greeter. A PIR motion sensor wakes the system, the camera captures frames, and a personalized spoken greeting plays through a USB speaker. A touchscreen display will show status and admin info in a future release.

**Version 1 goal:** Validate all hardware — PIR, Camera Module 3, USB audio, and the motion-triggered main loop with a placeholder greeting.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Hardware List](#hardware-list)
4. [Physical Assembly Order](#physical-assembly-order)
5. [GPIO Wiring](#gpio-wiring)
6. [Raspberry Pi OS Setup](#raspberry-pi-os-setup)
7. [Enable Camera](#enable-camera)
8. [USB Audio Setup](#usb-audio-setup)
9. [Develop on Mac](#develop-on-mac)
10. [Deploy to Raspberry Pi](#deploy-to-raspberry-pi)
11. [Step 1 Validation (No PIR)](#step-1-validation-no-pir)
12. [Hardware Test Order](#hardware-test-order)
13. [Run the Main App](#run-the-main-app)
14. [Project Structure](#project-structure)
15. [Troubleshooting](#troubleshooting)
16. [Next Milestones](#next-milestones)

---

## Project Overview

Pi Face Greeter sits by your door and:

1. Waits for motion (PIR sensor)
2. Wakes the camera and captures frames
3. Identifies known faces *(future)*
4. Plays a personalized greeting through speakers
5. Shows status on a touchscreen *(future)*

**Current milestone (Step 1):** Validate Camera Module 3 + USB TTS without PIR.

- Captures a test JPEG to `data/captured/`
- Speaks the placeholder greeting via espeak-ng
- PIR is disabled until wired (`pir.enabled: false`)

**After PIR is wired:** motion-triggered main loop with cooldown.

**Not yet implemented:** face enrollment, face recognition, touchscreen UI, auto-start on boot.

---

## Architecture

![Pi Face Greeter Architecture](architecture/architecture.svg)

Source: [architecture/architecture.drawio](architecture/architecture.drawio). Solid boxes = Step 1 (active). Dashed = Step 2 / future (PIR, main loop, DSI UI).

Regenerate after diagram edits:

```bash
drawio -x -f svg -o architecture/architecture.svg architecture/architecture.drawio
drawio -x -f png -o architecture/architecture.png architecture/architecture.drawio
```

| Module | Path | Role |
|--------|------|------|
| Main loop | `src/pi_face_greeter/main.py` | Motion → capture → TTS → cooldown |
| Step 1 validator | `src/pi_face_greeter/validate_step1.py` | Camera + TTS (no PIR) |
| PIR | `src/pi_face_greeter/pir_sensor.py` | gpiozero wrapper for AM312 |
| Camera | `src/pi_face_greeter/camera.py` | Picamera2 (CSI) backend |
| TTS | `src/pi_face_greeter/tts.py` | espeak-ng subprocess |
| Config | `config/config.yaml` | Runtime settings |

**Camera path for this build:** You have a **Raspberry Pi Camera Module 3** (CSI). Use **Picamera2** (`camera.backend: picamera2` in config). OpenCV is used only to save JPEGs and will support face detection later.

**USB webcam alternative:** Set `camera.backend: opencv` and `camera.device_index: 0` — not needed for Camera Module 3.

See [docs/wiring.md](docs/wiring.md) for physical connections and [docs/roadmap.md](docs/roadmap.md) for future work.

---

## Hardware List

| Component | Notes |
|-----------|-------|
| Raspberry Pi 5 | 64-bit Raspberry Pi OS Bookworm |
| Official 27W USB-C power supply | Required for stable camera + CPU load |
| Active cooler | Recommended for sustained use |
| Raspberry Pi Camera Module 3 | CSI ribbon cable |
| AM312 / HC-SR312 mini PIR | 3.3V power only |
| USB sound card + 8Ω 5W speaker | Driver-free, plug and play |
| Hosyond 5" MIPI DSI touchscreen | 800×480, capacitive — future UI |
| Female-to-female jumper wires | For PIR wiring |

---

## Physical Assembly Order

Follow this order on the bench before installing software.

### Step 1: Pi 5 base system

1. Attach the active cooler to the Pi 5.
2. Insert a microSD card flashed with **Raspberry Pi OS (64-bit) Bookworm**.
3. Connect HDMI (or DSI display later), keyboard, and the **27W USB-C power supply**.
4. Boot and complete initial setup (user, Wi‑Fi, updates).
5. Verify architecture:

```bash
uname -m
# Expected: aarch64
```

### Step 2: Camera Module 3

1. **Power off** the Pi.
2. Connect the CSI ribbon to the camera connector (see [docs/wiring.md](docs/wiring.md)).
3. Power on and enable the camera (see [Enable Camera](#enable-camera)).

### Step 3: DSI touchscreen (optional now)

1. **Power off** the Pi.
2. Connect the Hosyond 5" DSI ribbon per the display manual.
3. Power on — you should see the desktop at 800×480.
4. No application code uses the display in v1.

### Step 4: PIR sensor wiring

Wire the PIR **after** camera and audio are tested — see [GPIO Wiring](#gpio-wiring).

### Step 5: USB sound card + speaker

1. Connect the speaker to the sound card header.
2. Plug the USB sound card into the Pi.
3. Complete [USB Audio Setup](#usb-audio-setup).

### Step 6: Final checklist

- [ ] Pi boots reliably with PSU + cooler
- [ ] Camera detected (`rpicam-hello --list-cameras`)
- [ ] USB audio works (`speaker-test`)
- [ ] PIR wired to 3.3V, GND, GPIO17
- [ ] Project cloned and dependencies installed

---

## GPIO Wiring

| PIR pin | Pi physical pin | Pi function |
|---------|-----------------|-------------|
| VCC (+) | Pin 1           | 3.3V        |
| GND (-) | Pin 6           | GND         |
| OUT (S) | Pin 11          | GPIO17      |

**Do not power the PIR from 5V.** The AM312 / HC-SR312 expects 3.3V.

Full diagrams: [docs/wiring.md](docs/wiring.md)

---

## Raspberry Pi OS Setup

1. Flash **Raspberry Pi OS (64-bit) Bookworm** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Enable SSH and set hostname/user in Imager if headless.
3. Boot the Pi and update:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

4. Clone this project:

```bash
cd ~
git clone <your-repo-url> pi_face_greeter
cd pi_face_greeter
```

---

## Enable Camera

1. Enable the camera interface:

```bash
sudo raspi-config
# Interface Options → Camera → Enable → Finish → Reboot
```

2. Verify Camera Module 3:

```bash
rpicam-hello --list-cameras
rpicam-hello -t 5000
```

You should see a live preview for 5 seconds. Pi 5 exposes `cam0` and `cam1`; either port works.

**Do not use** legacy `raspicam` or `picamera` — they are unsupported on Bookworm.

---

## USB Audio Setup

1. List playback devices:

```bash
aplay -l
```

Example output:

```
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
```

2. Test the USB card (adjust card/device numbers):

```bash
speaker-test -D plughw:1,0 -c 2 -t wav
```

Press Ctrl+C after confirming audio.

3. Set the device in `config/config.yaml`:

```yaml
tts:
  alsa_device: "plughw:1,0"
```

Leave as `null` to use the system default if HDMI/audio jack is preferred.

---

## Develop on Mac

```bash
git clone <your-repo-url> pi_face_greeter
cd pi_face_greeter
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Hardware tests (camera, TTS, PIR) run on the Pi only. Push after `pytest` passes.

---

## Deploy to Raspberry Pi

```bash
cd ~/pi_face_greeter
git pull
source .venv/bin/activate
pip install -e .
```

Install system packages (once on the Pi):

```bash
sudo apt update
sudo apt install -y \
  python3-picamera2 python3-libcamera rpicam-apps \
  python3-gpiozero python3-lgpio python3-opencv \
  espeak-ng alsa-utils v4l-utils

sudo usermod -aG video,gpio $USER
```

Create the venv on the Pi with system site packages so apt libraries are visible:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

Log out and back in for group membership. Do **not** pip install `picamera2`, `opencv-python`, or `RPi.GPIO`.

---

## Step 1 Validation (No PIR)

After camera and USB audio are wired, set `tts.alsa_device` if needed (see [USB Audio Setup](#usb-audio-setup)), then:

```bash
pi-face-greeter-validate-step1
```

Success: `data/captured/step1_frame.jpg` exists and the placeholder greeting is audible. Exit code `0`.

Manual single greet (no PIR, no loop):

```bash
pi-face-greeter-greet-once
```

---

## Python Setup

Legacy note: `pip install -r requirements.txt` still works for runtime deps only. Prefer `pip install -e ".[dev]"` on Mac or `pip install -e .` on Pi.

**Pi venv must use `--system-site-packages`** so Picamera2, gpiozero, and OpenCV from apt are available.

---

## Install Dependencies

See [Deploy to Raspberry Pi](#deploy-to-raspberry-pi) for the apt install block.

---

## Hardware Test Order

From project root with venv activated on the **Pi**:

```bash
cd ~/pi_face_greeter
source .venv/bin/activate
```

### 1. Step 1 validation (camera + TTS)

```bash
pi-face-greeter-validate-step1
```

Or run components individually:

```bash
pi-face-greeter-test-camera
pi-face-greeter-test-tts
```

### 2. PIR (when wired)

Set `pir.enabled: true` in `config/config.yaml`, then:

```bash
pi-face-greeter-test-pir
```

### 3. Full motion loop

```bash
pi-face-greeter
```

Expected: motion → JPEG in `data/captured/` → greeting → 30s cooldown. Ctrl+C to stop.

---

## Run the Main App

Requires `pir.enabled: true` in config.

```bash
pi-face-greeter
```

Configuration: `config/config.yaml`. Logs: `data/logs/greeter.log`.

### systemd (future — do not enable until tested)

A service template is in `systemd/pi-face-greeter.service`. After hardware validation:

```bash
# Edit paths in the service file first, then:
sudo cp systemd/pi-face-greeter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-face-greeter
sudo systemctl start pi-face-greeter
sudo systemctl status pi-face-greeter
```

---

## Project Structure

```
pi_face_greeter/
├── pyproject.toml
├── README.md
├── architecture/
│   ├── architecture.drawio
│   ├── architecture.svg
│   └── architecture.png
├── config/
│   ├── config.yaml
│   └── people.yaml
├── src/pi_face_greeter/
│   ├── main.py
│   ├── validate_step1.py
│   ├── greet_once.py
│   ├── cli.py
│   ├── camera.py
│   ├── tts.py
│   ├── pir_sensor.py
│   └── ...
├── scripts/                 # thin wrappers (backward compatible)
├── tests/
├── data/
├── docs/
└── systemd/
```

---

## Troubleshooting

### PIR never triggers

- Confirm **3.3V** on pin 1 (not 5V).
- Confirm OUT → GPIO17 (physical pin 11).
- Wait 15–30 s after power-on for sensor stabilization.
- Keep sensor away from heat sources.

### PIR triggers constantly

- Repoint away from vents, windows, or moving curtains.
- Increase distance from the Pi board (PIR can be sensitive to warm electronics).

### Camera not detected

```bash
rpicam-hello --list-cameras
```

- Reseat CSI ribbon with Pi **powered off**; contacts face the board.
- Enable camera in `raspi-config`.
- Try the other CSI port (`cam0` vs `cam1`).

### No audio from USB speaker

```bash
aplay -l
speaker-test -D plughw:1,0 -c 2 -t wav
```

- Set `tts.alsa_device` in `config/config.yaml`.
- Confirm speaker wired to sound card header with correct polarity.
- Check volume: `alsamixer` (select USB card with F6).

### gpiozero / GPIO errors on Pi 5

- Use **gpiozero** with **lgpio** (installed via apt above).
- Do **not** use `RPi.GPIO` — it does not work on Pi 5.
- Ensure user is in the `gpio` group: `groups` should list `gpio`.

### Picamera2 import errors in venv

- Recreate venv with system site packages:

```bash
python3 -m venv --system-site-packages .venv
```

- Confirm apt package: `dpkg -l python3-picamera2`

### Permission denied on camera

```bash
sudo usermod -aG video $USER
# log out and back in
```

---

## Next Milestones

See [docs/roadmap.md](docs/roadmap.md) for the full roadmap:

1. Face enrollment script and `data/known_faces/` storage
2. Face recognition with confidence threshold
3. Per-person greetings and cooldown
4. Hosyond DSI touchscreen kiosk UI
5. FastAPI admin portal
6. systemd auto-start
7. Piper TTS upgrade

---

## TODO List

- [ ] Add face enrollment script
- [ ] Store known face images under `data/known_faces/<person_name>/`
- [ ] Generate face embeddings
- [ ] Add face recognition (`face_recognition`, DeepFace, or InsightFace)
- [ ] Add confidence threshold
- [ ] Require multiple matching frames before greeting
- [ ] Add per-person greeting messages
- [ ] Add per-person cooldown
- [ ] Add touchscreen kiosk UI (Hosyond 5" DSI)
- [ ] Add local FastAPI admin portal
- [ ] Add systemd service for boot startup
- [ ] Add privacy mode / mute button
- [ ] Add optional logging to SQLite
- [ ] Add optional AWS sync later
- [ ] Upgrade TTS to Piper for natural voice

---

## License

MIT (or your chosen license)
