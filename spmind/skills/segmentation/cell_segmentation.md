# Cell Segmentation Skill

## Two-Step Process

### Step 1: Probability Maps (UnMICST)
```python
from spmind.tool.segmentation_unmicst import generate_probability_maps

result = generate_probability_maps(
    input_image='/path/to/image.ome.tif',
    output_dir='/path/to/output/',
    channel=0  # Nuclear channel (0-indexed)
)
```

### Step 2: Segment Cells (S3Segmenter)
```python
from spmind.tool.segmentation_s3segmenter import segment_cells

result = segment_cells(
    input_image='/path/to/image.ome.tif',
    probability_map='/path/to/output/*_Probabilities.tif',
    output_dir='/path/to/segmentation/',
    nucleus_channel=0
)
```

## Output
- `cell.ome.tif` - Cell segmentation mask
- `nuclei.ome.tif` - Nuclei segmentation mask
