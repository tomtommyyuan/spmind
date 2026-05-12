description = [
    {
        "name": "cluster_cells",
        "description": "Perform unsupervised clustering on single-cell quantification data using scimap. This function takes the CSV output from mcquant (quantify_cells) and performs clustering to identify distinct cell populations. Supports K-means, Leiden (community detection), and Phenograph clustering algorithms. Generates cluster assignments, UMAP visualizations, and cluster statistics for downstream analysis.",
        "required_parameters": [
            {
                "name": "csv_path",
                "type": "str",
                "default": None,
                "description": "Path to the CSV file containing single-cell quantification data from mcquant. Must contain marker intensity columns, spatial coordinates (centroidX, centroidY), and other morphological features. This is typically the output from the quantify_cells function."
            }
        ],
        "optional_parameters": [
            {
                "name": "method",
                "type": "str",
                "default": "leiden",
                "description": "Clustering algorithm to use. Options: 'leiden' (community detection, recommended for most cases), 'kmeans' (requires specifying k clusters), or 'phenograph' (graph-based clustering). Leiden is generally recommended as it automatically determines optimal cluster granularity."
            },
            {
                "name": "k",
                "type": "int",
                "default": 10,
                "description": "Number of clusters for K-means clustering. Only used when method='kmeans'. Choose based on expected cell type diversity."
            },
            {
                "name": "resolution",
                "type": "float",
                "default": 1.0,
                "description": "Resolution parameter for Leiden clustering. Higher values (e.g., 2.0) lead to more fine-grained clusters, lower values (e.g., 0.5) lead to fewer, broader clusters. Only used when method='leiden'."
            },
            {
                "name": "nearest_neighbors",
                "type": "int",
                "default": 30,
                "description": "Number of nearest neighbors for graph construction in Leiden and Phenograph clustering. Higher values (e.g., 50) create more connected graphs and may merge similar clusters, lower values (e.g., 15) preserve finer distinctions."
            },
            {
                "name": "use_markers",
                "type": "List[str]",
                "default": None,
                "description": "List of specific marker names to use for clustering. If None, all markers in the CSV will be used (excluding spatial and morphological features). Example: ['CD3', 'CD8', 'CD20', 'CD4', 'CD68']. Use this to focus clustering on functionally relevant markers."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": "./clustering",
                "description": "Directory to save output files including clustered CSV, UMAP plots, cluster statistics, and AnnData object."
            },
            {
                "name": "output_prefix",
                "type": "str",
                "default": "clustered",
                "description": "Prefix for output files. Output files will be named as: {prefix}_cells.csv, {prefix}_cluster_stats.csv, {prefix}_cluster_markers.csv, {prefix}_umap.png, {prefix}_adata.h5ad"
            },
            {
                "name": "random_state",
                "type": "int",
                "default": 0,
                "description": "Random seed for reproducibility. Use the same value to get consistent results across runs."
            }
        ]
    },
    {
        "name": "phenotype_cells_supervised",
        "description": "Annotate cells with phenotypes using a supervised gating strategy (similar to manual gating in flow cytometry). This function takes single-cell data and a phenotype workflow defining marker combinations for each cell type, then assigns phenotypes based on marker expression patterns. Use this when you know which markers define specific cell types (e.g., CD3+CD4+ for T helper cells). For unsupervised discovery of cell populations, use cluster_cells instead.",
        "required_parameters": [
            {
                "name": "csv_path",
                "type": "str",
                "default": None,
                "description": "Path to the CSV file containing single-cell quantification data from mcquant."
            },
            {
                "name": "phenotype_workflow",
                "type": "Union[str, pd.DataFrame]",
                "default": None,
                "description": "Either a path to a CSV file containing the phenotyping workflow or a pandas DataFrame. The workflow defines gating strategies for each phenotype using columns: 'phenotype' (cell type name), 'marker' (marker name), 'gate_strategy' (allpos/allneg/anypos/anyneg/pos/neg). Example: to define T cells as CD3+ cells, use phenotype='T cells', marker='CD3', gate_strategy='pos'. See scimap documentation for detailed format and examples."
            }
        ],
        "optional_parameters": [
            {
                "name": "gate",
                "type": "float",
                "default": 0.5,
                "description": "Threshold value for determining positive cells on scaled data (0-1 range). Values above this threshold are considered marker-positive. Default of 0.5 means cells with above-median expression are considered positive."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": "./phenotyping",
                "description": "Directory to save output files including phenotyped CSV, statistics, and AnnData object."
            },
            {
                "name": "output_prefix",
                "type": "str",
                "default": "phenotyped",
                "description": "Prefix for output files. Output files will be named as: {prefix}_cells.csv, {prefix}_phenotype_stats.csv, {prefix}_adata.h5ad"
            }
        ]
    }
]