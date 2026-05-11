# Cell Quantification Skill

## Prerequisites
Quantification requires THREE inputs:
1. **Image** (OME-TIFF with marker channels)
2. **Segmentation mask** (cell labels)
3. **Channel/marker names** (optional but recommended)

**If only an image is provided**, you MUST run segmentation first:
1. Generate probability maps with high sensitivity
2. Segment cells with **WHOLE-CELL segmentation**
3. Then quantify using the generated `cell.ome.tif` mask

## Step 1: Generate Probability Maps

```python
from spmind.tool.segmentation_unmicst import generate_probability_maps

result = generate_probability_maps(
    input_image='/path/to/image.ome.tif',
    output_dir='/path/to/probability_maps/',
    channel=0,  # DAPI/Hoechst channel (0-indexed)
    model='unmicst-solo',
    scaling_factor=1.0  # IMPORTANT: Override default to 1.0 for standard quantification
)
```

## Step 2: Whole-Cell Segmentation (CRITICAL)

**ALWAYS use whole-cell segmentation** to capture membrane markers:

```python
from spmind.tool.segmentation_s3segmenter import segment_cells

result = segment_cells(
    input_image='/path/to/image.ome.tif',
    probability_maps_dir='/path/to/probability_maps/',
    output_dir='/path/to/segmentation/',
    
    # WHOLE-CELL SEGMENTATION - captures membrane/cytoplasm markers
    segment_cytoplasm=True,
    cytoplasm_channels=[2],  # Use a membrane marker channel (CD45, CD44, Na-K-ATPase)
    cyto_method='distanceTransform',
    cyto_dilation=5,
    
    # Use default nuclei parameters - they are already optimized
    # Do NOT modify log_sigma or nuclei_filter unless you know they work
)
```

**Why whole-cell?** Most immune markers (CD45, CD3, CD20, CD68) are on cell membranes, not nuclei. Nuclei-only segmentation misses ~50-70% of the signal.

**IMPORTANT**: If S3segmenter fails, DO NOT write custom Python segmentation code. Instead:
1. Check the error message carefully
2. Try with default parameters (remove log_sigma, nuclei_filter)
3. Report the error - do not fall back to simple watershed

## Step 3: Quantification

```python
from spmind.tool.quantification import quantify_cells

result = quantify_cells(
    image_path='/path/to/image.ome.tif',
    mask_paths=['/path/to/segmentation/cell.ome.tif'],  # Use cell mask, not nuclei
    channel_names=['DAPI', 'CD45', 'CD3', ...],  # Must match image channels
    output_dir='/path/to/output/'
)
```

## Critical Checks
- **Image and mask must have matching spatial dimensions**
- **Number of channel_names must equal number of image channels**
- **Use `cell.ome.tif` mask (whole-cell), not `nuclei.ome.tif`**
- **NEVER write custom segmentation code** - always use the SP-Mind tools
- Check dimensions first: `tifffile.imread(path).shape`

## Output
- `*_cell.csv` - Per-cell quantification with CellID, marker intensities, spatial coordinates, morphology
