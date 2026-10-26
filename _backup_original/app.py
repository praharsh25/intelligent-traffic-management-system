from flask import Flask, render_template, jsonify, request
from datetime import datetime
import random
import threading

app = Flask(__name__)
DIRECTIONS = ["North", "East", "South", "West"]
JUNCTIONS = [
    {"id":"J1","name":"Central Square","location":"Main Road × Station Road"},
    {"id":"J2","name":"Market Junction","location":"Market Street × College Road"},
    {"id":"J3","name":"River Bridge","location":"Riverside Road × Ring Road"},
    {"id":"J4","name":"Tech Park Gate","location":"IT Park Road × Airport Road"},
]
lock = threading.RLock()
settings = {"min_green": 8, "max_green": 35}
running, auto_mode, tick = True, True, 0
events = []

def event(message, kind="info", junction=None):
    events.insert(0, {"time":datetime.now().strftime("%H:%M:%S"),"message":message,"kind":kind,"junction":junction})
    del events[60:]

def new_junction(item, idx):
    lanes = {}
    for d in DIRECTIONS:
        lanes[d] = {"vehicles":random.randint(4,22),"waiting":random.randint(1,8),"signal":"RED","green_remaining":0,"total_passed":random.randint(10,90)}
    active = DIRECTIONS[idx]
    lanes[active]["signal"] = "GREEN"
    lanes[active]["green_remaining"] = random.randint(8,20)
    j = {**item,"lanes":lanes,"active_direction":active,"cycle":1}
    update_totals(j)
    return j

def update_totals(j):
    j["total_vehicles"] = sum(x["vehicles"] for x in j["lanes"].values())
    j["total_passed"] = sum(x["total_passed"] for x in j["lanes"].values())
    n = j["total_vehicles"]
    j["congestion"] = "Low" if n < 28 else "Moderate" if n < 58 else "Heavy"

junctions = {x["id"]:new_junction(x,i) for i,x in enumerate(JUNCTIONS)}
last_updated = datetime.now().isoformat(timespec="seconds")
event("Traffic simulation initialized. Adaptive signal control is ready.", "success")

def choose_next(j):
    lanes = j["lanes"]
    scores = {d: lanes[d]["vehicles"]*1.4 + lanes[d]["waiting"]*2.2 + random.random()*3 for d in DIRECTIONS}
    current = j["active_direction"]
    candidates = [d for d in DIRECTIONS if d != current]
    nxt = max(candidates, key=lambda d:scores[d])
    return DIRECTIONS[(DIRECTIONS.index(current)+1)%4] if scores[nxt] < scores[current]+2 else nxt

def step():
    global tick, last_updated
    with lock:
        tick += 1
        for j in junctions.values():
            for d, lane in j["lanes"].items():
                lane["vehicles"] = min(60, lane["vehicles"] + random.choices([0,1,2,3],[25,45,23,7])[0])
                if d != j["active_direction"]:
                    lane["waiting"] = min(60, lane["waiting"] + (1 if lane["vehicles"] else 0))
                else:
                    cleared = min(lane["vehicles"], random.randint(2,6))
                    lane["vehicles"] -= cleared
                    lane["total_passed"] += cleared
                    lane["waiting"] = max(0,lane["waiting"]-random.randint(1,4))
            active = j["lanes"][j["active_direction"]]
            active["green_remaining"] = max(0, active["green_remaining"]-1)
            if auto_mode and running and active["green_remaining"] <= 0:
                nxt = choose_next(j)
                for lane in j["lanes"].values():
                    lane["signal"], lane["green_remaining"] = "RED", 0
                lane = j["lanes"][nxt]
                queue = lane["vehicles"] + lane["waiting"]
                duration = int(max(settings["min_green"], min(settings["max_green"], settings["min_green"] + queue*0.45)))
                lane["signal"], lane["green_remaining"] = "GREEN", duration
                j["active_direction"], j["cycle"] = nxt, j["cycle"]+1
                event(f'{j["name"]}: green signal moved to {nxt} ({duration}s).', "signal", j["id"])
            update_totals(j)
        last_updated = datetime.now().isoformat(timespec="seconds")

def snapshot():
    with lock:
        return {"running":running,"auto_mode":auto_mode,"tick":tick,"last_updated":last_updated,
                "settings":dict(settings),"intersections":[j for j in junctions.values()],
                "events":events[:20],"summary":{"vehicles":sum(j["total_vehicles"] for j in junctions.values()),
                "passed":sum(j["total_passed"] for j in junctions.values()),
                "heavy":sum(j["congestion"]=="Heavy" for j in junctions.values()),"junctions":len(junctions)}}

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/state")
def api_state(): return jsonify(snapshot())

@app.route("/api/tick", methods=["POST"])
def api_tick():
    step()
    return jsonify(snapshot())

@app.route("/api/control", methods=["POST"])
def api_control():
    global running, auto_mode, tick, junctions
    action = (request.get_json(silent=True) or {}).get("action")
    with lock:
        if action == "pause":
            running = False; event("Simulation paused.","warning")
        elif action == "resume":
            running = True; event("Simulation resumed.","success")
        elif action == "auto":
            auto_mode = True; event("Adaptive signal mode enabled.","success")
        elif action == "manual":
            auto_mode = False; event("Manual signal mode enabled.","warning")
        elif action == "reset":
            tick, running, auto_mode = 0, True, True
            junctions = {x["id"]:new_junction(x,i) for i,x in enumerate(JUNCTIONS)}
            events.clear(); event("Simulation reset to initial traffic conditions.","success")
        else: return jsonify({"error":"Unknown action"}), 400
    return jsonify(snapshot())

@app.route("/api/signal", methods=["POST"])
def api_signal():
    data = request.get_json(silent=True) or {}
    jid, direction = data.get("junction"), data.get("direction")
    with lock:
        if auto_mode: return jsonify({"error":"Switch to Manual mode before changing signals."}),400
        if jid not in junctions or direction not in DIRECTIONS: return jsonify({"error":"Invalid junction or direction."}),400
        j = junctions[jid]
        for d,lane in j["lanes"].items():
            lane["signal"] = "GREEN" if d == direction else "RED"
            lane["green_remaining"] = 15 if d == direction else 0
        j["active_direction"], j["cycle"] = direction, j["cycle"]+1
        event(f'Manual override: {j["name"]} set to {direction} GREEN for 15s.',"warning",jid)
    return jsonify(snapshot())

@app.route("/api/traffic", methods=["POST"])
def api_traffic():
    data = request.get_json(silent=True) or {}
    jid, direction, amount = data.get("junction"), data.get("direction"), data.get("amount",5)
    if not isinstance(amount,int) or not 1 <= amount <= 25: return jsonify({"error":"Amount must be an integer from 1 to 25."}),400
    with lock:
        if jid not in junctions or direction not in DIRECTIONS: return jsonify({"error":"Invalid junction or direction."}),400
        lane = junctions[jid]["lanes"][direction]
        lane["vehicles"] = min(60,lane["vehicles"]+amount)
        lane["waiting"] = min(60,lane["waiting"]+max(1,amount//3))
        update_totals(junctions[jid])
        event(f'{amount} simulated vehicles added to {junctions[jid]["name"]} — {direction} lane.',"info",jid)
    return jsonify(snapshot())

@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json(silent=True) or {}
    try: mn, mx = int(data.get("min_green",settings["min_green"])), int(data.get("max_green",settings["max_green"]))
    except (TypeError,ValueError): return jsonify({"error":"Signal timings must be whole numbers."}),400
    if not 3 <= mn <= 20 or not mn <= mx <= 60: return jsonify({"error":"Minimum must be 3–20s and maximum must be between minimum and 60s."}),400
    with lock:
        settings.update(min_green=mn,max_green=mx)
        event(f"Adaptive timing updated: minimum {mn}s, maximum {mx}s.","success")
    return jsonify(snapshot())

if __name__ == "__main__":
    print("Intelligent Traffic Management System — http://127.0.0.1:5000")
    app.run(debug=True, use_reloader=False)
