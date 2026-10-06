# Pi Face Greeter — Roadmap

## Milestone 1: Kiosk App (current)

- [x] Kivy kiosk UI on Hosyond 5" DSI display (800×480)
- [x] Swipeable screens: animated face + settings
- [x] Animated face (random blinking eyes, talking mouth during TTS)
- [x] Live camera preview in upper-left with yellow face-detection boxes
- [x] Face presence triggers greeting: "Hi \<name\>" or "Hi friend"
- [x] Settings screen: list/add/edit/delete faces (live enrollment from camera)
- [ ] Confirm kiosk app on real Pi 5 with DSI display

## Milestone 2: Face Recognition

- [x] Integrate recognition library (`face_recognition` / dlib)
- [x] Generate face embeddings from enrolled photos
- [x] Wire `identify()` to return known names
- [x] Add confidence threshold in config (`recognition.tolerance`)
- [x] Require multiple matching frames before greeting
- [x] Per-person greeting messages from `config/people.yaml` (`greeting:` field)
- [x] Per-person cooldown overrides

## Milestone 3: Real Enrollment

- [x] Photo capture flow from settings "Add Face"
- [x] CLI `pi-face-greeter-enroll` saves photos + `encodings.npy`
- [x] Single-face check via OpenCV Haar cascade during enrollment
- [ ] Confirm enrollment on real Pi 5

## Milestone 4: Admin & Operations

- [ ] Local FastAPI admin portal (enroll, test, config)
- [ ] systemd service for boot startup (template in `systemd/`)
- [ ] Privacy mode / mute button
- [ ] Optional logging to SQLite

## Milestone 5: Local Conversation (Ollama SLM)

One-way spoken greetings via a local SLM on the Pi 5. No microphone or cloud API.

- [x] Install Ollama on Raspberry Pi 5 (`scripts/setup_system.sh`)
- [x] Pull a Pi-friendly SLM via `scripts/setup_venv.sh` (default `llama3.2:1b`)
- [x] Add `ollama` config section (`enabled`, `base_url`, `model`, `timeout_seconds`, `max_tokens`)
- [x] Ollama client module (HTTP to `localhost:11434`; health check; graceful fallback)
- [x] Context-aware prompts: known name, time of day — short replies (1–2 sentences)
- [x] Greeting flow in kiosk and PIR loop: SLM text → Piper TTS → cooldown → idle
- [x] CLI smoke test (`pi-face-greeter-test-ollama`)
- [ ] Confirm conversation latency and stability on real Pi 5 hardware

## Milestone 6: Freyja voice conversation

Local mic + STT + multi-turn chat with **Freyja** (executive assistant persona) on the Pi 5. No cloud API.

- [x] Shared `MicStream` (`mic.py`) for wake word + conversation
- [x] Silero VAD utterance detection (`vad.py`)
- [x] faster-whisper `tiny.en` STT (`stt.py`, `[stt]` extra)
- [x] Ollama streaming `/api/chat` with sentence-by-sentence TTS
- [x] Fixed opener: "Hi, \<name\>. How are you?" then listen
- [x] Wake word ("Hey Freyja") bypasses greet cooldown
- [x] Kiosk + optional PIR loop integration; cooldown after conversation ends
- [x] `assistant` + `conversation` + `stt` + `wake_word` config sections
- [x] CLI smoke tests (`pi-face-greeter-test-stt`, `pi-face-greeter-test-wake`)
- [x] `./scripts/start.sh` — verify install, Ollama, launch kiosk
- [ ] Train and ship `data/models/hey_freyja.onnx` on real Pi hardware
- [ ] Confirm latency and stability on real Pi 5 hardware (mic + speaker)

**Out of scope:** cloud LLMs, always-on listening without face or wake word.

## Final Step: Motion (PIR) — optional

- [x] PIR sensor module and test script
- [x] Motion validator (`pi-face-greeter-validate-motion`)
- [x] Main loop: motion → capture → placeholder greeting → cooldown
- [ ] Wire PIR and validate on Pi (optional; camera presence may suffice)

## Hardware Validation (supporting)

- [x] Project scaffold and config
- [x] Camera test (Picamera2 / Camera Module 3)
- [x] TTS test (espeak-ng + USB audio)
- [x] Step 1 validator (camera + TTS, quiet CLI)
- [x] CLI enrollment (`pi-face-greeter-enroll`)
- [ ] Confirm Step 1 on real Pi 5

## Enhancements

- [x] Piper TTS for natural voice (replace espeak-ng)
- [x] Ollama SLM for light local conversation (see Milestone 5)
- [ ] Optional AWS sync for logs or face data
- [ ] Remote monitoring / alerts
