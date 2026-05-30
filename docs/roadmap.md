# Pi Face Greeter — Roadmap

## Milestone 1: Kiosk App (current)

- [x] Kivy kiosk UI on Hosyond 5" DSI display (800×480)
- [x] Swipeable screens: animated face + settings
- [x] Animated face (random blinking eyes, talking mouth during TTS)
- [x] Live camera preview in upper-left with yellow face-detection boxes
- [x] Face presence triggers greeting: "Hi \<name\>" or "Hi friend"
- [x] Settings screen: list/add/edit/delete faces (stub enrollment)
- [ ] Confirm kiosk app on real Pi 5 with DSI display

## Milestone 2: Face Recognition

- [ ] Integrate recognition library (`face_recognition`, DeepFace, or InsightFace)
- [ ] Generate face embeddings from enrolled photos
- [ ] Wire `identify()` to return known names
- [ ] Add confidence threshold in config
- [ ] Require multiple matching frames before greeting
- [ ] Per-person greeting messages from `config/people.yaml`
- [ ] Per-person cooldown overrides

## Milestone 3: Real Enrollment

- [ ] Photo capture flow from settings "Add Face"
- [ ] Reuse or replace CLI `pi-face-greeter-enroll`
- [ ] Optional single-face check via OpenCV Haar cascade
- [ ] Confirm enrollment on real Pi 5

## Milestone 4: Admin & Operations

- [ ] Local FastAPI admin portal (enroll, test, config)
- [ ] systemd service for boot startup (template in `systemd/`)
- [ ] Privacy mode / mute button
- [ ] Optional logging to SQLite

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

- [ ] Piper TTS for natural voice (replace espeak-ng)
- [ ] Optional AWS sync for logs or face data
- [ ] Remote monitoring / alerts
