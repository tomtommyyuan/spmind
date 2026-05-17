"""
Unsupervised clustering tools using scimap for spatial single-cell analysis.

This module provides wrapper functions for scimap clustering methods, enabling 
unsupervised clustering of single-cell data following the mcmicro quantification step.
Scimap is a powerful toolkit for integrated spatial analysis of multiplexed imaging data.
"""


def cluster_cells(
    csv_path,
    method='leiden',
    k=10,
    resolution=1.0,
    nearest_neighbors=30,
    use_markers=None,
    output_dir="./clustering",
    output_prefix="clustered",
    random_state=0,
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Perform unsupervised clustering on single-cell quantification data.
    
    This function uses scimap to perform unsupervised clustering on single-cell data
    from the quantification step (mcquant output). It supports multiple clustering
    algorithms including K-means, Leiden, and Phenograph.
    
    Parameters
    ----------
    csv_path : str
        Path to the CSV file containing single-cell quantification data from mcquant.
        Must contain columns for cell markers, spatial coordinates (centroidX, centroidY),
        and other morphological features.
    method : str, optional
        Clustering algorithm to use. Options:
        - 'leiden': Community detection algorithm (default, recommended)
        - 'kmeans': K-means clustering (requires specifying k)
        - 'phenograph': Graph-based clustering
        Default: 'leiden'
    k : int, optional
        Number of clusters for K-means clustering. Only used when method='kmeans'.
        Default: 10
    resolution : float, optional
        Resolution parameter for Leiden clustering. Higher values lead to more clusters.
        Only used when method='leiden'. Default: 1.0
    nearest_neighbors : int, optional
        Number of nearest neighbors for graph construction in Leiden and Phenograph.
        Default: 30
    use_markers : list of str, optional
        List of specific marker names to use for clustering. If None, all markers
        in the CSV will be used (excluding spatial and morphological features).
        Example: ['CD3', 'CD8', 'CD20', 'CD4']
        Default: None (use all markers)
    output_dir : str, optional
        Directory to save output files including clustered CSV and analysis plots.
        Default: "./clustering"
    output_prefix : str, optional
        Prefix for output files. Default: "clustered"
    random_state : int, optional
        Random seed for reproducibility. Default: 0
    singularity_image : str, optional
        Path to the scimap Singularity image file.
        If not provided, will look for SCIMAP_SIF environment variable,
        or default to "scimap_latest.sif" in current directory.
        Default: None
        
    Returns
    -------
    str
        Research log summarizing the clustering process, including:
        - Number of cells clustered
        - Number of clusters identified
        - Cluster size distribution
        - Output file locations
        
    Examples
    --------
    >>> # Basic Leiden clustering with default settings
    >>> log = cluster_cells(
    ...     csv_path='quantification/cells.csv',
    ...     output_dir='./clustering'
    ... )
    
    >>> # K-means clustering with specific markers
    >>> log = cluster_cells(
    ...     csv_path='cells.csv',
    ...     method='kmeans',
    ...     k=15,
    ...     use_markers=['CD3', 'CD8', 'CD4', 'CD20', 'CD68'],
    ...     output_dir='./results/clustering'
    ... )
    
    >>> # Phenograph clustering with more neighbors
    >>> log = cluster_cells(
    ...     csv_path='cells.csv',
    ...     method='phenograph',
    ...     nearest_neighbors=50,
    ...     output_dir='./clustering'
    ... )
    
    Notes
    -----
    - The input CSV should be the output from mcquant (quantify_cells function)
    - Clustering is performed on normalized/scaled marker intensities
    - Output includes: clustered CSV, UMAP visualization, cluster statistics
    - This function requires Singularity to be installed
    - The CSV structure should match the mcmicro/mcquant output format
    """
    import os
    import subprocess
    import shlex
    import shutil
    from datetime import datetime
    import tempfile
    
    # Initialize research log
    log = []
    log.append("# Scimap Single-Cell Clustering")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Detect container runtime
    container_type = None
    container_cmd = None
    
    # Detect platform for Docker image selection
    import platform
    machine = platform.machine().lower()
    is_arm64 = machine in ("arm64", "aarch64")
    
    # Use ARM64 image on Apple Silicon / ARM64 platforms
    if is_arm64:
        docker_image = "tomyuanyucheng/scimap:arm64"
        log.append(f"Detected ARM64 platform ({machine}), using ARM-native image")
    else:
        docker_image = "labsyspharm/scimap:latest"
    
    if container_runtime == "auto":
        container_cmd = shutil.which("apptainer") or shutil.which("singularity")
        if container_cmd:
            container_type = "apptainer" if "apptainer" in container_cmd else "singularity"
            log.append(f"Detected container runtime: {container_type} at {container_cmd}")
        else:
            container_cmd = shutil.which("docker")
            if container_cmd:
                container_type = "docker"
                log.append(f"Detected container runtime: docker at {container_cmd}")
    elif container_runtime in ("apptainer", "singularity"):
        container_cmd = shutil.which(container_runtime)
        container_type = container_runtime
    elif container_runtime == "docker":
        container_cmd = shutil.which("docker")
        container_type = "docker"
    
    if not container_cmd:
        log.append(f"✗ Error: No container runtime (apptainer, singularity, or docker) found in PATH.")
        return "\n".join(log)
    
    # For apptainer/singularity, check .sif file exists
    if container_type in ("apptainer", "singularity"):
        if singularity_image is None:
            singularity_image = os.environ.get('SCIMAP_SIF', 'scimap_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/scimap:latest")
            return "\n".join(log)
    else:
        log.append(f"Using Docker image: {docker_image}")
    
    # Validate CSV path
    csv_path_abs = os.path.abspath(csv_path)
    if not os.path.exists(csv_path_abs):
        log.append(f"✗ Error: CSV file not found: {csv_path}")
        return "\n".join(log)
    
    # Create output directory
    output_dir_abs = os.path.abspath(output_dir)
    os.makedirs(output_dir_abs, exist_ok=True)
    
    # Validate method
    valid_methods = ['leiden', 'kmeans', 'phenograph']
    if method not in valid_methods:
        log.append(f"✗ Error: Invalid method '{method}'. Choose from: {', '.join(valid_methods)}")
        return "\n".join(log)
    
    log.append("## Input Parameters")
    log.append(f"- CSV file: {csv_path}")
    log.append(f"- Clustering method: {method}")
    if method == 'kmeans':
        log.append(f"- Number of clusters (k): {k}")
    elif method == 'leiden':
        log.append(f"- Resolution: {resolution}")
    log.append(f"- Nearest neighbors: {nearest_neighbors}")
    if use_markers:
        log.append(f"- Selected markers ({len(use_markers)}): {', '.join(use_markers)}")
    else:
        log.append(f"- Using all available markers")
    log.append(f"- Output directory: {output_dir}")
    log.append(f"- Random state: {random_state}")
    
    # Create a Python script to run inside the container
    # This script will use scimap to perform clustering
    python_script = f'''
import os
import sys
import pandas as pd
import numpy as np
import anndata as ad
import scimap as sm

# Read the CSV file
print("Loading CSV file...")
df = pd.read_csv('{os.path.basename(csv_path_abs)}')
print(f"Loaded {{len(df)}} cells")

# Ensure imageid column exists (required by scimap)
if 'imageid' not in df.columns:
    if 'identifier' in df.columns:
        df['imageid'] = df['identifier']
        print("Created 'imageid' column from 'identifier'")
    else:
        df['imageid'] = 'image_1'
        print("Created default 'imageid' column (all cells assigned to 'image_1')")

# Identify marker columns (exclude spatial and metadata columns)
exclude_cols = ['cellLabel', 'Annotation', 'centroidX', 'centroidY', 'cellSize', 
                'identifier', 'imageid', 'X_centroid', 'Y_centroid', 'Area', 
                'MajorAxisLength', 'MinorAxisLength', 'Eccentricity', 'Solidity', 
                'Extent', 'Orientation']

all_cols = df.columns.tolist()
marker_cols = [col for col in all_cols if col not in exclude_cols]

print(f"Identified {{len(marker_cols)}} marker columns")

# Use specific markers if provided
use_markers = {use_markers}
if use_markers:
    marker_cols = [col for col in marker_cols if col in use_markers]
    print(f"Using {{len(marker_cols)}} selected markers: {{marker_cols}}")
else:
    print(f"Using all {{len(marker_cols)}} markers")

# Create AnnData object
# Set cell index - combine imageid and cellLabel for uniqueness
if 'cellLabel' in df.columns and 'imageid' in df.columns:
    # Combine imageid and cellLabel to ensure unique cell identifiers across images
    df.index = df['imageid'].astype(str) + '_cell_' + df['cellLabel'].astype(str)
elif 'cellLabel' in df.columns:
    # No imageid, append row number to ensure uniqueness
    df.index = 'cell_' + df['cellLabel'].astype(str) + '_' + pd.Series(range(len(df))).astype(str)
else:
    # Fallback: use row numbers
    df.index = 'cell_' + pd.Series(range(len(df))).astype(str)

# Make sure indices are unique (safety check)
if df.index.duplicated().any():
    print(f"Warning: Found {{df.index.duplicated().sum()}} duplicate indices. Making them unique...")
    df.index = df.index.astype(str) + '_' + pd.Series(range(len(df))).astype(str)

# Extract marker expression matrix
X = df[marker_cols].values

# Create AnnData
adata = ad.AnnData(X=X)
# Store metadata in obs, excluding cellLabel to avoid duplication (it's already in the index)
obs_cols = [col for col in exclude_cols if col in df.columns and col != 'cellLabel']
adata.obs = df[obs_cols]
adata.var_names = marker_cols

print(f"Created AnnData object: {{adata.shape[0]}} cells x {{adata.shape[1]}} markers")

# Preprocessing: Normalize and scale the data
# Using scanpy's standard preprocessing instead of scimap's rescale to avoid gate parameter bug
print("Preprocessing data...")
import scanpy as sc

# Log-transform if data is not already log-transformed
# Check if data looks like raw counts (has values > 10)
if adata.X.max() > 10:
    sc.pp.log1p(adata)
    print("Applied log1p transformation")

# Normalize to median total counts
sc.pp.normalize_total(adata, target_sum=1e4)
print("Normalized to median total counts")

# Scale to unit variance and zero mean (important for clustering)
sc.pp.scale(adata, max_value=10)
print("Scaled data to unit variance")

# Perform clustering
print(f"Performing {{'{method}'}} clustering...")
method = '{method}'
if method == 'kmeans':
    adata = sm.tl.cluster(adata, method='kmeans', k={k}, use_raw=False, 
                          random_state={random_state}, label='cluster')
elif method == 'leiden':
    adata = sm.tl.cluster(adata, method='leiden', resolution={resolution}, 
                          nearest_neighbors={nearest_neighbors}, use_raw=False, 
                          random_state={random_state}, label='cluster')
elif method == 'phenograph':
    adata = sm.tl.cluster(adata, method='phenograph', 
                          nearest_neighbors={nearest_neighbors}, use_raw=False, 
                          random_state={random_state}, label='cluster')

print(f"Clustering complete!")

# Get cluster assignments
clusters = adata.obs['cluster'].values
print(f"Number of clusters identified: {{len(np.unique(clusters))}}")
print(f"Cluster distribution:")
cluster_counts = pd.Series(clusters).value_counts().sort_index()
for cluster_id, count in cluster_counts.items():
    print(f"  Cluster {{cluster_id}}: {{count}} cells ({{100*count/len(clusters):.2f}}%)")

# Add cluster labels to original dataframe
df['cluster'] = clusters

# Save clustered CSV
output_csv = '{output_prefix}_cells.csv'
df.to_csv(output_csv, index=False)
print(f"Saved clustered data to {{output_csv}}")

# Generate UMAP for visualization using our own implementation
print("Generating UMAP visualization...")
try:
    # Compute PCA for UMAP (if not already present)
    if 'X_pca' not in adata.obsm:
        print("Computing PCA for UMAP...")
        n_comps = min(50, min(adata.shape) - 1)
        sc.tl.pca(adata, n_comps=n_comps)
        print(f"Computed {{n_comps}} principal components")
    
    # Use scanpy's UMAP implementation (more reliable than scimap's)
    print("Running UMAP calculation...")
    sc.pp.neighbors(adata, n_neighbors=15, n_pcs=min(30, adata.obsm['X_pca'].shape[1]), 
                    random_state={random_state})
    sc.tl.umap(adata, random_state={random_state})
    print("UMAP calculation complete")
    
    # Verify UMAP coordinates exist
    if 'X_umap' not in adata.obsm:
        print("Warning: UMAP coordinates not generated. Skipping UMAP plot.")
    else:
        print(f"UMAP coordinates generated: {{adata.obsm['X_umap'].shape}}")
        
        # Save UMAP plot using matplotlib directly
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        
        # Create scatter plot of UMAP colored by cluster
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Get UMAP coordinates
        umap_coords = adata.obsm['X_umap']
        
        # Plot each cluster with a different color
        cluster_ids = adata.obs['cluster'].unique()
        colors = plt.cm.tab20(np.linspace(0, 1, len(cluster_ids)))
        
        for i, cluster in enumerate(sorted(cluster_ids, key=str)):
            mask = adata.obs['cluster'] == cluster
            ax.scatter(umap_coords[mask, 0], umap_coords[mask, 1], 
                      c=[colors[i]], label=f'Cluster {{cluster}}', 
                      s=5, alpha=0.7)
        
        ax.set_xlabel('UMAP 1')
        ax.set_ylabel('UMAP 2')
        ax.set_title('UMAP Colored by Cluster')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', markerscale=3)
        plt.tight_layout()
        plt.savefig('{output_prefix}_umap.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved UMAP plot to {output_prefix}_umap.png")
except Exception as e:
    print(f"Warning: Could not generate UMAP plot: {{str(e)}}")
    import traceback
    print(f"Error details: {{traceback.format_exc()}}")

# Save cluster statistics
stats_df = pd.DataFrame({{
    'cluster': cluster_counts.index,
    'cell_count': cluster_counts.values,
    'percentage': 100 * cluster_counts.values / len(clusters)
}})
stats_df.to_csv('{output_prefix}_cluster_stats.csv', index=False)
print(f"Saved cluster statistics to {output_prefix}_cluster_stats.csv")

# Calculate mean marker expression per cluster
print("Calculating mean marker expression per cluster...")
cluster_means = df.groupby('cluster')[marker_cols].mean()
cluster_means.to_csv('{output_prefix}_cluster_markers.csv')
print(f"Saved cluster marker expression to {output_prefix}_cluster_markers.csv")

# Save the AnnData object for further analysis
# Note: The h5ad file is cleaned up by the host before running this script
h5ad_file = '{output_prefix}_adata.h5ad'
try:
    # Force overwrite mode and use compression
    adata.write(h5ad_file, compression='gzip')
    print(f"Saved AnnData object to {{h5ad_file}}")
except Exception as e:
    print(f"Warning: Could not save AnnData object: {{str(e)}}")
    print("CSV files contain all necessary data for analysis.")

print("Clustering analysis complete!")
'''
    
    # Save Python script to temp file
    script_file = os.path.join(output_dir_abs, 'cluster_script.py')
    with open(script_file, 'w') as f:
        f.write(python_script)
    
    # Determine directories to mount
    csv_dir = os.path.dirname(csv_path_abs)
    
    # Find common parent directory
    if csv_dir == output_dir_abs:
        mount_dir = csv_dir
    else:
        mount_dir = os.path.commonpath([csv_dir, output_dir_abs])
    
    # Calculate relative paths for container
    csv_rel = os.path.relpath(csv_path_abs, mount_dir)
    output_rel = os.path.relpath(output_dir_abs, mount_dir)
    script_rel = os.path.relpath(script_file, mount_dir)
    
    # Build the container command
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{mount_dir}:/data",
            "-w", f"/data/{output_rel}",
            docker_image,
            "python", f"/data/{script_rel}"
        ]
    else:  # apptainer or singularity
        cmd = [
            container_cmd, "exec",
            "--bind", f"{mount_dir}:/data",
            "--pwd", f"/data/{output_rel}",
            singularity_image,
            "python", f"/data/{script_rel}"
        ]
    
    # Clean up any existing h5ad file to avoid "name already exists" error
    h5ad_path = os.path.join(output_dir_abs, f"{output_prefix}_adata.h5ad")
    if os.path.exists(h5ad_path):
        try:
            os.remove(h5ad_path)
            log.append(f"Removed existing h5ad file: {output_prefix}_adata.h5ad")
        except Exception as e:
            log.append(f"Warning: Could not remove existing h5ad file: {e}")
    
    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}\n")
    
    # Run clustering
    try:
        log.append("Running scimap clustering...")
        log.append(f"This may take several minutes depending on dataset size...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=mount_dir
        )
        
        log.append("✓ Clustering completed successfully\n")
        
        # Log stdout (contains progress info)
        if result.stdout:
            log.append("## Scimap Output")
            stdout_lines = result.stdout.strip().split('\n')
            for line in stdout_lines:
                log.append(line)
        
        # Find output files
        import glob
        output_csv = glob.glob(os.path.join(output_dir_abs, f"{output_prefix}_cells.csv"))
        output_stats = glob.glob(os.path.join(output_dir_abs, f"{output_prefix}_cluster_stats.csv"))
        output_markers = glob.glob(os.path.join(output_dir_abs, f"{output_prefix}_cluster_markers.csv"))
        output_umap = glob.glob(os.path.join(output_dir_abs, f"{output_prefix}_umap.png"))
        output_h5ad = glob.glob(os.path.join(output_dir_abs, f"{output_prefix}_adata.h5ad"))
        
        if output_csv or output_stats:
            log.append("\n## Results")
            
            if output_csv:
                csv_size = os.path.getsize(output_csv[0]) / 1024
                log.append(f"✓ Clustered cells CSV: {os.path.basename(output_csv[0])} ({csv_size:.2f} KB)")
                
                # Read and analyze results
                try:
                    import pandas as pd
                    df = pd.read_csv(output_csv[0])
                    n_cells = len(df)
                    n_clusters = df['cluster'].nunique()
                    log.append(f"  - Total cells: {n_cells}")
                    log.append(f"  - Number of clusters: {n_clusters}")
                except Exception as e:
                    log.append(f"  (Could not parse results: {e})")
            
            if output_stats:
                log.append(f"✓ Cluster statistics: {os.path.basename(output_stats[0])}")
            
            if output_markers:
                log.append(f"✓ Cluster marker profiles: {os.path.basename(output_markers[0])}")
            
            if output_umap:
                log.append(f"✓ UMAP visualization: {os.path.basename(output_umap[0])}")
            
            if output_h5ad:
                h5ad_size = os.path.getsize(output_h5ad[0]) / 1024
                log.append(f"✓ AnnData object: {os.path.basename(output_h5ad[0])} ({h5ad_size:.2f} KB)")
        else:
            log.append("\n⚠ Warning: No output files found")
        
    except subprocess.CalledProcessError as e:
        log.append(f"\n✗ Error: Clustering failed with exit code {e.returncode}")
        if e.stdout:
            log.append(f"\nStdout:\n{e.stdout}")
        if e.stderr:
            log.append(f"\nStderr:\n{e.stderr}")
        return "\n".join(log)
    
    except FileNotFoundError:
        log.append(f"\n✗ Error: 'singularity' command not found. Please ensure Singularity is installed and in your PATH.")
        return "\n".join(log)
    
    except Exception as e:
        log.append(f"\n✗ Error: {str(e)}")
        import traceback
        log.append(traceback.format_exc())
        return "\n".join(log)
    
    finally:
        # Clean up script file
        try:
            if os.path.exists(script_file):
                os.remove(script_file)
        except:
            pass
    
    log.append("\n## Conclusion")
    log.append("Unsupervised clustering completed successfully.")
    log.append(f"Output files saved to: {output_dir_abs}")
    log.append("\nThe output can be used for:")
    log.append("  - Cell type identification and annotation")
    log.append("  - Spatial analysis of cluster distributions")
    log.append("  - Differential expression analysis between clusters")
    log.append("  - Neighborhood analysis and cell-cell interactions")
    log.append("  - Further downstream analysis with scimap or other tools")
    
    return "\n".join(log)


def phenotype_cells_supervised(
    csv_path,
    phenotype_workflow,
    gate=0.5,
    output_dir="./phenotyping",
    output_prefix="phenotyped",
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Annotate cells with phenotypes using supervised gating strategy.
    
    This function uses scimap's phenotype_cells to assign cell types based on
    a predefined gating workflow (similar to manual gating in flow cytometry).
    This is useful when you know which markers define specific cell types.
    
    Parameters
    ----------
    csv_path : str
        Path to the CSV file containing single-cell quantification data.
    phenotype_workflow : str or pd.DataFrame
        Either a path to a CSV file containing the phenotyping workflow or
        a pandas DataFrame. The workflow defines gating strategies for each
        phenotype. See scimap documentation for format details.
        Example columns: phenotype, marker, gate_strategy (allpos/allneg/anypos/anyneg/pos/neg)
    gate : float, optional
        Threshold value for determining positive cells (on scaled data 0-1).
        Values above this threshold are considered positive. Default: 0.5
    output_dir : str, optional
        Directory to save output files. Default: "./phenotyping"
    output_prefix : str, optional
        Prefix for output files. Default: "phenotyped"
    singularity_image : str, optional
        Path to the scimap Singularity image. Default: None
        
    Returns
    -------
    str
        Research log summarizing the phenotyping process
        
    Examples
    --------
    >>> # Phenotype cells using a workflow CSV
    >>> log = phenotype_cells_supervised(
    ...     csv_path='cells.csv',
    ...     phenotype_workflow='phenotype_workflow.csv',
    ...     gate=0.5,
    ...     output_dir='./phenotyping'
    ... )
    
    Notes
    -----
    - The phenotype workflow should define marker combinations for each cell type
    - This is supervised classification based on known marker patterns
    - For unsupervised discovery, use cluster_cells instead
    """
    import os
    import subprocess
    import shlex
    import shutil
    from datetime import datetime
    
    log = []
    log.append("# Scimap Supervised Cell Phenotyping")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Detect container runtime
    container_type = None
    container_cmd = None
    
    # Detect platform for Docker image selection
    import platform
    machine = platform.machine().lower()
    is_arm64 = machine in ("arm64", "aarch64")
    
    # Use ARM64 image on Apple Silicon / ARM64 platforms
    if is_arm64:
        docker_image = "tomyuanyucheng/scimap:arm64"
        log.append(f"Detected ARM64 platform ({machine}), using ARM-native image")
    else:
        docker_image = "labsyspharm/scimap:latest"
    
    if container_runtime == "auto":
        container_cmd = shutil.which("apptainer") or shutil.which("singularity")
        if container_cmd:
            container_type = "apptainer" if "apptainer" in container_cmd else "singularity"
            log.append(f"Detected container runtime: {container_type} at {container_cmd}")
        else:
            container_cmd = shutil.which("docker")
            if container_cmd:
                container_type = "docker"
                log.append(f"Detected container runtime: docker at {container_cmd}")
    elif container_runtime in ("apptainer", "singularity"):
        container_cmd = shutil.which(container_runtime)
        container_type = container_runtime
    elif container_runtime == "docker":
        container_cmd = shutil.which("docker")
        container_type = "docker"
    
    if not container_cmd:
        log.append(f"✗ Error: No container runtime (apptainer, singularity, or docker) found in PATH.")
        return "\n".join(log)
    
    # For apptainer/singularity, check .sif file exists
    if container_type in ("apptainer", "singularity"):
        if singularity_image is None:
            singularity_image = os.environ.get('SCIMAP_SIF', 'scimap_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/scimap:latest")
            return "\n".join(log)
    else:
        log.append(f"Using Docker image: {docker_image}")
    
    csv_path_abs = os.path.abspath(csv_path)
    if not os.path.exists(csv_path_abs):
        log.append(f"✗ Error: CSV file not found: {csv_path}")
        return "\n".join(log)
    
    # Handle phenotype workflow
    if isinstance(phenotype_workflow, str):
        workflow_path_abs = os.path.abspath(phenotype_workflow)
        if not os.path.exists(workflow_path_abs):
            log.append(f"✗ Error: Phenotype workflow file not found: {phenotype_workflow}")
            return "\n".join(log)
    else:
        # Save DataFrame to temp file
        output_dir_abs = os.path.abspath(output_dir)
        os.makedirs(output_dir_abs, exist_ok=True)
        workflow_path_abs = os.path.join(output_dir_abs, 'temp_workflow.csv')
        phenotype_workflow.to_csv(workflow_path_abs, index=False)
    
    output_dir_abs = os.path.abspath(output_dir)
    os.makedirs(output_dir_abs, exist_ok=True)
    
    log.append("## Input Parameters")
    log.append(f"- CSV file: {csv_path}")
    log.append(f"- Phenotype workflow: {phenotype_workflow if isinstance(phenotype_workflow, str) else 'DataFrame'}")
    log.append(f"- Gate threshold: {gate}")
    log.append(f"- Output directory: {output_dir}")
    
    # Create Python script for phenotyping
    python_script = f'''
import os
import pandas as pd
import anndata as ad
import scimap as sm

# Read CSV and workflow
print("Loading data...")
df = pd.read_csv('{os.path.basename(csv_path_abs)}')
phenotype_workflow = pd.read_csv('{os.path.basename(workflow_path_abs)}')

print(f"Loaded {{len(df)}} cells")
print(f"Loaded phenotype workflow with {{len(phenotype_workflow)}} rules")

# Ensure imageid column exists (required by scimap)
if 'imageid' not in df.columns:
    if 'identifier' in df.columns:
        df['imageid'] = df['identifier']
        print("Created 'imageid' column from 'identifier'")
    else:
        df['imageid'] = 'image_1'
        print("Created default 'imageid' column")

# Identify markers
exclude_cols = ['cellLabel', 'Annotation', 'centroidX', 'centroidY', 'cellSize', 
                'identifier', 'imageid', 'X_centroid', 'Y_centroid', 'Area', 
                'MajorAxisLength', 'MinorAxisLength', 'Eccentricity', 'Solidity', 
                'Extent', 'Orientation']
marker_cols = [col for col in df.columns if col not in exclude_cols]

# Create AnnData
# Set cell index - combine imageid and cellLabel for uniqueness
if 'cellLabel' in df.columns and 'imageid' in df.columns:
    # Combine imageid and cellLabel to ensure unique cell identifiers across images
    df.index = df['imageid'].astype(str) + '_cell_' + df['cellLabel'].astype(str)
elif 'cellLabel' in df.columns:
    # No imageid, append row number to ensure uniqueness
    df.index = 'cell_' + df['cellLabel'].astype(str) + '_' + pd.Series(range(len(df))).astype(str)
else:
    # Fallback: use row numbers
    df.index = 'cell_' + pd.Series(range(len(df))).astype(str)

# Make sure indices are unique (safety check)
if df.index.duplicated().any():
    print(f"Warning: Found {{df.index.duplicated().sum()}} duplicate indices. Making them unique...")
    df.index = df.index.astype(str) + '_' + pd.Series(range(len(df))).astype(str)

X = df[marker_cols].values
adata = ad.AnnData(X=X)
# Store metadata in obs, excluding cellLabel to avoid duplication (it's already in the index)
obs_cols = [col for col in exclude_cols if col in df.columns and col != 'cellLabel']
adata.obs = df[obs_cols]
adata.var_names = marker_cols

# Preprocessing: Normalize and scale the data
# Using scanpy instead of scimap's rescale to avoid gate parameter bug
print("Preprocessing data...")
import scanpy as sc

# Log-transform if needed
if adata.X.max() > 10:
    sc.pp.log1p(adata)
    print("Applied log1p transformation")

# Normalize
sc.pp.normalize_total(adata, target_sum=1e4)
print("Normalized data")

# Scale to 0-1 range for phenotyping (gate threshold interpretation)
# Store original scaled data for phenotyping
from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
adata.X = scaler.fit_transform(adata.X)
print("Scaled data to 0-1 range for phenotyping")

# Phenotype cells
print("Assigning phenotypes...")
adata = sm.tl.phenotype_cells(adata, phenotype=phenotype_workflow, 
                               gate={gate}, label='phenotype')

# Add phenotypes to dataframe
df['phenotype'] = adata.obs['phenotype'].values

# Save results
output_csv = '{output_prefix}_cells.csv'
df.to_csv(output_csv, index=False)
print(f"Saved phenotyped data to {{output_csv}}")

# Save phenotype statistics
pheno_counts = df['phenotype'].value_counts()
print(f"\\nPhenotype distribution:")
for pheno, count in pheno_counts.items():
    print(f"  {{pheno}}: {{count}} cells ({{100*count/len(df):.2f}}%)")

stats_df = pd.DataFrame({{
    'phenotype': pheno_counts.index,
    'cell_count': pheno_counts.values,
    'percentage': 100 * pheno_counts.values / len(df)
}})
stats_df.to_csv('{output_prefix}_phenotype_stats.csv', index=False)
print(f"Saved phenotype statistics")

# Save AnnData
try:
    adata.write('{output_prefix}_adata.h5ad', compression='gzip')
    print(f"Saved AnnData object to {output_prefix}_adata.h5ad")
except Exception as e:
    print(f"Warning: Could not save AnnData object: {{str(e)}}")
    print("CSV files contain all necessary data for analysis.")

print("Phenotyping complete!")
'''
    
    script_file = os.path.join(output_dir_abs, 'phenotype_script.py')
    with open(script_file, 'w') as f:
        f.write(python_script)
    
    # Setup mount and run
    csv_dir = os.path.dirname(csv_path_abs)
    workflow_dir = os.path.dirname(workflow_path_abs)
    mount_dir = os.path.commonpath([csv_dir, workflow_dir, output_dir_abs])
    
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{mount_dir}:/data",
            "-w", f"/data/{os.path.relpath(output_dir_abs, mount_dir)}",
            docker_image,
            "python", f"/data/{os.path.relpath(script_file, mount_dir)}"
        ]
    else:  # apptainer or singularity
        cmd = [
            container_cmd, "exec",
            "--bind", f"{mount_dir}:/data",
            "--pwd", f"/data/{os.path.relpath(output_dir_abs, mount_dir)}",
            singularity_image,
            "python", f"/data/{os.path.relpath(script_file, mount_dir)}"
        ]
    
    # Clean up any existing h5ad file to avoid "name already exists" error
    h5ad_path = os.path.join(output_dir_abs, f"{output_prefix}_adata.h5ad")
    if os.path.exists(h5ad_path):
        try:
            os.remove(h5ad_path)
            log.append(f"Removed existing h5ad file: {output_prefix}_adata.h5ad")
        except Exception as e:
            log.append(f"Warning: Could not remove existing h5ad file: {e}")
    
    log.append("\n## Processing")
    log.append(f"Command: {shlex.join(cmd)}\n")
    
    try:
        log.append("Running phenotyping...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=mount_dir)
        
        log.append("✓ Phenotyping completed successfully\n")
        
        if result.stdout:
            log.append("## Scimap Output")
            for line in result.stdout.strip().split('\n'):
                log.append(line)
        
        log.append("\n## Results")
        log.append(f"✓ Phenotyped cells saved to: {output_dir_abs}")
        
    except subprocess.CalledProcessError as e:
        log.append(f"\n✗ Error: Phenotyping failed with exit code {e.returncode}")
        if e.stderr:
            log.append(f"\nStderr:\n{e.stderr}")
        return "\n".join(log)
    
    except Exception as e:
        log.append(f"\n✗ Error: {str(e)}")
        return "\n".join(log)
    
    finally:
        try:
            if os.path.exists(script_file):
                os.remove(script_file)
        except:
            pass
    
    log.append("\n## Conclusion")
    log.append("Cell phenotyping completed successfully.")
    log.append("Cells have been annotated with phenotypes based on the gating workflow.")
    
    return "\n".join(log)

