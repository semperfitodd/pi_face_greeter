# Pi Face Greeter — Wiring Guide

Physical connections for the Raspberry Pi 5 hardware validation build.

## PIR Sensor (AM312 / HC-SR312)

**Important:** Power the PIR from **3.3V**, not 5V. These mini PIR modules are 3.3V logic.

| PIR pin | Label | Pi physical pin | Pi function |
|---------|-------|-----------------|-------------|
| VCC     | +     | Pin 1           | 3.3V        |
| GND     | -     | Pin 6           | GND         |
| OUT     | S     | Pin 11          | GPIO17      |

### GPIO header (top-down, USB ports facing you)

```
        3.3V  (1) (2)  5V
              (3) (4)  5V
              (5) (6)  GND  ← PIR GND
              ...
GPIO17 ← (11) (12)
              ...
        GND  (39) (40)
```

Use **female-to-female jumper wires** for all three PIR connections.

### PIR placement tips

- Point the dome away from heat sources (heaters, sunny windows, AC vents).
- Allow ~15–30 seconds after power-on for the sensor to stabilize.
- AM312 outputs a short HIGH pulse on motion — normal behavior.

---

## Raspberry Pi Camera Module 3 (CSI)

1. **Power off** the Pi completely.
2. Open the **CSI camera connector** latch on the Pi 5 board.
3. Insert the ribbon cable with the **contacts facing the board** (blue backing faces the Ethernet/USB side on standard Pi cables — verify your cable marking).
4. Close the latch firmly.
5. Pi 5 has two CSI ports (`cam0`, `cam1`). Either works; `cam0` is the standard choice.

Verify after boot:

```bash
rpicam-hello --list-cameras
rpicam-hello -t 5000
```

---

## Hosyond 5" MIPI DSI Touchscreen

1. **Power off** the Pi.
2. Connect the **DSI ribbon** to the display connector on the Pi 5 (separate from CSI).
3. Power the display per its product guide (many connect power via the Pi GPIO 5V/GND pins — check your display manual).
4. On Raspberry Pi OS Bookworm, the display should appear automatically at 800×480.

The touchscreen is **not used by v1 software**. It is for future status/kiosk UI.

---

## USB Sound Card + Speaker

1. Connect the **8Ω 5W speaker** to the sound card's speaker header (+/− polarity as marked).
2. Plug the USB sound card into a Pi 5 USB port.
3. List audio devices:

```bash
aplay -l
```

4. Test output (replace card/device numbers as needed):

```bash
speaker-test -D plughw:1,0 -c 2 -t wav
```

5. Set the device in `config/config.yaml`:

```yaml
tts:
  alsa_device: "plughw:1,0"
```

---

## Recommended assembly order

1. Pi 5 + PSU + active cooler → boot test
2. Camera Module 3 ribbon → camera test
3. DSI touchscreen (optional now) → visual boot check
4. USB sound card + speaker → audio test
5. PIR wiring (last) → motion test

Wire the PIR **last** to avoid false triggers while working on the bench.
