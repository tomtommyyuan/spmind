# Cell Clustering Skill

## Function Signature

```python
from spmind.tool.clustering import cluster_cells

result = cluster_cells(
    input_csv='/path/to/quantification.csv',
    output_dir='/path/to/output/',
    method='phenograph',  # or 'leiden', 'louvain'
    n_neighbors=30
)
```

## Workflow
1. Load quantification CSV
2. Identify marker columns (exclude metadata like CellID, centroid, Area)
3. Standardize data with `StandardScaler`
4. Apply clustering (phenograph or sklearn)
5. Save CSV with new `cluster` column
