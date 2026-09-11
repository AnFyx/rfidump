# RFIDump: RFID weighing station for organic waste bins

Prototype of a weighing station that identifies organic waste bins by RFID, shows the bin and its weight on a live web page, and lets a gloved operator rate the sorting quality with physical buttons.

Built in June 2026 during GarageWeek, the innovation week of ISEN Méditerranée engineering school, by team BioNova (four students), for Les Alchimistes Côte d'Azur, a company that collects food waste and composts it locally. Code identifiers are in English; comments, docstrings and the user interface are in French.

## The problem

On a composting site, operators weigh and inspect each incoming bin while wearing gloves in a dirty environment. Every manual data entry means removing gloves or typing on an unsuitable device. RFIDump reduces the interaction to presenting the bin and pressing one large button.

## How it works

1. An RFID tag is fixed on each bin. Its UID is the only data read: bin information lives in a local SQLite database, so tags never need to be written.
2. When a bin reaches the reading zone of the weighing bench, the station looks up the bin, reads the weight and pushes the new state to every open browser through Server-Sent Events.
3. The operator rates the quality of the sorting from 1 to 3 stars with physical buttons. The weighing is recorded.
4. A photo can be taken on demand as proof. It is linked to the weighing whether it is taken before or after the rating.

A tag left on the bench is read again at every poll: repeated reads of the same UID within a grace period count as the same presentation, so each presentation produces at most one weighing.

## Project status

| Component | Simulation mode | Real mode (Raspberry Pi) |
|---|---|---|
| Web page, live updates, database | Complete | Complete |
| RFID reader (RC522 over SPI) | Simulated | Implemented, not yet validated on hardware |
| Rating and photo buttons (GPIO) | Simulated | Implemented, not yet validated on hardware |
| Camera | Placeholder image | Extension point (`NotImplementedError`) |
| Scale | Random weight | Extension point (`NotImplementedError`) |

In simulation mode, a control panel in the page replaces the hardware: present a bin, rate it, take a photo.

## Architecture

```
app.py                Flask server: page, event stream (SSE), simulation endpoints
station.py            Business logic: station state, weighing cycle, event broker
db.py                 SQLite access: bins (UID -> establishment) and weighings
config.py             Settings and environment variables
hardware/
├── base.py           Abstract interfaces: RFID reader, scale, camera, button panel
├── simulator.py      Simulated implementations (PC, no hardware)
├── real.py           Raspberry Pi implementations (RC522, GPIO)
└── __init__.py       Factory selecting the simulated or real implementation
templates/, static/   Web page (vanilla JavaScript, no external resource)
tests/                Unit tests (simulation mode)
```

A background thread polls the reader and updates the station state; the event broker pushes each change to the connected browsers; Flask only reads the state. The rest of the code depends only on the hardware interfaces, so switching from simulation to the real station is a single environment variable.

## Running on a PC (simulation)

Requirements: Python 3.10 or later.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt      # Windows: .venv\Scripts\python.exe
.venv/bin/python app.py
```

Open http://127.0.0.1:8000 and use the simulation panel at the bottom of the page.

## Running on a Raspberry Pi (real mode)

```bash
# 1. Enable SPI for the RC522 reader
sudo raspi-config        # Interface Options -> SPI -> Enable, then reboot

# 2. System packages
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-flask python3-spidev python3-gpiozero python3-lgpio python3-pip

# 3. RC522 library
pip3 install -r requirements.txt --break-system-packages

# 4. Only if GPIO access fails at runtime on Bookworm
sudo apt install -y python3-rpi-lgpio

# 5. Start, reachable from the local network (see Security)
STATION_HW=real STATION_HOST=0.0.0.0 python3 app.py
```

Then browse to `http://<pi-hostname>:8000` from another device on the same network.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `STATION_HW` | `sim` | `sim` or `real` hardware |
| `STATION_HOST` | `127.0.0.1` | Listening interface; `0.0.0.0` exposes the station to the network |
| `STATION_PORT` | `8000` | Listening port, validated at startup |
| `STATION_DB_PATH` | `station.db` next to the code | SQLite database location |

## Wiring (real mode)

The RC522 is a **3.3 V only** module: 5 V destroys it. The Pi's GPIO pins are 3.3 V, so no level shifter is needed.

| RC522 | Pi (BCM) | Physical pin |
|---|---|---|
| SDA (SS) | GPIO8 (CE0) | 24 |
| SCK | GPIO11 | 23 |
| MOSI | GPIO10 | 19 |
| MISO | GPIO9 | 21 |
| RST | GPIO25 | 22 |
| 3.3V | 3V3 | 1 |
| GND | GND | 6 |
| IRQ | not connected | — |

Each push button connects a GPIO pin to ground; the internal pull-up is enabled in software, with a 100 ms debounce.

| Button | GPIO (BCM) | Physical pin |
|---|---|---|
| 1 star | GPIO5 | 29 |
| 2 stars | GPIO6 | 31 |
| 3 stars | GPIO13 | 33 |
| Photo | GPIO19 | 35 |
| Common ground | GND | 39 |

Pin numbers can be changed in `hardware/real.py`.

## Security

The station is designed for a **trusted local network**: a single device on a composting site, not an internet-facing service.

What is in place:
- **Local by default**: the server only listens on `127.0.0.1` unless `STATION_HOST` says otherwise.
- **Simulation endpoints** are refused outside simulation mode (HTTP 403) and require a JSON body (HTTP 415 otherwise), so a third-party web page cannot trigger them with a plain form.
- **Input validation** on the server side (UID type and length, score bounds), and parameterised SQL queries only.
- **Resource limits**: bounded event queue per client and a maximum number of simultaneous event-stream clients (HTTP 503 beyond it), since each client holds a server thread.
- **Headers**: `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`; the page loads no external resource and never inserts data as HTML.
- **No debugger**: Flask runs with `debug=False`.

Known limitations:
- **No authentication and no HTTPS.** With `STATION_HOST=0.0.0.0`, anyone on the network can watch weighings live and open the stored photos. Put the station on an isolated network or VLAN, or behind a reverse proxy with authentication and TLS.
- **Flask development server.** Enough for a single-station prototype; a real deployment should use a production WSGI server.
- **No Host header validation**, so a malicious web page could reach a station bound to localhost through DNS rebinding. Low impact here (read-only state, simulation commands disabled in real mode), but to address before any deployment.

## Tests

```bash
.venv/bin/python -m pytest
```

The tests run on a PC in simulation mode with a temporary database. They cover the weighing cycle (tag left on the bench, repeated button presses, grace period, unknown bins, photos before and after rating), the event broker limits, HTTP validation of the simulation commands, and configuration parsing.

## History and credits

- The first commit contains the code exactly as submitted at the end of GarageWeek (June 2026). Later commits, made in September 2026 to prepare the publication, fix the weighing cycle, harden the server, and add the tests and this README.
- Code: Thomas Iliot ([@AnFyx](https://github.com/AnFyx)), developed with AI coding assistance (Claude Code) under my direction.
- Project: team BioNova, GarageWeek 2026, ISEN Méditerranée, for Les Alchimistes.

No license: all rights reserved.
