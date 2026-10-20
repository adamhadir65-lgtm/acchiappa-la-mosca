# Third-party data notice

`connectome_weights.json` is derived from the BANC v888 v3 neuron-to-neuron edge list and BANC v888 neuron metadata.

## Attribution

Bates, A. S., Phelps, J. S., Kim, M., Yang, H. H. J., Matsliah, A., Ajabi, Z., Perlman, E., et al. (2026). “Distributed control circuits across a brain-and-cord connectome.” *Nature*. https://doi.org/10.1038/s41586-026-10735-w

Dataset: “BANC v888 — Brain-and-nerve-cord connectome (data and analysis code).” Harvard Dataverse. https://doi.org/10.7910/DVN/7WTH1N

## License

The BANC project identifies the data deposit as **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Keep the attribution above with copies and adaptations of the derived population graph. See the [BANC project license statement](https://github.com/htem/BANC-project#license) and [official FlyWire/BANC publication](https://www.nature.com/articles/s41586-026-10735-w).

## What this project derives

The source data contain 13,620,865 directed neuron-to-neuron pairs for the v3 edge list. The preparation script maps pairs whose neurons have one of the three annotated flow labels (`afferent`, `intrinsic`, `efferent`) and groups them by left/right/midline side. It sums the source `count` field into a 9×9 population matrix. In the generated release used here, 12,399,147 pairs map into those populations; unannotated nodes are omitted. These are structural connection counts, not measured neural activity.
