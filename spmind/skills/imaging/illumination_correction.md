# Illumination Correction Skill

## Function Signature

```python
from spmind.tool.basic_illumination import generate_illumination_profiles

result = generate_illumination_profiles(
    input_dir='/path/to/raw_tiles/',
    output_dir='/path/to/output/',
    pattern='*.tif'
)
```

## Output
- `*-ffp.tif` - Flat-field profile
- `*-dfp.tif` - Dark-field profile

Use these profiles in ASHLAR stitching step.
