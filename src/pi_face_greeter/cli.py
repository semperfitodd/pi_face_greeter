from __future__ import annotations

import logging
import sys
import time

from pi_face_greeter.camera import create_camera
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.logger import setup_logging
from pi_face_greeter.pir_sensor import PIRSensor
from pi_face_greeter.tts import speak

logger = logging.getLogger("pi_face_greeter.cli")

TEST_TTS_PHRASE = "Pi Face Greeter audio test. If you can hear this, text to speech is working."
PIR_TEST_SECONDS = 30


def test_camera() -> int:
    config = load_config()
    setup_logging(level=config.get("logging", {}).get("level", "INFO"))

    camera_cfg = config.get("camera", {})
    if not camera_cfg.get("enabled", True):
        print("Camera is disabled in config/config.yaml")
        return 1

    from pathlib import Path

    capture_dir = Path(camera_cfg.get("capture_dir", "data/captured"))
    output_path = capture_dir / "test_frame.jpg"

    print(f"Capturing test frame using backend: {camera_cfg.get('backend', 'picamera2')}")
    print(f"Output: {output_path}\n")

    camera = create_camera(camera_cfg)
    try:
        frame = camera.capture_frame()
        saved = camera.save_frame(frame, output_path)
        print(f"Success: saved {saved} ({saved.stat().st_size} bytes)")
        return 0
    except Exception as exc:
        print(f"Camera test failed: {exc}", file=sys.stderr)
        logger.exception("Camera test failed")
        return 1
    finally:
        camera.close()


def test_tts() -> int:
    config = load_config()
    setup_logging(level=config.get("logging", {}).get("level", "INFO"))

    tts_cfg = config.get("tts", {})
    alsa_device = tts_cfg.get("alsa_device")
    voice = tts_cfg.get("voice", "en")

    print("TTS test using espeak-ng")
    if alsa_device:
        print(f"ALSA device: {alsa_device}")
    else:
        print("ALSA device: default (set tts.alsa_device in config if silent)")
    print(f"Phrase: {TEST_TTS_PHRASE}\n")

    try:
        speak(TEST_TTS_PHRASE, voice=voice, alsa_device=alsa_device)
        print("TTS test complete.")
        return 0
    except Exception as exc:
        print(f"TTS test failed: {exc}", file=sys.stderr)
        logger.exception("TTS test failed")
        return 1


def test_pir() -> int:
    config = load_config()
    setup_logging(level=config.get("logging", {}).get("level", "INFO"))

    pir_cfg = config.get("pir", {})
    if not pir_cfg.get("enabled", False):
        print("PIR is disabled in config. Set pir.enabled: true when the sensor is wired.")
        return 1

    gpio_pin = pir_cfg.get("gpio_pin", 17)
    print(f"PIR test on GPIO {gpio_pin} for {PIR_TEST_SECONDS} seconds.")
    print("Wave your hand in front of the sensor. Press Ctrl+C to stop early.\n")

    motion_count = 0
    end_time = time.monotonic() + PIR_TEST_SECONDS

    with PIRSensor(gpio_pin=gpio_pin) as pir:
        while time.monotonic() < end_time:
            if pir.wait_for_motion(timeout=1.0):
                motion_count += 1
                print(f"[{time.strftime('%H:%M:%S')}] Motion detected (#{motion_count})")
                time.sleep(0.5)

    print(f"\nPIR test complete. Motion events: {motion_count}")
    if motion_count == 0:
        print("No motion detected. Check wiring and 3.3V power.")
        return 1
    return 0
