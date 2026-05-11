# Background Subtraction

Remove tissue autofluorescence via pixel-by-pixel channel subtraction.

## Function
```python
from spmind.tool.background_subtraction import subtract_background
```

## Fallback

If the wrapper fails (empty task list, container errors), implement background subtraction manually using `tifffile` and `numpy`. For each channel with a background assignment, subtract the corresponding background channel pixel-by-pixel, scaled by exposure times.

## Markers File

The `background` column in markers.csv must map each channel to its background channel name (e.g., `A488_background` for FITC channels). If the column is empty, populate it by matching Filter types to background channels.

## Output
Background-subtracted OME-TIFF and updated markers CSV.
