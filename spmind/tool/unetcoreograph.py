"""
UNetCoreograph TMA dearraying tool.

This module provides wrapper functions for UNetCoreograph, a deep learning tool that uses
UNet to identify and segment complete/incomplete tissue cores on tissue microarrays (TMAs).
The tool generates individual core images, tissue masks, and a TMA map for quality control.
"""


def dearray_tma(
    input_image: str,
    output_dir: str,
    downsample_factor: int = 5,
    channel: int = 0,
    buffer: float = 2.0,
    output_channels: str = "-1",
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Dearray a tissue microarray (TMA) image into individual tissue cores using UNet.

    This function uses UNetCoreograph, a deep learning model, to identify complete/incomplete
    tissue cores on a TMA slide. It generates individual core images, binary tissue masks,
    and a TMA map showing core labels and outlines for quality control.

    The tool has been trained on 9 TMA slides of different sizes and tissue types at
    0.2 micron/pixel resolution, downsampled 1/32 times. Once cores are identified,
    active contours generate tissue masks to aid downstream single cell segmentation.

    Parameters
    ----------
    input_image : str
        Path to the input TMA image file. Should be TIF or OME-TIFF format.
    output_dir : str
        Directory where output files will be saved. Will be created if it doesn't exist.
    downsample_factor : int, optional
        How many times to downsample the raw image file. Lower values (1-3) work better
        for high-resolution images. Higher values (5-10) work for lower resolution images.
        WARNING: If using for tissue splitting, set to higher than default of 5.
        (default: 5)
    channel : int, optional
        Which channel to feed into UNet for probability map generation.
        This is usually a DAPI/nuclear channel. (default: 0)
    buffer : float, optional
        Extra space around a core before cropping it. A value of 2 means there is twice
        the width of the core added as buffer around it. (default: 2.0)
    output_channels : str, optional
        Range of channels to export. "-1" exports all channels (takes longer).
        Can specify single channel "0" or range "0 10" for channels 0-10 (inclusive).
        (default: "-1")
    singularity_image : str, optional
        Path to the UNetCoreograph Singularity image file.
        If not provided, will look for UNETCOREOGRAPH_SIF environment variable,
        or default to "unetcoreograph_latest.sif" in current directory.
        (default: None)

    Returns
    -------
    str
        A research log summarizing the dearraying process and results.

    Notes
    -----
    - GPU is not required but will reduce computation time
    - Training data was at 0.2 micron/pixel, downsampled 1/32 times
    - If 0 cores detected, try adjusting downsample_factor
    - Output includes: core TIFs, mask/ subdirectory, TMA_MAP.tif/jpg, centroidsY-X.txt

    Examples
    --------
    >>> # Process a high-resolution TMA image
    >>> result = dearray_tma(
    ...     input_image="tma_scan.ome.tif",
    ...     output_dir="./cores_output",
    ...     downsample_factor=1,
    ...     channel=0
    ... )
    
    >>> # Export only specific channels (0-5)
    >>> result = dearray_tma(
    ...     input_image="tma_scan.ome.tif",
    ...     output_dir="./cores_output",
    ...     downsample_factor=1,
    ...     channel=0,
    ...     output_channels="0 5"
    ... )
    """
    import subprocess
    import os
    import shlex
    import shutil
    from datetime import datetime

    log = []
    log.append(f"# UNetCoreograph TMA Dearraying Report")
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
        docker_image = "labsyspharm/unetcoreograph:2.4.3-arm"
        log.append(f"Detected ARM64 platform ({machine}), using ARM-native image")
    else:
        docker_image = "labsyspharm/unetcoreograph:latest"
    
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
            singularity_image = os.environ.get('UNETCOREOGRAPH_SIF', 'unetcoreograph_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/unetcoreograph:latest")
            return "\n".join(log)
    else:
        log.append(f"Using Docker image: {docker_image}")

    # Validate inputs
    if not os.path.isfile(input_image):
        log.append(f"✗ Error: Input image not found: {input_image}")
        return "\n".join(log)

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log.append(f"Created output directory: {output_dir}")

    # Get absolute paths for bind mounting
    input_image_abs = os.path.abspath(input_image)
    output_dir_abs = os.path.abspath(output_dir)

    # Find common parent directory for bind mount
    input_dir = os.path.dirname(input_image_abs)
    common_parent = os.path.commonpath([input_dir, output_dir_abs])

    # Create relative paths for use inside container
    input_rel = os.path.relpath(input_image_abs, common_parent)
    output_rel = os.path.relpath(output_dir_abs, common_parent)

    # Build the container command
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{common_parent}:/data",
            docker_image,
            "python", "/app/UNetCoreograph.py",
            "--imagePath", f"/data/{input_rel}",
            "--outputPath", f"/data/{output_rel}/",
            "--downsampleFactor", str(downsample_factor),
            "--channel", str(channel),
            "--buffer", str(buffer),
        ]
    else:  # apptainer or singularity
        cmd = [
            container_cmd, "exec",
            "--nv",  # Enable GPU support
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "python", "/app/UNetCoreograph.py",
            "--imagePath", f"/data/{input_rel}",
            "--outputPath", f"/data/{output_rel}/",
            "--downsampleFactor", str(downsample_factor),
            "--channel", str(channel),
            "--buffer", str(buffer),
        ]

    # Add output channel specification
    if output_channels == "-1":
        cmd.extend(["--outputChan", "-1"])
    else:
        # Split the channel range if provided
        channels = output_channels.split()
        cmd.extend(["--outputChan"] + channels)

    log.append("## Input Parameters")
    log.append(f"- Input image: {input_image}")
    log.append(f"- Output directory: {output_dir}")
    log.append(f"- Downsample factor: {downsample_factor}")
    if downsample_factor <= 5:
        log.append("  ⚠ WARNING: For tissue splitting, downsample factor > 5 is recommended")
    log.append(f"- Channel: {channel} (usually DAPI/nuclear channel)")
    log.append(f"- Buffer: {buffer}x core width")
    log.append(f"- Output channels: {output_channels} ({'all channels' if output_channels == '-1' else 'selected channels'})")
    log.append(f"- Singularity image: {singularity_image}")

    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}")

    try:
        log.append("Running UNetCoreograph dearraying...")
        log.append("This may take several minutes depending on image size and resolution...")
        log.append("GPU will be used if available for faster processing.")
        
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log.append("✓ Dearraying completed successfully")
        
        log.append("\n### Processing Output:")
        if process.stdout:
            # Parse output to extract core count
            stdout_lines = process.stdout.strip().split('\n')
            for line in stdout_lines:
                if 'cores detected' in line.lower():
                    log.append(f"  {line}")
                if 'Segmented all cores' in line:
                    log.append(f"  ✓ {line}")
            log.append("\nFull output:")
            log.append(process.stdout)
        
        if process.stderr:
            log.append("\n### Warnings/Messages:")
            # Filter out common non-critical warnings
            stderr_lines = process.stderr.strip().split('\n')
            critical_lines = [line for line in stderr_lines 
                             if not line.startswith('WARNING: All log messages') 
                             and not 'CUDA' in line
                             and not 'GPU' in line]
            if critical_lines:
                log.append('\n'.join(critical_lines))

        log.append("\n## Results")
        
        # Give a moment for files to be written (especially when exporting all channels)
        import time
        time.sleep(2)
        
        # Check for core files - be more thorough
        core_files = []
        try:
            all_files = os.listdir(output_dir_abs)
            core_files = [f for f in all_files if f.startswith('core_') and f.endswith(('.tif', '.ome.tif'))]
            
            if core_files:
                log.append(f"✓ Individual cores extracted: {len(core_files)} files")
                log.append(f"  Example: {core_files[0]}, {core_files[1] if len(core_files) > 1 else '...'}")
            else:
                # Check if processing was successful based on other indicators
                if "cores detected!" in process.stdout and int(process.stdout.split("cores detected!")[0].split()[-1]) > 0:
                    detected_cores = int(process.stdout.split("cores detected!")[0].split()[-1])
                    log.append(f"⚠ Processing completed ({detected_cores} cores detected), but core files not yet visible.")
                    log.append(f"  Files may still be writing to disk. Check {output_dir_abs} in a moment.")
                    log.append(f"  If files don't appear, the issue may be with channel export or disk space.")
                else:
                    log.append(f"✗ No cores detected during processing.")
                    log.append(f"  Try adjusting the --downsample_factor parameter.")
        except Exception as e:
            log.append(f"⚠ Could not check output files: {e}")
        
        # Check for mask directory
        mask_dir = os.path.join(output_dir_abs, 'mask')
        if os.path.exists(mask_dir):
            try:
                mask_files = [f for f in os.listdir(mask_dir) if f.endswith('.tif')]
                log.append(f"✓ Tissue masks: {len(mask_files)} files in mask/ subdirectory")
            except:
                log.append(f"⚠ Mask directory exists but couldn't list contents")
        else:
            log.append(f"⚠ Mask directory not found (may still be writing)")
        
        # Check for TMA map
        tma_map_tif = os.path.join(output_dir_abs, 'TMA_MAP.tif')
        tma_map_jpg = os.path.join(output_dir_abs, 'TMA_MAP.jpg')
        if os.path.exists(tma_map_tif):
            log.append(f"✓ TMA map (TIFF): {tma_map_tif}")
            log.append(f"  File size: {os.path.getsize(tma_map_tif) / (1024*1024):.2f} MB")
        if os.path.exists(tma_map_jpg):
            log.append(f"✓ TMA map (JPEG): {tma_map_jpg}")
            log.append(f"  File size: {os.path.getsize(tma_map_jpg) / 1024:.2f} KB")
        
        # Check for centroids file
        centroids_file = os.path.join(output_dir_abs, 'centroidsY-X.txt')
        if os.path.exists(centroids_file):
            log.append(f"✓ Core centroids: {centroids_file}")

        # Calculate total output size and list all files for debugging
        try:
            all_output_files = os.listdir(output_dir_abs)
            total_size = sum(
                os.path.getsize(os.path.join(output_dir_abs, f))
                for f in all_output_files
                if os.path.isfile(os.path.join(output_dir_abs, f))
            )
            log.append(f"\n  Total output size: {total_size / (1024*1024):.2f} MB")
            log.append(f"  Total files in output directory: {len([f for f in all_output_files if os.path.isfile(os.path.join(output_dir_abs, f))])}")
        except Exception as e:
            log.append(f"\n  Could not calculate output size: {e}")

    except subprocess.CalledProcessError as e:
        log.append(f"✗ Error running UNetCoreograph: {e}")
        log.append(f"  Return Code: {e.returncode}")
        if e.stdout:
            log.append(f"\n  Stdout:\n{e.stdout}")
        if e.stderr:
            log.append(f"\n  Stderr:\n{e.stderr}")
        return "\n".join(log)
    except FileNotFoundError:
        log.append(f"✗ Error: Container runtime command not found. Please ensure {container_type} is installed and in your PATH.")
        return "\n".join(log)
    except Exception as e:
        log.append(f"✗ An unexpected error occurred: {e}")
        return "\n".join(log)

    log.append("\n## Conclusion")
    
    # Determine success based on stdout indicators
    cores_detected = 0
    segmentation_complete = False
    if "cores detected!" in process.stdout:
        try:
            cores_detected = int(process.stdout.split("cores detected!")[0].split()[-1])
        except:
            pass
    if "Segmented all cores" in process.stdout or "Segmented all cores/tissues!" in process.stdout:
        segmentation_complete = True
    
    if cores_detected > 0 and segmentation_complete:
        log.append(f"✓ TMA dearraying completed successfully!")
        log.append(f"  - Detected and segmented {cores_detected} tissue cores")
        if core_files:
            log.append(f"  - Extracted {len(core_files)} individual core image files")
        log.append(f"  - Output saved to: {output_dir}")
        log.append("\nGenerated files:")
        log.append("  1. Individual core images as TIFF stacks (core_XXX.tif)")
        log.append("  2. Binary tissue masks in mask/ subdirectory")
        log.append("  3. TMA_MAP.tif/jpg showing core labels and outlines for QC")
        log.append("  4. centroidsY-X.txt with core centroid coordinates")
        if not core_files:
            log.append("\n⚠ Note: Core files may still be writing to disk (especially if exporting all channels).")
            log.append(f"  Please check {output_dir} to verify all files are present.")
        log.append("\nThese cores can now be used for downstream analysis such as:")
        log.append("  - Single cell segmentation")
        log.append("  - Quantitative image analysis")
        log.append("  - Biomarker expression profiling")
    else:
        log.append("✗ TMA dearraying did not detect any cores.")
        log.append("Troubleshooting suggestions:")
        log.append("  - Try different downsample_factor values (1, 2, 3, 5, 10)")
        log.append("  - Verify the correct channel is specified (usually DAPI)")
        log.append("  - Check that the input is actually a TMA image")

    return "\n".join(log)


def batch_dearray_tma(
    input_images: list[str],
    output_base_dir: str,
    downsample_factor: int = 5,
    channel: int = 0,
    buffer: float = 2.0,
    output_channels: str = "-1",
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Dearray multiple TMA images in batch.

    This function processes multiple TMA images, dearraying each one into individual
    tissue cores using UNetCoreograph.

    Parameters
    ----------
    input_images : list of str
        List of input TMA image file paths.
    output_base_dir : str
        Base directory where output subdirectories will be created for each TMA.
        Each TMA will get its own subdirectory named after the input file.
    downsample_factor : int, optional
        How many times to downsample the raw image files. (default: 5)
    channel : int, optional
        Which channel to use for core detection (usually DAPI). (default: 0)
    buffer : float, optional
        Extra space around cores before cropping. (default: 2.0)
    output_channels : str, optional
        Range of channels to export. (default: "-1" for all channels)
    singularity_image : str, optional
        Path to the UNetCoreograph Singularity image file.
        If not provided, will look for UNETCOREOGRAPH_SIF environment variable,
        or default to "unetcoreograph_latest.sif" in current directory.
        (default: None)

    Returns
    -------
    str
        A research log summarizing the batch processing results for all TMAs.
    """
    import os
    from datetime import datetime

    # Auto-detect Singularity image path if not provided
    if singularity_image is None:
        singularity_image = os.environ.get('UNETCOREOGRAPH_SIF', 'unetcoreograph_latest.sif')

    log = []
    log.append(f"# Batch TMA Dearraying Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    log.append("## Configuration")
    log.append(f"- Number of TMAs: {len(input_images)}")
    log.append(f"- Output base directory: {output_base_dir}")
    log.append(f"- Downsample factor: {downsample_factor}")
    log.append(f"- Channel: {channel}")
    log.append(f"- Buffer: {buffer}")
    log.append(f"- Output channels: {output_channels}")
    log.append(f"- Singularity image: {singularity_image}")

    # Ensure output base directory exists
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
        log.append(f"\nCreated output base directory: {output_base_dir}")

    log.append("\n## Processing TMAs")

    successful_tmas = []
    failed_tmas = []
    core_counts = {}

    for i, input_image in enumerate(input_images, 1):
        log.append(f"\n### TMA {i}/{len(input_images)}: {os.path.basename(input_image)}")

        if not os.path.isfile(input_image):
            log.append(f"✗ Input image not found: {input_image}")
            failed_tmas.append(input_image)
            continue

        # Create output directory for this TMA
        tma_basename = os.path.splitext(os.path.basename(input_image))[0]
        output_dir = os.path.join(output_base_dir, tma_basename)

        # Process this TMA
        result = dearray_tma(
            input_image=input_image,
            output_dir=output_dir,
            downsample_factor=downsample_factor,
            channel=channel,
            buffer=buffer,
            output_channels=output_channels,
            singularity_image=singularity_image,
            container_runtime=container_runtime,
        )

        # Check if processing was successful
        if "✓ Dearraying completed successfully" in result:
            # Extract core count from result
            for line in result.split('\n'):
                if 'Individual cores extracted:' in line:
                    try:
                        core_count = int(line.split(':')[1].strip().split()[0])
                        core_counts[tma_basename] = core_count
                    except:
                        core_counts[tma_basename] = "unknown"
            
            log.append(f"✓ Dearrayed successfully → {output_dir}")
            if tma_basename in core_counts:
                log.append(f"  Cores extracted: {core_counts[tma_basename]}")
            successful_tmas.append(input_image)
        else:
            log.append(f"✗ Dearraying failed")
            failed_tmas.append(input_image)
            # Include brief error info
            if "0 cores detected" in result or "No core files found" in result:
                log.append("  Reason: No cores detected (try adjusting downsample_factor)")

    log.append("\n## Summary")
    log.append(f"- Total TMAs: {len(input_images)}")
    log.append(f"- Successful: {len(successful_tmas)}")
    log.append(f"- Failed: {len(failed_tmas)}")
    
    if core_counts:
        total_cores = sum(c for c in core_counts.values() if isinstance(c, int))
        log.append(f"- Total cores extracted: {total_cores}")
        log.append("\nCores per TMA:")
        for tma_name, count in core_counts.items():
            log.append(f"  - {tma_name}: {count} cores")

    if failed_tmas:
        log.append("\nFailed TMAs:")
        for img in failed_tmas:
            log.append(f"  - {img}")

    if len(successful_tmas) == len(input_images):
        log.append("\n✓ All TMAs processed successfully!")
    elif len(successful_tmas) > 0:
        log.append("\n⚠ Some TMAs processed successfully, but some failed.")
    else:
        log.append("\n✗ All TMAs failed to process.")

    return "\n".join(log)

