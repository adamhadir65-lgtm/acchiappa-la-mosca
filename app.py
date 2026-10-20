"""Acchiappa la Mosca API.

The /brain-step endpoint advances a small leaky-integrate-and-fire circuit over
individual neurons and synapses from the male-cns:v1.0 Drosophila connectome.
Visual currents are encoded from a looming object by the caller. The simulator
is intentionally lightweight and is not a complete fly brain or a validated
biophysical model.
"""
from __future__ import annotations
import math
import os
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
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

# Individual-neuron escape subcircuit. Synapse counts are normalized by the
# postsynaptic neuron's total input, then scaled as in a simple LIF model.
_CIRCUIT_PATH = Path(__file__).with_name("escape_circuit.json")
with _CIRCUIT_PATH.open("r", encoding="utf-8") as _circuit_file:
    _CIRCUIT = json.load(_circuit_file)
_NEURONS = _CIRCUIT["neurons"]
_N = len(_NEURONS)
_INDEX = {neuron["bodyId"]: i for i, neuron in enumerate(_NEURONS)}
_TYPES = [neuron["type"] for neuron in _NEURONS]
_INSTANCES = [neuron.get("instance", "") for neuron in _NEURONS]
_RAW = np.zeros((_N, _N), dtype=np.float32)  # [post, pre]
for _edge in _CIRCUIT["edges"]:
    _pre = _INDEX.get(_edge["pre"])
    _post = _INDEX.get(_edge["post"])
    if _pre is not None and _post is not None:
        _RAW[_post, _pre] += float(_edge["weight"])
_TOTALS = _RAW.sum(axis=1, keepdims=True)
_IS_SOURCE = _TOTALS[:, 0] == 0
_TOTALS[_TOTALS == 0] = 1.0
_WEIGHTS = (_RAW / _TOTALS) * np.float32(3.0)
_SOURCES = {
    side: {
        "LC4": np.asarray([i for i, n in enumerate(_NEURONS) if n["type"] == "LC4" and n.get("instance", "").endswith("_" + side)], dtype=np.int32),
        "LPLC2": np.asarray([i for i, n in enumerate(_NEURONS) if n["type"] == "LPLC2" and n.get("instance", "").endswith("_" + side)], dtype=np.int32),
    }
    for side in ("L", "R")
}
_OUTPUTS = {
    side: np.asarray([i for i, n in enumerate(_NEURONS) if n["type"] == "DLMn" and n.get("instance", "").endswith("_" + side)], dtype=np.int32)
    for side in ("L", "R")
}
_GF = np.asarray([i for i, kind in enumerate(_TYPES) if kind == "GF"], dtype=np.int32)
_GF_SIDE = {
    side: np.asarray([i for i in _GF if _INSTANCES[i].endswith("_" + side)], dtype=np.int32)
    for side in ("L", "R")
}
# Treat LC4 and LPLC2 as sensory input layers. The extracted circuit also has
# recurrent edges within these populations, but Roblox supplies their visual
# drive directly as the model's sensory boundary condition.
_SENSORY = np.asarray([i for i, kind in enumerate(_TYPES) if kind in ("LC4", "LPLC2")], dtype=np.int32)
_IS_SOURCE[_SENSORY] = True
_SIMULATION_DESCRIPTION = "327 individual neurons; 20,684 MaleCNS synapses; 1 ms LIF steps"

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

def _finite_vector(value, name):
    if not isinstance(value, list) or len(value) != _N:
        raise ValueError(f"state.{name} must be a list of {_N} numbers")
    arr = np.asarray(value, dtype=np.float32)
    if not np.isfinite(arr).all():
        raise ValueError(f"state.{name} must contain only finite numbers")
    return np.clip(arr, -10.0, 10.0)

def _brain_step(payload):
    dt = float(payload.get("dt", 0.1))
    if not math.isfinite(dt) or dt < 0.02 or dt > 0.25:
        raise ValueError("dt must be between 0.02 and 0.25 seconds")
    state = payload.get("state") or {}
    voltage = _finite_vector(state.get("voltage", [0.0] * _N), "voltage")
    activity = _finite_vector(state.get("activity", [0.0] * _N), "activity")
    activity = np.clip(activity, 0.0, 1.0)
    sensory = payload.get("visual") or {}
    external = np.zeros(_N, dtype=np.float32)
    for side in ("L", "R"):
        side_input = sensory.get(side) or {}
        for kind in ("LC4", "LPLC2"):
            current = float(side_input.get(kind, 0.0))
            if not math.isfinite(current) or current < 0 or current > 4:
                raise ValueError(f"visual.{side}.{kind} must be between 0 and 4")
            external[_SOURCES[side][kind]] = current

    steps = max(1, round(dt * 1000))
    spike_counts = np.zeros(_N, dtype=np.float32)
    for _ in range(steps):
        synaptic_input = _WEIGHTS @ activity
        voltage += np.float32(0.1) * (-voltage + synaptic_input)
        spiked = voltage >= 1.0
        spike_counts += spiked
        voltage[spiked] = 0.0
        source_activity = np.clip(external / 4.0, 0.0, 1.0)
        activity = np.where(_IS_SOURCE, source_activity, spiked.astype(np.float32))

    duration = steps / 1000.0
    left_rate = float(spike_counts[_OUTPUTS["L"]].sum() / max(1, len(_OUTPUTS["L"])) / duration)
    right_rate = float(spike_counts[_OUTPUTS["R"]].sum() / max(1, len(_OUTPUTS["R"])) / duration)
    gf_rate = float(spike_counts[_GF].sum() / max(1, len(_GF)) / duration)
    gf_left_rate = float(spike_counts[_GF_SIDE["L"]].sum() / max(1, len(_GF_SIDE["L"])) / duration)
    gf_right_rate = float(spike_counts[_GF_SIDE["R"]].sum() / max(1, len(_GF_SIDE["R"])) / duration)
    return {
        "state": {"voltage": voltage.round(5).tolist(), "activity": activity.round(5).tolist()},
        "motor": {"DLMn_L_hz": round(left_rate, 3), "DLMn_R_hz": round(right_rate, 3), "GF_L_hz": round(gf_left_rate, 3), "GF_R_hz": round(gf_right_rate, 3), "GF_hz": round(gf_rate, 3)},
        "simulation": _SIMULATION_DESCRIPTION,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

@app.get("/")
def index():
    return jsonify({"service": "Acchiappa la Mosca", "ok": True, "endpoints": ["/health", "/fly-position", "/brain-step"]})

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "legacy_position_model": _GRAPH["dataset"],
        "escape_circuit": _SIMULATION_DESCRIPTION,
        "utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })

@app.post("/brain-step")
def brain_step():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "expected a JSON object"}), 400
    try:
        return jsonify({"ok": True, **_brain_step(payload)})
    except (TypeError, ValueError, OverflowError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

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
