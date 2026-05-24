# Pi Face Greeter — Roadmap

## Milestone 1: Hardware Validation

- [x] Project scaffold and config
- [x] Camera test (Picamera2 / Camera Module 3)
- [x] TTS test (espeak-ng + USB audio)
- [x] Step 1 validator (camera + TTS, quiet CLI)
- [ ] Confirm Step 1 on real Pi 5

## Milestone 2: Face Enrollment (current)

- [x] `pi-face-greeter-enroll` CLI
- [x] Store images under `data/known_faces/<person_name>/`
- [x] Register person in `config/people.yaml`
- [x] Optional single-face check via OpenCV Haar cascade
- [ ] Confirm enrollment on real Pi 5
- [ ] Generate face embeddings (Step 3)

## Milestone 3: Face Recognition

- [ ] Integrate recognition library (`face_recognition`, DeepFace, or InsightFace)
- [ ] Add confidence threshold in config
- [ ] Require multiple matching frames before greeting
- [ ] Per-person greeting messages from `config/people.yaml`
- [ ] Per-person cooldown overrides

## Milestone 4: Touchscreen UI

- [ ] Kiosk UI on Hosyond 5" DSI display (800×480)
- [ ] Show current status (idle, motion, recognizing, greeting)
- [ ] Show recognized person name
- [ ] Basic admin/setup screens

## Milestone 5: Admin & Operations

- [ ] Local FastAPI admin portal (enroll, test, config)
- [ ] systemd service for boot startup (template in `systemd/`)
- [ ] Privacy mode / mute button
- [ ] Optional logging to SQLite

## Final Step: Motion (PIR)

- [x] PIR sensor module and test script
- [x] Motion validator (`pi-face-greeter-validate-motion`)
- [x] Main loop: motion → capture → placeholder greeting → cooldown
- [ ] Wire PIR and validate on Pi (last hardware step)

## Milestone 6: Enhancements

- [ ] Piper TTS for natural voice (replace espeak-ng)
- [ ] Optional AWS sync for logs or face data
- [ ] Remote monitoring / alerts
