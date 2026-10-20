"""Build a tiny population-level graph from the public BANC v888 connectome.

The 13.6-million-edge source graph is reduced by summing its measured neuron-to-
neuron connection counts between annotated afferent, intrinsic, and efferent
populations. The game service uses this small matrix; it does not load or simulate
188,000 individual neurons at runtime.

Run from this folder with:
    python prepare_connectome.py --data-dir data/banc

The files are fetched from the BANC project's public Google Cloud Storage bucket
when they are not already present. Derived data must retain BANC attribution and
the CC BY 4.0 notice; see THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc


BASE_URL = (
    "https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/"
    "compiled_data/banc_888/"
)
FILES = {
    "banc_888_meta.feather": BASE_URL + "banc_888_meta.feather",
    "banc_888_edgelist_simple_v3.feather": BASE_URL + "banc_888_edgelist_simple_v3.feather",
}
GROUPS = [
    "afferent_left", "afferent_right", "afferent_mid",
    "intrinsic_left", "intrinsic_right", "intrinsic_mid",
    "efferent_left", "efferent_right", "efferent_mid",
]
FLOW_TO_PREFIX = {"afferent": "afferent", "intrinsic": "intrinsic", "efferent": "efferent"}


def download_if_missing(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for filename, url in FILES.items():
        destination = folder / filename
        if destination.exists() and destination.stat().st_size > 0:
            continue
        print(f"Downloading {filename}…", flush=True)
        temporary = destination.with_suffix(destination.suffix + ".partial")
        try:
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_population_graph(data_dir: Path) -> dict:
    metadata_path = data_dir / "banc_888_meta.feather"
    edge_path = data_dir / "banc_888_edgelist_simple_v3.feather"
    metadata = pd.read_feather(
        metadata_path,
        columns=["banc_888_id", "flow", "side"],
    )
    # Feather returns columns in file-schema order, which need not match the
    # requested order. Select them again so the tuple unpacking below is explicit.
    metadata = metadata[["banc_888_id", "flow", "side"]]

    id_to_group: dict[str, int] = {}
    group_neurons = [0] * len(GROUPS)
    for neuron_id, flow, side in metadata.itertuples(index=False, name=None):
        prefix = FLOW_TO_PREFIX.get(flow)
        if prefix is None:
            continue
        side_name = side if side in ("left", "right") else "mid"
        group_index = GROUPS.index(f"{prefix}_{side_name}")
        id_to_group[str(neuron_id)] = group_index
        group_neurons[group_index] += 1

    width = len(GROUPS)
    totals = np.zeros((width, width), dtype=np.float64)
    source_edges = 0
    included_edges = 0
    included_synapses = 0
    reader = ipc.open_file(pa.memory_map(str(edge_path), "r"))
    needed = {"pre", "post", "count"}
    if not needed.issubset(reader.schema.names):
        raise ValueError(f"Unexpected BANC edge-list columns: {reader.schema.names}")

    pre_column = reader.schema.get_field_index("pre")
    post_column = reader.schema.get_field_index("post")
    count_column = reader.schema.get_field_index("count")
    for batch_number in range(reader.num_record_batches):
        batch = reader.get_batch(batch_number)
        source_edges += batch.num_rows
        pre_ids = batch.column(pre_column).to_pylist()
        post_ids = batch.column(post_column).to_pylist()
        counts = batch.column(count_column).to_numpy(zero_copy_only=False)
        pre_groups = np.fromiter(
            (id_to_group.get(str(value), -1) for value in pre_ids),
            dtype=np.int8,
            count=batch.num_rows,
        )
        post_groups = np.fromiter(
            (id_to_group.get(str(value), -1) for value in post_ids),
            dtype=np.int8,
            count=batch.num_rows,
        )
        valid = (pre_groups >= 0) & (post_groups >= 0)
        if not np.any(valid):
            continue
        pair_ids = pre_groups[valid].astype(np.int64) * width + post_groups[valid]
        sums = np.bincount(pair_ids, weights=counts[valid], minlength=width * width)
        totals += sums.reshape((width, width))
        included_edges += int(valid.sum())
        included_synapses += int(counts[valid].sum())

    return {
        "dataset": "BANC v888, edgelist v3 (synapse size threshold >= 10)",
        "license": "CC BY 4.0",
        "attribution": (
            "Bates AS, Phelps JS, Kim M, Yang HHJ, et al. Distributed control circuits "
            "across a brain-and-cord connectome. Nature (2026). DOI: 10.1038/s41586-026-10735-w. "
            "Dataset DOI: 10.7910/DVN/7WTH1N."
        ),
        "groups": GROUPS,
        "group_neuron_counts": group_neurons,
        "source_edge_count": source_edges,
        "included_edge_count": included_edges,
        "excluded_edge_count": source_edges - included_edges,
        "included_synapse_count": included_synapses,
        "edge_count_matrix": totals.astype(np.int64).tolist(),
        "source_sha256": {
            "metadata": sha256_file(metadata_path),
            "edgelist": sha256_file(edge_path),
        },
        "reduction": (
            "Full measured BANC v888 v3 neuron-to-neuron edgelist aggregated into "
            "9 annotated flow-by-side populations. Connection counts are retained; "
            "unannotated cells are excluded. This is a reduced population graph, "
            "not a per-neuron simulation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/banc"))
    parser.add_argument("--output", type=Path, default=Path("connectome_weights.json"))
    args = parser.parse_args()
    download_if_missing(args.data_dir)
    graph = build_population_graph(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(
        f"Saved {args.output}: {graph['included_edge_count']:,} of "
        f"{graph['source_edge_count']:,} source edges mapped into {len(GROUPS)} populations.",
        flush=True,
    )


if __name__ == "__main__":
    main()
