"""
Background subtraction tools for microscopy images.

This module provides wrapper functions for background_subtraction, a tool that performs
pixel-by-pixel channel subtraction scaled by exposure times. Primarily developed for
images produced by the COMET platform and works within the MCMICRO pipeline. Main use
case is autofluorescence subtraction for multichannel and multicycle images.
"""


def subtract_background(
    input_image: str,
    markers_file: str,
    output_image: str,
    output_markers: str | None = None,
    pixel_size: float | None = None,
    tile_size: int = 1024,
    chunk_size: int = 5000,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Subtract background from microscopy image using pixel-by-pixel channel subtraction.

    This function performs background (autofluorescence) subtraction for multichannel
    microscopy images on a pixel-to-pixel basis, scaled by exposure times. The most
    precise way of subtracting background for improved segmentation, quantification,
    and visualization of images from tissues with high autofluorescence (FFPE).

    Background subtraction formula:
    Marker_corrected = Marker_raw - (Background / Exposure_Background) * Exposure_Marker

    Parameters
    ----------
    input_image : str
        Path to the input microscopy image file (OME-TIFF).
    markers_file : str
        Path to the markers.csv file containing channel information.
        Must have columns: "marker_name", "background", "exposure", and optionally "remove".
        - marker_name: Name of the marker for each channel (must be unique)
        - background: Marker name of the channel to subtract (must match a marker_name)
        - exposure: Exposure time used for channel acquisition (consistent units)
        - remove: TRUE for channels to exclude from output
    output_image : str
        Path for the output background-subtracted OME-TIFF image.
    output_markers : str, optional
        Path for the output markers CSV file. If not provided, will use
        "{output_image_basename}_markers.csv" in the same directory as output_image.
    pixel_size : float, optional
        Pixel size of the input image. If not specified, will be read from metadata.
        (default: None)
    tile_size : int, optional
        Tile size for the pyramidal output image. Adjust to smaller value (e.g. 512)
        if output file is unexpectedly large. (default: 1024)
    chunk_size : int, optional
        Chunk size for delayed calculation execution. Lower values increase execution
        time, higher values increase RAM usage. (default: 5000)
    singularity_image : str, optional
        Path to the background_subtraction Singularity image file.
        If not provided, will look for BACKGROUND_SUBTRACTION_SIF environment variable,
        or default to "background_subtraction_latest.sif" in current directory.
        (default: None)

    Returns
    -------
    str
        A research log summarizing the background subtraction process and results.

    Notes
    -----
    - The markers.csv file format is critical for correct operation
    - Memory-efficient implementation processes images in chunks
    - Output is a pyramidal OME-TIFF with processed channels only (removed channels excluded)
    """
    import subprocess
    import os
    import shlex
    import shutil
    from datetime import datetime

    log = []
    log.append(f"# Background Subtraction Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Detect container runtime
    container_type = None
    container_cmd = None
    docker_image = "ghcr.io/schapirolabor/background_subtraction:latest"
    
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
            singularity_image = os.environ.get('BACKGROUND_SUBTRACTION_SIF', 'background_subtraction_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://ghcr.io/schapirolabor/background_subtraction:latest")
            return "\n".join(log)
    else:
        log.append(f"Using Docker image: {docker_image}")

    # Validate inputs
    if not os.path.isfile(input_image):
        log.append(f"✗ Error: Input image not found: {input_image}")
        return "\n".join(log)
    
    if not os.path.isfile(markers_file):
        log.append(f"✗ Error: Markers file not found: {markers_file}")
        return "\n".join(log)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_image)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log.append(f"Created output directory: {output_dir}")

    # Set output markers path if not provided
    if output_markers is None:
        output_base = os.path.splitext(output_image)[0]
        output_markers = f"{output_base}_markers.csv"

    # Get absolute paths for bind mounting
    input_image_abs = os.path.abspath(input_image)
    markers_file_abs = os.path.abspath(markers_file)
    output_image_abs = os.path.abspath(output_image)
    output_markers_abs = os.path.abspath(output_markers)

    # Find common parent directory for bind mount
    all_paths = [
        os.path.dirname(input_image_abs),
        os.path.dirname(markers_file_abs),
        os.path.dirname(output_image_abs),
        os.path.dirname(output_markers_abs)
    ]
    common_parent = os.path.commonpath(all_paths)

    # Create relative paths for use inside container
    input_rel = os.path.relpath(input_image_abs, common_parent)
    markers_rel = os.path.relpath(markers_file_abs, common_parent)
    output_rel = os.path.relpath(output_image_abs, common_parent)
    output_markers_rel = os.path.relpath(output_markers_abs, common_parent)

    # Build the container command
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{common_parent}:/data",
            docker_image,
            "python", "-m", "backsub",
            "-r", f"/data/{input_rel}",
            "-o", f"/data/{output_rel}",
            "-m", f"/data/{markers_rel}",
            "-mo", f"/data/{output_markers_rel}",
            "--tile-size", str(tile_size),
        ]
    else:  # apptainer or singularity
        cmd = [
            container_cmd, "exec",
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "python", "-m", "backsub",
            "-r", f"/data/{input_rel}",
            "-o", f"/data/{output_rel}",
            "-m", f"/data/{markers_rel}",
            "-mo", f"/data/{output_markers_rel}",
            "--tile-size", str(tile_size),
        ]

    # Add optional pixel size
    if pixel_size is not None:
        cmd.extend(["--pixel-size", str(pixel_size)])

    log.append("## Input Parameters")
    log.append(f"- Input image: {input_image}")
    log.append(f"- Markers file: {markers_file}")
    log.append(f"- Output image: {output_image}")
    log.append(f"- Output markers: {output_markers}")
    if pixel_size is not None:
        log.append(f"- Pixel size: {pixel_size}")
    log.append(f"- Tile size: {tile_size}")
    log.append(f"- Chunk size: {chunk_size}")
    log.append(f"- Singularity image: {singularity_image}")

    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}")

    try:
        log.append("Running background subtraction...")
        log.append("This may take several minutes depending on image size...")
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log.append("✓ Background subtraction completed successfully")
        
        log.append("\n### Processing Output:")
        if process.stdout:
            log.append(process.stdout)
        if process.stderr:
            log.append("\n### Warnings/Errors:")
            log.append(process.stderr)

        log.append("\n## Results")
        if os.path.exists(output_image):
            log.append(f"✓ Output image: {output_image}")
            log.append(f"  File size: {os.path.getsize(output_image) / (1024*1024):.2f} MB")
        else:
            log.append(f"✗ Output image not found at {output_image}")
        
        if os.path.exists(output_markers):
            log.append(f"✓ Output markers: {output_markers}")
        else:
            log.append(f"✗ Output markers not found at {output_markers}")

    except subprocess.CalledProcessError as e:
        log.append(f"✗ Error running background subtraction: {e}")
        log.append(f"  Return Code: {e.returncode}")
        if e.stdout:
            log.append(f"  Stdout: {e.stdout}")
        if e.stderr:
            log.append(f"  Stderr: {e.stderr}")
        return "\n".join(log)
    except FileNotFoundError:
        log.append(f"✗ Error: Container runtime command not found. Please ensure {container_type} is installed and in your PATH.")
        return "\n".join(log)
    except Exception as e:
        log.append(f"✗ An unexpected error occurred: {e}")
        return "\n".join(log)

    log.append("\n## Conclusion")
    log.append("Background subtraction completed successfully.")
    log.append("The output image contains processed channels with autofluorescence removed.")
    log.append("Channels marked for removal have been excluded from the output.")

    return "\n".join(log)


def batch_subtract_background(
    input_images: list[str],
    markers_files: list[str],
    output_dir: str,
    pixel_size: float | None = None,
    tile_size: int = 1024,
    chunk_size: int = 5000,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Subtract background from multiple microscopy images in batch.

    This function processes multiple microscopy images, performing background
    subtraction for each one using corresponding markers files.

    Parameters
    ----------
    input_images : list of str
        List of input microscopy image file paths.
    markers_files : list of str
        List of markers CSV file paths, corresponding to each input image.
        Must be same length as input_images.
    output_dir : str
        Directory where all output images and markers files will be saved.
    pixel_size : float, optional
        Pixel size of the input images. If not specified, will be read from metadata.
        (default: None)
    tile_size : int, optional
        Tile size for the pyramidal output images. (default: 1024)
    chunk_size : int, optional
        Chunk size for delayed calculation execution. (default: 5000)
    singularity_image : str, optional
        Path to the background_subtraction Singularity image file.
        If not provided, will look for BACKGROUND_SUBTRACTION_SIF environment variable,
        or default to "background_subtraction_latest.sif" in current directory.
        (default: None)

    Returns
    -------
    str
        A research log summarizing the batch processing results for all images.
    """
    import os
    from datetime import datetime

    # Auto-detect Singularity image path if not provided
    if singularity_image is None:
        singularity_image = os.environ.get('BACKGROUND_SUBTRACTION_SIF', 'background_subtraction_latest.sif')

    log = []
    log.append(f"# Batch Background Subtraction Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Validate input lists
    if len(input_images) != len(markers_files):
        log.append(f"✗ Error: Number of input images ({len(input_images)}) does not match number of markers files ({len(markers_files)})")
        return "\n".join(log)

    log.append("## Configuration")
    log.append(f"- Number of images: {len(input_images)}")
    log.append(f"- Output directory: {output_dir}")
    if pixel_size is not None:
        log.append(f"- Pixel size: {pixel_size}")
    log.append(f"- Tile size: {tile_size}")
    log.append(f"- Chunk size: {chunk_size}")
    log.append(f"- Singularity image: {singularity_image}")

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log.append(f"\nCreated output directory: {output_dir}")

    log.append("\n## Processing Images")

    successful_images = []
    failed_images = []

    for i, (input_image, markers_file) in enumerate(zip(input_images, markers_files), 1):
        log.append(f"\n### Image {i}/{len(input_images)}: {os.path.basename(input_image)}")

        if not os.path.isfile(input_image):
            log.append(f"✗ Input image not found: {input_image}")
            failed_images.append(input_image)
            continue
        
        if not os.path.isfile(markers_file):
            log.append(f"✗ Markers file not found: {markers_file}")
            failed_images.append(input_image)
            continue

        # Generate output paths
        image_basename = os.path.splitext(os.path.basename(input_image))[0]
        output_image = os.path.join(output_dir, f"{image_basename}_backsub.ome.tif")
        output_markers = os.path.join(output_dir, f"{image_basename}_markers.csv")

        # Process this image
        result = subtract_background(
            input_image=input_image,
            markers_file=markers_file,
            output_image=output_image,
            output_markers=output_markers,
            pixel_size=pixel_size,
            tile_size=tile_size,
            chunk_size=chunk_size,
            singularity_image=singularity_image,
            container_runtime=container_runtime,
        )

        # Check if processing was successful
        if "✓ Background subtraction completed successfully" in result:
            log.append(f"✓ Background subtracted successfully → {output_image}")
            successful_images.append(input_image)
        else:
            log.append(f"✗ Background subtraction failed")
            failed_images.append(input_image)
            # Include the detailed error log
            log.append("\nDetailed error log:")
            log.append(result)

    log.append("\n## Summary")
    log.append(f"- Total images: {len(input_images)}")
    log.append(f"- Successful: {len(successful_images)}")
    log.append(f"- Failed: {len(failed_images)}")

    if failed_images:
        log.append("\nFailed images:")
        for img in failed_images:
            log.append(f"  - {img}")

    if len(successful_images) == len(input_images):
        log.append("\n✓ All images processed successfully!")
    elif len(successful_images) > 0:
        log.append("\n⚠ Some images processed successfully, but some failed.")
    else:
        log.append("\n✗ All images failed to process.")

    return "\n".join(log)

