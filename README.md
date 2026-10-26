# Intelligent Traffic Management System

A complete software-only, IoT-style traffic simulation. No cameras, sensors, microcontrollers, or other hardware are required.

## Features
- Four simulated intersections with North/East/South/West lanes.
- Synthetic vehicle arrivals, queue estimates, and waiting counts.
- Adaptive green-signal selection based on estimated queue pressure.
- Configurable minimum and maximum green duration.
- Manual signal override, pause/resume, and reset.
- Congestion labels, vehicle throughput metrics, signal cycle counts, and event log.
- JSON API endpoints and responsive web dashboard.

## Requirements
Python 3.9+ and Flask.

## Run on Windows / VS Code
1. Extract the ZIP file.
2. Open the extracted `intelligent_traffic_management_system` folder in VS Code.
3. Select **Terminal → New Terminal**.
4. Install dependencies: `python -m pip install -r requirements.txt`
5. Start the server: `python app.py` (or `py app.py` on Windows if needed).
6. Open **http://127.0.0.1:5000** in your browser.
7. Keep the terminal open while using the dashboard. Press Ctrl+C to stop the server.

## macOS / Linux
Run `python3 -m pip install -r requirements.txt`, then `python3 app.py`; open http://127.0.0.1:5000.

## How to demonstrate
- Leave Adaptive mode on and watch signal changes as queues evolve.
- Switch to Manual mode and use a lane's “→ Green” button.
- Pause/resume the simulation.
- Adjust green timing and click Apply timing rules.
- Reset the simulation to restart the demo.

## API endpoints
- `GET /api/state` — dashboard state and metrics
- `POST /api/tick` — advance one simulation step
- `POST /api/control` — `{"action":"pause|resume|auto|manual|reset"}`
- `POST /api/signal` — `{"junction":"J1","direction":"North"}` (manual mode only)
- `POST /api/traffic` — `{"junction":"J1","direction":"North","amount":5}` (amount 1–25)
- `POST /api/settings` — `{"min_green":8,"max_green":35}`

## Architecture
Browser dashboard (HTML/CSS/JavaScript) ⇄ Flask REST API ⇄ Python traffic simulation state and adaptive controller.

## Abstract
This project demonstrates an intelligent traffic control concept using synthetic data. It estimates traffic pressure for four approaches at each intersection, chooses a suitable next green direction, and adjusts green duration within configurable limits. The dashboard provides network-wide summaries and junction-level signal states. It is for academic demonstration only and must not be used to control real road infrastructure.

## Limitations
Traffic is randomly simulated rather than measured from physical sensors. State is kept in memory and resets when the Python server restarts. The browser advances the simulation once per second while the dashboard is open.
