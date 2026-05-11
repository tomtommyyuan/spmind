# Image Stitching Skill

## Function Signature

```python
from spmind.tool.imaging import stitch_and_register_tiles_ashlar

result = stitch_and_register_tiles_ashlar(
    input_dir='/path/to/tiles/',
    output_path='/path/to/output/stitched.ome.tif',
    ffp_path='/path/to/illumination/*-ffp.tif',
    dfp_path='/path/to/illumination/*-dfp.tif'
)
```

## Cyclic Alignment

```python
from spmind.tool.imaging import align_cyclic_images_ashlar

result = align_cyclic_images_ashlar(
    input_images=['/path/to/cycle1.ome.tif', '/path/to/cycle2.ome.tif'],
    output_path='/path/to/aligned.ome.tif',
    reference_channel=0
)
```

Run illumination correction first before stitching.
