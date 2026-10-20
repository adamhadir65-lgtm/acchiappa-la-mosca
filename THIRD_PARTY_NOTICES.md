# Third-party data notice

`connectome_weights.json` is derived from the BANC v888 v3 neuron-to-neuron edge list and BANC v888 neuron metadata.

## Attribution

Bates, A. S., Phelps, J. S., Kim, M., Yang, H. H. J., Matsliah, A., Ajabi, Z., Perlman, E., et al. (2026). “Distributed control circuits across a brain-and-cord connectome.” *Nature*. https://doi.org/10.1038/s41586-026-10735-w

Dataset: “BANC v888 — Brain-and-nerve-cord connectome (data and analysis code).” Harvard Dataverse. https://doi.org/10.7910/DVN/7WTH1N

## License

The BANC project identifies the data deposit as **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Keep the attribution above with copies and adaptations of the derived population graph. See the [BANC project license statement](https://github.com/htem/BANC-project#license) and [official FlyWire/BANC publication](https://www.nature.com/articles/s41586-026-10735-w).

## What this project derives

The source data contain 13,620,865 directed neuron-to-neuron pairs for the v3 edge list. The preparation script maps pairs whose neurons have one of the three annotated flow labels (`afferent`, `intrinsic`, `efferent`) and groups them by left/right/midline side. It sums the source `count` field into a 9×9 population matrix. In the generated release used here, 12,399,147 pairs map into those populations; unannotated nodes are omitted. These are structural connection counts, not measured neural activity.

## Escape circuit data

`escape_circuit.json` contains an extracted subgraph of the adult male *Drosophila melanogaster* central nervous system connectome, MaleCNS v1.0: 327 neurons and 20,684 directed synaptic connections involving LC4, LPLC2, DNp01/GF, TTMn, PSI, and DLMn cells. The data are from the Janelia/FlyEM MaleCNS release and are distributed under CC BY 4.0. Cite Berg et al., “Sexual dimorphism in the complete Drosophila male central nervous system connectome,” *Cell* (2026), DOI: https://doi.org/10.1016/j.cell.2026.08.015, and the [MaleCNS download page](https://male-cns.janelia.org/download/).

The application code implements its own small leaky-integrate-and-fire (LIF) approximation over that graph. The sensory currents and mapping from bilateral GF spikes to Roblox movement are simplified engineering assumptions. This is a connectome-based subcircuit simulation, not a complete brain, a biophysical replica, or evidence of consciousness.
