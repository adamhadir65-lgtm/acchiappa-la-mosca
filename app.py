"""Deterministic lightweight Drosophila-inspired fly controller API.

Educational toy network only: it is not a biological connectome reconstruction.
The trajectory is deterministic for a given UTC time and reset anchor.
"""
from __future__ import annotations
import math
import os
import threading
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request

app = Flask(__name__)
_lock = threading.Lock()
_reset_epoch = time.time()  # Render Free restarts lose this in-memory value.
_NAMES = ("visual_left", "visual_right", "turn_left", "turn_right", "speed", "motor")
_W = (
    (0, -.32, .18, -.10, 0, 0), (-.32, 0, -.10, .18, 0, 0),
    (.45, -.25, .12, -.18, 0, 0), (-.25, .45, -.18, .12, 0, 0),
    (.08, .08, 0, 0, .10, .20), (0, 0, .26, -.26, .30, .12),
)

def _sigmoid(v):
    return 1 / (1 + math.exp(-max(-30, min(30, v))))

def _neural_state(elapsed):
    """A small recurrent toy network evaluated with fixed deterministic steps."""
    phase = elapsed * (2 * math.pi / 12)
    state = [.5] * len(_NAMES)
    dt, steps = .05, 48
    for step in range(steps):
        t = phase - (steps - 1 - step) * dt
        sensory = (.5 + .5 * math.sin(t), .5 + .5 * math.sin(t + 1.35), 0, 0, 0, 0)
        next_state = []
        for i in range(len(state)):
            recurrent = sum(_W[i][j] * state[j] for j in range(len(state)))
            target = _sigmoid(2 * (recurrent + sensory[i] * 1.35 - .35))
            next_state.append(state[i] + dt * (target - state[i]) / .45)
        state = next_state
    return state

def _fly_at(now):
    with _lock:
        anchor = _reset_epoch
    t = max(0.0, now - anchor)
    n = _neural_state(t)
    heading = .55 * math.sin(t * .47) + .35 * (n[3] - n[2])
    return {
        "x": round(10 * math.sin(t * .31) + 2 * math.sin(t * .83 + .4), 4),
        "y": round(5 + 2.2 * math.sin(t * .72) + 1.2 * (n[4] - .5), 4),
        "z": round(-12 + 8 * math.cos(t * .27) + 1.5 * math.sin(t * .61), 4),
        "rotation": round(math.degrees(heading) % 360, 3), "state": "flying",
        "speed": round(5 + 2 * n[4], 3),
        "neurons": {name: round(value, 5) for name, value in zip(_NAMES, n)},
        "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "elapsed": round(t, 3),
    }

@app.get("/")
def index():
    return jsonify({"service": "Acchiappa la Mosca", "ok": True, "endpoint": "/fly-position"})

@app.get("/health")
def health():
    return jsonify({"ok": True, "utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})

@app.get("/fly-position")
def fly_position():
    return jsonify(_fly_at(time.time()))

@app.post("/reset")
def reset_fly():
    expected = os.environ.get("CATCH_TOKEN", "")
    if not expected or request.headers.get("X-Catch-Token", "") != expected:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    global _reset_epoch
    with _lock:
        _reset_epoch = time.time()
        epoch = _reset_epoch
    return jsonify({"ok": True, "resetTimestamp": datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
