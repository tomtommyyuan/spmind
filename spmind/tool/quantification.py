"""
Single-cell quantification tools using mcquant.

This module provides wrapper functions for mcquant, a tool for single-cell data 
extraction given segmentation masks and multi-channel images. The output CSV 
structure is aligned with histoCAT format.
"""


def quantify_cells(
    image_path,
    mask_paths,
    channel_names,
    output_dir="./quantification",
    mask_props=None,
    intensity_props=None,
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Extract single-cell quantification data from segmented microscopy images.
    
    This function uses mcquant to quantify marker intensities for each segmented cell
    in multi-channel microscopy images. It extracts spatial features and intensity
    measurements for downstream analysis.
    
    Parameters
    ----------
    image_path : str
        Path to the multi-channel image file for quantification.
        Supports .tif, .tiff, .h5, or .hdf5 formats.
    mask_paths : str or list of str
        Path(s) to segmentation mask file(s). If multiple masks are provided,
        the first mask will be used for spatial feature extraction but all
        will be quantified. Typically outputs from segmentation tools like
        S3segmenter or similar.
    channel_names : str or list of str
        Either:
        - Path to a CSV file containing channel names (one name per line)
        - List of channel names as strings
        The number of channels must match the image.
    output_dir : str, optional
        Directory to save output CSV files. Default: "./quantification"
    mask_props : list of str, optional
        Additional mask properties to calculate (e.g., 'perimeter', 'convex_area').
        These are metrics that depend only on the cell mask shape.
        See: https://scikit-image.org/docs/dev/api/skimage.measure.html#regionprops
        Default: None (uses standard properties)
    intensity_props : list of str, optional
        Additional intensity properties to calculate for each marker.
        Options include: 'intensity_median', 'intensity_sum', 'gini_index'
        Default: None (uses 'intensity_mean' only)
    singularity_image : str, optional
        Path to the mcquant Singularity image file.
        If not provided, will look for MCQUANT_SIF environment variable,
        or default to "mcquant_latest.sif" in current directory.
        Default: None
        
    Returns
    -------
    str
        Research log summarizing the quantification process, including:
        - Number of cells quantified
        - Number of markers analyzed
        - Output file locations
        - Summary statistics
        
    Examples
    --------
    >>> # Basic quantification with default settings
    >>> log = quantify_cells(
    ...     image_path='data/registered_image.ome.tif',
    ...     mask_paths='data/segmentation/cell_mask.tif',
    ...     channel_names='data/markers.csv',
    ...     output_dir='./results/quantification'
    ... )
    
    >>> # Quantification with multiple masks and custom properties
    >>> log = quantify_cells(
    ...     image_path='image.tif',
    ...     mask_paths=['nuclei_mask.tif', 'cell_mask.tif'],
    ...     channel_names=['DAPI', 'CD3', 'CD8', 'CD20'],
    ...     mask_props=['perimeter', 'convex_area'],
    ...     intensity_props=['intensity_median', 'gini_index'],
    ...     output_dir='./quantification'
    ... )
    
    Notes
    -----
    - Output CSV files are compatible with histoCAT and other single-cell analysis tools
    - Each row represents one cell with its spatial coordinates and marker intensities
    - This function requires Singularity to be installed
    - The image and masks must have matching dimensions
    """
    import os
    import subprocess
    import shlex
    import shutil
    from datetime import datetime
    import tempfile
    
    # Initialize research log
    log = []
    log.append("# mcquant Single-Cell Quantification")
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
        docker_image = "labsyspharm/mcquant:arm64-local"
        log.append(f"Detected ARM64 platform ({machine}), using ARM-native image")
    else:
        docker_image = "labsyspharm/mcquant:latest"
    
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
            singularity_image = os.environ.get('MCQUANT_SIF', 'mcquant_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/mcquant:latest")
            return "\n".join(log)
    else:
        log.append(f"Using Docker image: {docker_image}")
    
    # Validate image path
    image_path_abs = os.path.abspath(image_path)
    if not os.path.exists(image_path_abs):
        log.append(f"✗ Error: Image file not found: {image_path}")
        return "\n".join(log)
    
    # Handle mask paths (can be string or list)
    if isinstance(mask_paths, str):
        mask_paths = [mask_paths]
    
    mask_paths_abs = []
    for mask_path in mask_paths:
        mask_abs = os.path.abspath(mask_path)
        if not os.path.exists(mask_abs):
            log.append(f"✗ Error: Mask file not found: {mask_path}")
            return "\n".join(log)
        mask_paths_abs.append(mask_abs)
    
    # Create output directory
    output_dir_abs = os.path.abspath(output_dir)
    os.makedirs(output_dir_abs, exist_ok=True)
    
    # Handle channel names
    # If it's a list, create a temporary CSV file
    # If it's a path, use it directly
    temp_channel_file = None
    if isinstance(channel_names, list):
        # Create temporary CSV file with channel names
        temp_channel_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False, dir=output_dir_abs
        )
        for channel in channel_names:
            temp_channel_file.write(f"{channel}\n")
        temp_channel_file.close()
        channel_names_abs = temp_channel_file.name
        log.append(f"Created temporary channel names file: {os.path.basename(channel_names_abs)}")
    else:
        # Assume it's a file path
        channel_names_abs = os.path.abspath(channel_names)
        if not os.path.exists(channel_names_abs):
            log.append(f"✗ Error: Channel names file not found: {channel_names}")
            return "\n".join(log)
    
    # Collect all directories that need to be mounted
    mount_dirs = set()
    mount_dirs.add(os.path.dirname(image_path_abs))
    mount_dirs.add(os.path.dirname(channel_names_abs))
    mount_dirs.add(output_dir_abs)
    for mask_abs in mask_paths_abs:
        mount_dirs.add(os.path.dirname(mask_abs))
    
    # Find common parent directory for bind mount
    all_paths = list(mount_dirs)
    if len(all_paths) == 1:
        common_parent = all_paths[0]
    else:
        common_parent = os.path.commonpath(all_paths)
    
    # Create relative paths for use inside container
    image_rel = os.path.relpath(image_path_abs, common_parent)
    masks_rel = [os.path.relpath(m, common_parent) for m in mask_paths_abs]
    channel_names_rel = os.path.relpath(channel_names_abs, common_parent)
    output_rel = os.path.relpath(output_dir_abs, common_parent)
    
    log.append("## Input Parameters")
    log.append(f"- Image: {image_path}")
    log.append(f"- Number of masks: {len(mask_paths_abs)}")
    for i, mask in enumerate(mask_paths):
        log.append(f"  - Mask {i+1}: {mask}")
    log.append(f"- Channel names: {channel_names if isinstance(channel_names, str) else f'{len(channel_names)} channels'}")
    log.append(f"- Output directory: {output_dir}")
    if mask_props:
        log.append(f"- Additional mask properties: {', '.join(mask_props)}")
    if intensity_props:
        log.append(f"- Additional intensity properties: {', '.join(intensity_props)}")
    
    # Build the container command
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{common_parent}:/data",
            docker_image,
            "mcquant",
            "--image", f"/data/{image_rel}",
            "--output", f"/data/{output_rel}",
            "--channel_names", f"/data/{channel_names_rel}",
            "--masks"
        ]
    else:  # apptainer or singularity
        cmd = [
            container_cmd, "exec",
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "mcquant",
            "--image", f"/data/{image_rel}",
            "--output", f"/data/{output_rel}",
            "--channel_names", f"/data/{channel_names_rel}",
            "--masks"
        ]
    
    # Add mask paths
    for mask_rel in masks_rel:
        cmd.append(f"/data/{mask_rel}")
    
    # Add optional mask properties
    if mask_props:
        cmd.append("--mask_props")
        cmd.extend(mask_props)
    
    # Add optional intensity properties
    if intensity_props:
        cmd.append("--intensity_props")
        cmd.extend(intensity_props)
    
    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}\n")
    
    # Run mcquant
    try:
        log.append("Running mcquant single-cell quantification...")
        log.append("Extracting spatial features and marker intensities...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        log.append("✓ mcquant completed successfully\n")
        
        # Log stdout if available (contains useful info)
        if result.stdout:
            log.append("## mcquant Output")
            # The stdout typically contains the parameter dictionary
            stdout_lines = result.stdout.strip().split('\n')
            for line in stdout_lines[:20]:  # Show first 20 lines
                log.append(line)
            if len(stdout_lines) > 20:
                log.append(f"... ({len(stdout_lines) - 20} more lines)")
        
        # Find output CSV file(s)
        import glob
        output_csvs = glob.glob(os.path.join(output_dir_abs, "*.csv"))
        
        if output_csvs:
            log.append("\n## Results")
            log.append(f"✓ Generated {len(output_csvs)} CSV file(s):")
            
            # Analyze each output CSV
            for csv_file in output_csvs:
                file_size = os.path.getsize(csv_file) / 1024  # Size in KB
                log.append(f"\n  File: {os.path.basename(csv_file)}")
                log.append(f"  Size: {file_size:.2f} KB")
                
                # Try to read CSV and get some stats
                try:
                    import pandas as pd
                    df = pd.read_csv(csv_file)
                    n_cells = len(df)
                    n_features = len(df.columns)
                    log.append(f"  Cells quantified: {n_cells}")
                    log.append(f"  Features extracted: {n_features}")
                    log.append(f"  Columns: {', '.join(df.columns[:10].tolist())}")
                    if n_features > 10:
                        log.append(f"    ... and {n_features - 10} more")
                except Exception as e:
                    log.append(f"  (Could not parse CSV: {e})")
        else:
            log.append("\n⚠ Warning: No CSV files found in output directory")
        
    except subprocess.CalledProcessError as e:
        log.append(f"\n✗ Error: mcquant failed with exit code {e.returncode}")
        if e.stdout:
            log.append(f"\nStdout:\n{e.stdout}")
        if e.stderr:
            log.append(f"\nStderr:\n{e.stderr}")
        return "\n".join(log)
    
    except FileNotFoundError:
        log.append(f"\n✗ Error: Container runtime command not found. Please ensure {container_type} is installed and in your PATH.")
        return "\n".join(log)
    
    except Exception as e:
        log.append(f"\n✗ Error: {str(e)}")
        import traceback
        log.append(traceback.format_exc())
        return "\n".join(log)
    
    finally:
        # Clean up temporary channel names file if created
        if temp_channel_file and os.path.exists(temp_channel_file.name):
            try:
                os.remove(temp_channel_file.name)
                log.append(f"\nCleaned up temporary channel file")
            except:
                pass
    
    log.append("\n## Conclusion")
    log.append("Single-cell quantification completed successfully.")
    log.append(f"Output CSV file(s) saved to: {output_dir_abs}")
    log.append("\nThe output CSV can be used for:")
    log.append("  - Single-cell analysis and clustering")
    log.append("  - Spatial analysis and neighborhood profiling")
    log.append("  - Integration with histoCAT, Seurat, Scanpy, etc.")
    log.append("  - Visualization and statistical analysis")
    
    return "\n".join(log)


def batch_quantify_cells(
    image_mask_pairs,
    channel_names,
    output_dir="./quantification",
    mask_props=None,
    intensity_props=None,
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Batch quantification of multiple images with their corresponding masks.
    
    Convenient wrapper for processing multiple images in a single call.
    
    Parameters
    ----------
    image_mask_pairs : list of tuple
        List of (image_path, mask_paths) tuples. Each tuple contains:
        - image_path: str - path to the image
        - mask_paths: str or list of str - path(s) to mask file(s)
    channel_names : str or list of str
        Channel names file or list of channel names (same for all images)
    output_dir : str, optional
        Base output directory. Each image will create a subdirectory.
        Default: "./quantification"
    mask_props : list of str, optional
        Additional mask properties to calculate. Default: None
    intensity_props : list of str, optional
        Additional intensity properties to calculate. Default: None
    singularity_image : str, optional
        Path to the mcquant Singularity image. Default: None
        
    Returns
    -------
    str
        Combined research log for all quantifications
        
    Examples
    --------
    >>> # Batch quantify multiple images
    >>> pairs = [
    ...     ('image1.tif', 'mask1.tif'),
    ...     ('image2.tif', 'mask2.tif'),
    ...     ('image3.tif', 'mask3.tif')
    ... ]
    >>> log = batch_quantify_cells(
    ...     image_mask_pairs=pairs,
    ...     channel_names='markers.csv',
    ...     output_dir='./quantification'
    ... )
    """
    import os
    from datetime import datetime
    
    batch_log = []
    batch_log.append("# Batch Single-Cell Quantification")
    batch_log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    batch_log.append(f"Total images to process: {len(image_mask_pairs)}\n")
    
    successful = 0
    failed = 0
    
    for i, (image_path, mask_paths) in enumerate(image_mask_pairs, 1):
        batch_log.append(f"\n{'='*60}")
        batch_log.append(f"Processing {i}/{len(image_mask_pairs)}: {os.path.basename(image_path)}")
        batch_log.append('='*60)
        
        # Create subdirectory for this image
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        image_output_dir = os.path.join(output_dir, image_name)
        
        # Run quantification
        log = quantify_cells(
            image_path=image_path,
            mask_paths=mask_paths,
            channel_names=channel_names,
            output_dir=image_output_dir,
            mask_props=mask_props,
            intensity_props=intensity_props,
            singularity_image=singularity_image,
            container_runtime=container_runtime,
        )
        
        batch_log.append(log)
        
        # Check if successful
        if "completed successfully" in log:
            successful += 1
            batch_log.append(f"\n✓ {image_name}: SUCCESS")
        else:
            failed += 1
            batch_log.append(f"\n✗ {image_name}: FAILED")
    
    # Summary
    batch_log.append(f"\n{'='*60}")
    batch_log.append("# Batch Processing Summary")
    batch_log.append('='*60)
    batch_log.append(f"Total processed: {len(image_mask_pairs)}")
    batch_log.append(f"Successful: {successful}")
    batch_log.append(f"Failed: {failed}")
    batch_log.append(f"Success rate: {100*successful/len(image_mask_pairs):.1f}%")
    
    return "\n".join(batch_log)

