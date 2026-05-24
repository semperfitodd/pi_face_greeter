# Pi Face Greeter — Roadmap

## Milestone 1: Hardware Validation (current)

- [x] Project scaffold and config
- [x] PIR test script
- [x] Camera test script (Picamera2 / Camera Module 3)
- [x] TTS test script (espeak-ng + USB audio)
- [x] Main loop: motion → capture → placeholder greeting → cooldown
- [ ] Confirm all hardware on real Pi 5

## Milestone 2: Face Enrollment

- [ ] Add `scripts/enroll_face.py` to capture and store reference photos
- [ ] Store images under `data/known_faces/<person_name>/`
- [ ] Validate image quality (single face, adequate lighting)
- [ ] Generate face embeddings from enrolled photos

## Milestone 3: Face Recognition

- [ ] Integrate recognition library (`face_recognition`, DeepFace, or InsightFace)
- [ ] Add confidence threshold in config
- [ ] Require multiple matching frames before greeting (reduce false positives)
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

## Milestone 6: Enhancements

- [ ] Piper TTS for natural voice (replace espeak-ng)
- [ ] Optional AWS sync for logs or face data
- [ ] Remote monitoring / alerts

## Future TODO summary

| Area | Item |
|------|------|
| Recognition | Face enrollment script |
| Recognition | Known face storage under `data/known_faces/<person_name>/` |
| Recognition | Face embeddings generation |
| Recognition | Library integration with confidence threshold |
| Recognition | Multi-frame match requirement |
| Greetings | Per-person messages and cooldown |
| UI | Touchscreen kiosk on DSI display |
| Admin | Local FastAPI portal |
| Ops | systemd boot service |
| Privacy | Mute / privacy mode |
| Data | SQLite logging |
| Cloud | Optional AWS sync |
