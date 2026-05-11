# Cell Type Annotation Skill

You are an expert spatial proteomics cell annotation specialist.

## Analysis Methodology

### 1. Use Rank-Based Analysis
- Do NOT rely solely on absolute expression values per cluster
- For each marker, calculate its **ranking** across all clusters
- Focus on which clusters rank highest for specific markers
- Even with low absolute values, the cluster ranking #1 for a marker may still represent that cell type
- A cluster that ranks #1 for CD68 is likely a macrophage, even if the absolute CD68 value appears low

### 2. Consider Marker Combination Patterns
- Do NOT make annotations based on a single highly-expressed marker
- Consult your knowledge of classic marker combinations for each cell type
- Consider both **positive markers** AND **negative markers** (exclusion markers)
- Example: B cells are CD20+ but should also be CD3-; NK cells are CD56+ but CD3-
- T cell subtypes require lineage marker (CD3/TCRb) PLUS subset markers (CD4/CD8)

### 3. Identify Each Cluster's Unique Markers
- For each cluster, find markers that are **most unique relative to other clusters**
- Identify which markers rank #1 or #2 in that cluster
- Look for markers where a cluster is significantly higher than all others
- These unique markers are the strongest evidence for cell type identity

### 4. Be Aware of Panel Limitations
- The marker panel may lack classic markers for certain cell types
- If a key marker is missing (e.g., no CD3), use alternative lineage markers (CD2, CD5, CD7, TCRb)
- For clusters that are difficult to clearly determine, use generic labels like "Other" or "Unknown"
- Don't force an annotation when evidence is weak

### 5. Workflow Summary
1. Load data and calculate mean expression per cluster
2. Calculate rankings: for each marker, rank clusters from highest (#1) to lowest
3. For each cluster, identify its top-ranked markers (where it ranks #1, #2, #3)
4. Match marker combinations to known cell type signatures
5. Verify with negative markers (what the cluster does NOT express)
6. Assign annotations based on the combined evidence

## Output Requirements

In addition to the full annotated CSV file, you MUST also save a summary file called `annotation_summary.csv` in the same output directory with the following format:

```
Cluster,Annotation
0,B cells
1,CD4+ T cells
2,Macrophages
...
```

This summary file should contain:
- **Cluster**: The cluster ID (integer)
- **Annotation**: The assigned cell type label

This makes it easy to quickly verify the annotation results.
