"""Deterministic population-level controller derived from the BANC v888 graph.

The source graph is reduced offline into nine flow-by-side populations. This
service simulates those populations as a small leaky rate network. It does not
simulate individual neurons, spikes, eyes, muscles, or validated fly behavior.
"""
from __future__ import annotations
import math
import os
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request

app = Flask(__name__)
_lock = threading.Lock()
_reset_epoch = time.time()  # Render Free restarts lose this in-memory value.
_GRAPH_PATH = Path(__file__).with_name("connectome_weights.json")
with _GRAPH_PATH.open("r", encoding="utf-8") as _graph_file:
    _GRAPH = json.load(_graph_file)
_NAMES = tuple(_GRAPH["groups"])
_EDGE_COUNTS = _GRAPH["edge_count_matrix"]
if len(_NAMES) != 9 or len(_EDGE_COUNTS) != 9 or any(len(row) != 9 for row in _EDGE_COUNTS):
    raise RuntimeError("connectome_weights.json must contain a 9 by 9 population graph")

# The measured edges mapped to these nine annotated populations are row-normalized
# by target population to keep the reduced model numerically stable. These are not
# fitted synaptic dynamics.
_INCOMING = []
for target in range(len(_NAMES)):
    total = sum(_EDGE_COUNTS[source][target] for source in range(len(_NAMES)))
    _INCOMING.append([
        (_EDGE_COUNTS[source][target] / total) if total else 0.0
        for source in range(len(_NAMES))
    ])
_CYCLE_SECONDS = 30.0
_STEP_SECONDS = 0.1

def _sigmoid(v):
    return 1 / (1 + math.exp(-max(-30, min(30, v))))

def _neural_state(elapsed):
    """Evaluate one deterministic cycle of the reduced connectome graph."""
    cycle_time = elapsed % _CYCLE_SECONDS
    phase = 2 * math.pi * cycle_time / _CYCLE_SECONDS
    steps = max(1, math.ceil(cycle_time / _STEP_SECONDS))
    state = [0.15] * len(_NAMES)
    for step in range(steps):
        t = phase * (step + 1) / steps
        # A periodic visual-like input keeps the autonomous game character moving.
        # No camera or player data enters this input signal.
        sensory = (
            0.15 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.0)),
            0.15 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.0 + 1.65)),
            0.12,
        )
        next_state = []
        for target_index in range(len(state)):
            incoming = sum(
                _INCOMING[target_index][source_index] * state[source_index]
                for source_index in range(len(state))
            )
            external = sensory[target_index] if target_index < 3 else 0.0
            target_activity = _sigmoid(4.0 * (0.8 * incoming + external - 0.42))
            next_state.append(state[target_index] + _STEP_SECONDS * (target_activity - state[target_index]) / 0.6)
        state = next_state
    return state

def _fly_at(now):
    with _lock:
        anchor = _reset_epoch
    t = max(0.0, now - anchor)
    n = _neural_state(t)
    cycle_phase = 2 * math.pi * (t % _CYCLE_SECONDS) / _CYCLE_SECONDS
    turn_signal = n[7] - n[6]
    heading = math.atan2(12.0 * math.cos(cycle_phase), -8.0 * math.sin(cycle_phase)) + 0.7 * turn_signal
    speed = 4.0 + 4.0 * ((n[6] + n[7]) / 2.0)
    return {
        "x": round(12 * math.sin(cycle_phase) + 2 * turn_signal, 4),
        "y": round(5 + 1.5 * math.sin(cycle_phase * 2) + 0.5 * (n[8] - 0.5), 4),
        "z": round(-12 + 8 * math.cos(cycle_phase + 0.7 * turn_signal), 4),
        "rotation": round(math.degrees(heading) % 360, 3), "state": "flying",
        "speed": round(speed, 3),
        "neurons": {name: round(value, 5) for name, value in zip(_NAMES, n)},
        "brain_model": _GRAPH["dataset"],
        "simulation_level": "9 connectome-derived populations; not a full neuron simulation",
        "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "elapsed": round(t, 3),
    }

@app.get("/")
def index():
    return jsonify({"service": "Acchiappa la Mosca", "ok": True, "endpoint": "/fly-position"})

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "brain_model": _GRAPH["dataset"],
        "source_edges": _GRAPH["source_edge_count"],
        "edges_in_population_model": _GRAPH["included_edge_count"],
        "utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })

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
