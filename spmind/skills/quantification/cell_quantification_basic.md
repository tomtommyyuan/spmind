# Cell Quantification

Extract single-cell marker intensities from multiplexed images.

## Workflow
If only an image is provided, run segmentation first (probability maps → segmentation), then quantify.

## MANDATORY: Scaling Factor Calculation

**YOU MUST calculate the scaling factor before generating probability maps. Do NOT use a default value.**

Steps:
1. Load the DAPI/nuclear channel from the image
2. Threshold and detect nuclei
3. Measure average nuclear diameter in pixels
4. Calculate: `scaling_factor = 12.0 / average_diameter`
5. Use this calculated value in `generate_probability_maps(scaling_factor=...)`

**Never hardcode scaling_factor=1.0. Always calculate it from the image.**

## Functions
```python
from spmind.tool.segmentation_unmicst import generate_probability_maps
from spmind.tool.segmentation_s3segmenter import segment_cells
from spmind.tool.quantification import quantify_cells
```

## Output
Generates a CSV with per-cell marker intensities.

