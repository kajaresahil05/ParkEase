# ParkEase ESP32 entry client

This is the Phase 7 firmware template. It uses Flask HTTP APIs and never
connects to MySQL. The pins match the confirmed hardware assignments:

| Function | GPIO |
| --- | ---: |
| Entry IR | 18 |
| Exit IR | 19 |
| Slot 1 IR | 21 |
| Slot 2 IR | 22 |
| Slot 3 IR | 23 |
| Servo signal | 25 |

## Before compiling

1. Install the ESP32 board package by Espressif in Arduino IDE.
2. Install the `ArduinoJson` and `ESP32Servo` libraries through Library Manager.
3. Copy `secrets.h.example` to `secrets.h` and set Wi-Fi details, the computer's
   LAN URL (for example `http://192.168.1.50:5000`), and the same `IOT_API_KEY`
   stored in `backend/.env`.
4. Add a long random `IOT_API_KEY` to `backend/.env`, then restart Flask.

`127.0.0.1` must not be used as `API_BASE_URL` on the ESP32: it refers to the
ESP32 itself. Use the LAN IPv4 address of the computer running Flask. For a
phone or ESP32 on the same network, Flask must listen on the LAN interface and
the Windows firewall must allow the chosen development port.

## Safe first test

`ENABLE_GATE_CONTROL` defaults to `false`. Flash the sketch, open Serial
Monitor at 115200 baud, and test only Wi-Fi plus entry-sensor reports first.
Keep the servo on its external 5V supply with a common ground; never power it
from the ESP32 3.3V pin. Enable gate control only after that check.

## Current scope

The sketch reports entry detection and polls one-time authorizations. It does
not yet report slot sensors or implement the complete exit state machine. The
exit IR only closes an already authorized entry gate, with a 10-second safety
timeout. Those fuller slot/exit behaviors remain the next phase.
