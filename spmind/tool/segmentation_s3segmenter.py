"""
S3segmenter watershed-based cell segmentation tools.

This module provides wrapper functions for S3segmenter, a watershed-based segmentation 
tool that generates single-cell (nuclei and cytoplasm) label masks from probability maps.
It uses marker-controlled watershed constrained by nuclei contours to create final 
segmentation masks.
"""


def segment_cells(
    input_image: str,
    probability_maps_dir: str,
    output_dir: str,
    contours_pm: str | None = None,
    nuclei_pm: str | None = None,
    crop_method: str = "noCrop",
    mask_type: str = "tissue",
    nuclei_region: str = "watershedContourInt",
    nuclei_filter: str = "IntPM",
    segment_cytoplasm: bool = False,
    cytoplasm_channels: list[int] | None = None,
    cyto_method: str = "distanceTransform",
    cyto_dilation: int = 5,
    log_sigma: list[int] | None = None,
    tissue_mask_channel: int = 1,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Segment cells using S3segmenter watershed-based segmentation.

    This function applies marker-controlled watershed segmentation to generate single-cell
    masks from probability maps. It can segment nuclei only or include cytoplasm segmentation
    using specified cytoplasmic markers.

    The workflow:
    1. Finds local maxima from nuclei foreground probability map
    2. Uses these as seeds for watershed constrained by nuclei contours
    3. Optionally segments cytoplasm using nuclei as seeds and cytoplasmic markers

    Parameters
    ----------
    input_image : str
        Path to the input microscopy image file (TIF or OME-TIFF).
        This is the original image, not the probability maps.
    probability_maps_dir : str
        Directory containing probability map files from UnMicst or similar tools.
        Should contain NucleiPM and ContoursPM files.
    output_dir : str
        Directory where output segmentation masks will be saved.
        Will be created if it doesn't exist.
    contours_pm : str, optional
        Path to nuclei contours probability map file. If None, will search in
        probability_maps_dir for files containing "ContoursPM".
        (default: None)
    nuclei_pm : str, optional
        Path to nuclei foreground probability map file. If None, will search in
        probability_maps_dir for files containing "NucleiPM".
        (default: None)
    crop_method : str, optional
        Cropping method:
        - 'noCrop': No cropping (default)
        - 'dearray': For TMA cores
        - 'autoCrop': Middle third region
        - 'plate': For multi-well plates
        (default: 'noCrop')
    mask_type : str, optional
        Type of tissue mask:
        - 'tissue': Automatic tissue detection (default)
        - 'TMA': For tissue microarray cores
        - 'none': No tissue masking
        (default: 'tissue')
    nuclei_region : str, optional
        Nuclei segmentation method:
        - 'watershedContourInt': Marker-controlled watershed using intensity (default)
        - 'watershedContourDist': Using distance transform
        - 'watershedBWDist': Binary distance watershed
        - 'dilation': Simple dilation
        - 'bypass': Use external segmentation
        (default: 'watershedContourInt')
    nuclei_filter : str, optional
        Feature for nuclei filtering:
        - 'IntPM': Intensity of probability map (default)
        - 'Int': DAPI intensity
        - 'LoG': Laplacian of Gaussian
        - 'none': Accept all nuclei
        (default: 'IntPM')
    segment_cytoplasm : bool, optional
        Whether to segment cytoplasm in addition to nuclei.
        (default: False)
    cytoplasm_channels : list of int, optional
        List of channel indices (1-indexed) to use for cytoplasm segmentation.
        Required if segment_cytoplasm=True. Example: [2, 3] for channels 2 and 3.
        (default: None)
    cyto_method : str, optional
        Cytoplasm segmentation method:
        - 'distanceTransform': Distance-based expansion from nuclei (default)
        - 'ring': 3-pixel annulus around nuclei
        - 'hybrid': Combination approach
        - 'bwdistanceTransform': Binary distance transform
        (default: 'distanceTransform')
    cyto_dilation : int, optional
        Dilation size for cytoplasm segmentation in pixels.
        (default: 5)
    log_sigma : list of int, optional
        Range of nuclei diameters in pixels [min, max] for Laplacian of Gaussian filter.
        (default: [3, 60])
    tissue_mask_channel : int, optional
        Channel to use for tissue mask generation (1-indexed).
        Usually a DNA or membrane marker channel.
        (default: 1)
    singularity_image : str, optional
        Path to the S3segmenter Singularity image file.
        If not provided, will look for S3SEGMENTER_SIF environment variable,
        or default to "s3segmenter_latest.sif" in current directory.
        Only used when container_runtime is 'apptainer' or 'singularity'.
        (default: None)
    container_runtime : str, optional
        Container runtime to use: 'auto', 'apptainer', 'singularity', or 'docker'.
        'auto' will detect available runtime (prefers apptainer/singularity over docker).
        (default: 'auto')

    Returns
    -------
    str
        A research log summarizing the segmentation process and results.

    Notes
    -----
    - Requires probability maps from UnMicst or similar tools
    - Output includes nuclei masks and optionally cytoplasm/cell masks
    - All channel indices are 1-indexed (channel 1 = first channel)
    - Creates subdirectory named after input file for outputs
    - Generates QC images with outlines for quality control

    Examples
    --------
    >>> # Nuclei-only segmentation
    >>> result = segment_cells(
    ...     input_image="tissue.ome.tif",
    ...     probability_maps_dir="./probability_maps",
    ...     output_dir="./segmentation",
    ...     segment_cytoplasm=False
    ... )
    
    >>> # Nuclei + cytoplasm segmentation
    >>> result = segment_cells(
    ...     input_image="tissue.ome.tif",
    ...     probability_maps_dir="./probability_maps",
    ...     output_dir="./segmentation",
    ...     segment_cytoplasm=True,
    ...     cytoplasm_channels=[2, 3],
    ...     cyto_method="distanceTransform"
    ... )
    """
    import subprocess
    import os
    import shlex
    import glob
    import shutil
    from datetime import datetime

    log = []
    
    def _raise_with_log(exception: type[Exception]) -> None:
        """Raise exception with the accumulated log."""
        raise exception("\n".join(log))

    log.append(f"# S3segmenter Cell Segmentation Report")
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
        docker_image = "labsyspharm/s3segmenter:arm64-local"
        log.append(f"Detected ARM64 platform ({machine}), using ARM-native image")
    else:
        docker_image = "labsyspharm/s3segmenter:latest"
    
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
        _raise_with_log(FileNotFoundError)
    
    # For apptainer/singularity, check .sif file exists
    if container_type in ("apptainer", "singularity"):
        if singularity_image is None:
            singularity_image = os.environ.get('S3SEGMENTER_SIF', 's3segmenter_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/s3segmenter:latest")
            _raise_with_log(FileNotFoundError)
    else:
        log.append(f"Using Docker image: {docker_image}")

    # Validate inputs
    if not os.path.isfile(input_image):
        log.append(f"✗ Error: Input image not found: {input_image}")
        _raise_with_log(FileNotFoundError)
    
    if not os.path.isdir(probability_maps_dir):
        log.append(f"✗ Error: Probability maps directory not found: {probability_maps_dir}")
        _raise_with_log(FileNotFoundError)

    # Auto-detect probability map files if not provided
    if contours_pm is None:
        contours_files = glob.glob(os.path.join(probability_maps_dir, "*ContoursPM*.tif"))
        if contours_files:
            contours_pm = contours_files[0]
            log.append(f"Auto-detected contours PM: {os.path.basename(contours_pm)}")
        else:
            log.append(f"✗ Error: No contours probability map found in {probability_maps_dir}")
            log.append(f"  Looking for files matching *ContoursPM*.tif")
            log.append("  Hint: Run the UnMicst probability map generator first to create contours maps.")
            _raise_with_log(FileNotFoundError)
    
    if nuclei_pm is None:
        nuclei_files = glob.glob(os.path.join(probability_maps_dir, "*NucleiPM*.tif"))
        if nuclei_files:
            nuclei_pm = nuclei_files[0]
            log.append(f"Auto-detected nuclei PM: {os.path.basename(nuclei_pm)}")
        else:
            log.append(f"✗ Error: No nuclei probability map found in {probability_maps_dir}")
            log.append(f"  Looking for files matching *NucleiPM*.tif")
            log.append("  Hint: Run the UnMicst probability map generator first to create nuclei maps.")
            _raise_with_log(FileNotFoundError)

    # Validate probability map files
    if not os.path.isfile(contours_pm):
        log.append(f"✗ Error: Contours probability map not found: {contours_pm}")
        _raise_with_log(FileNotFoundError)
    
    if not os.path.isfile(nuclei_pm):
        log.append(f"✗ Error: Nuclei probability map not found: {nuclei_pm}")
        _raise_with_log(FileNotFoundError)

    # Validate cytoplasm parameters
    if segment_cytoplasm and (cytoplasm_channels is None or len(cytoplasm_channels) == 0):
        log.append(f"✗ Error: segment_cytoplasm=True requires cytoplasm_channels to be specified")
        _raise_with_log(ValueError)

    # Set default log_sigma
    if log_sigma is None:
        log_sigma = [3, 60]

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log.append(f"Created output directory: {output_dir}")

    # Get absolute paths for bind mounting
    input_image_abs = os.path.abspath(input_image)
    contours_pm_abs = os.path.abspath(contours_pm)
    nuclei_pm_abs = os.path.abspath(nuclei_pm)
    output_dir_abs = os.path.abspath(output_dir)

    # Find common parent directory for bind mount
    all_paths = [
        os.path.dirname(input_image_abs),
        os.path.dirname(contours_pm_abs),
        os.path.dirname(nuclei_pm_abs),
        output_dir_abs
    ]
    common_parent = os.path.commonpath(all_paths)

    # Create relative paths for use inside container
    input_rel = os.path.relpath(input_image_abs, common_parent)
    contours_rel = os.path.relpath(contours_pm_abs, common_parent)
    nuclei_rel = os.path.relpath(nuclei_pm_abs, common_parent)
    output_rel = os.path.relpath(output_dir_abs, common_parent)

    # Build the container command
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{common_parent}:/data",
            docker_image,
            "python", "/app/S3segmenter.py",
            "--imagePath", f"/data/{input_rel}",
            "--contoursClassProbPath", f"/data/{contours_rel}",
            "--nucleiClassProbPath", f"/data/{nuclei_rel}",
            "--outputPath", f"/data/{output_rel}",
            "--crop", crop_method,
            "--mask", mask_type,
            "--nucleiRegion", nuclei_region,
            "--nucleiFilter", nuclei_filter,
            "--TissueMaskChan", str(tissue_mask_channel)
        ]
    else:  # apptainer or singularity
        cmd = [
                container_cmd, "exec",
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "python", "/app/S3segmenter.py",
            "--imagePath", f"/data/{input_rel}",
            "--contoursClassProbPath", f"/data/{contours_rel}",
            "--nucleiClassProbPath", f"/data/{nuclei_rel}",
            "--outputPath", f"/data/{output_rel}",
            "--crop", crop_method,
            "--mask", mask_type,
            "--nucleiRegion", nuclei_region,
            "--nucleiFilter", nuclei_filter,
            "--TissueMaskChan", str(tissue_mask_channel)
        ]

    # Add log sigma
    cmd.extend(["--logSigma"] + [str(s) for s in log_sigma])

    # Add cytoplasm segmentation parameters
    if segment_cytoplasm:
        cmd.extend([
            "--segmentCytoplasm", "segmentCytoplasm",
            "--cytoMethod", cyto_method,
            "--cytoDilation", str(cyto_dilation)
        ])
        if cytoplasm_channels:
            cmd.extend(["--CytoMaskChan"] + [str(c) for c in cytoplasm_channels])
    else:
        cmd.extend(["--segmentCytoplasm", "ignoreCytoplasm"])

    log.append("## Input Parameters")
    log.append(f"- Input image: {input_image}")
    log.append(f"- Contours probability map: {os.path.basename(contours_pm)}")
    log.append(f"- Nuclei probability map: {os.path.basename(nuclei_pm)}")
    log.append(f"- Output directory: {output_dir}")
    log.append(f"- Crop method: {crop_method}")
    log.append(f"- Mask type: {mask_type}")
    log.append(f"- Nuclei region method: {nuclei_region}")
    log.append(f"- Nuclei filter: {nuclei_filter}")
    log.append(f"- Log sigma (nuclei diameter range): {log_sigma} pixels")
    log.append(f"- Tissue mask channel: {tissue_mask_channel}")
    
    if segment_cytoplasm:
        log.append(f"- Segment cytoplasm: Yes")
        log.append(f"  - Cytoplasm channels: {cytoplasm_channels}")
        log.append(f"  - Cytoplasm method: {cyto_method}")
        log.append(f"  - Cytoplasm dilation: {cyto_dilation} pixels")
    else:
        log.append(f"- Segment cytoplasm: No (nuclei only)")
    
    log.append(f"- Singularity image: {singularity_image}")

    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}")

    try:
        log.append("Running S3segmenter watershed segmentation...")
        log.append("This may take several minutes depending on image size...")
        
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log.append("✓ Segmentation completed successfully")
        
        log.append("\n### Processing Output:")
        if process.stdout:
            # Show abbreviated output
            stdout_lines = process.stdout.strip().split('\n')
            # Filter out deprecation warnings
            important_lines = [line for line in stdout_lines 
                             if not 'DeprecationWarning' in line 
                             and not 'deprecated' in line.lower()]
            
            if len(important_lines) > 20:
                log.append("Abbreviated output (key lines):")
                log.append('\n'.join(important_lines[:10]))
                log.append(f"\n... ({len(important_lines) - 15} lines omitted) ...\n")
                log.append('\n'.join(important_lines[-5:]))
            else:
                log.append('\n'.join(important_lines))
        
        if process.stderr:
            # Only show critical errors
            stderr_lines = process.stderr.strip().split('\n')
            critical_lines = [line for line in stderr_lines 
                             if 'Error' in line or 'Failed' in line]
            if critical_lines:
                log.append("\n### Warnings/Errors:")
                log.append('\n'.join(critical_lines))

        log.append("\n## Results")
        
        # Check for output files
        import time
        time.sleep(1)  # Brief pause for file system
        
        # Determine output subdirectory name (handle .ome.tif double extensions)
        image_basename = os.path.splitext(os.path.basename(input_image))[0]
        candidate_names = [image_basename]
        if image_basename.lower().endswith('.ome'):
            candidate_names.append(os.path.splitext(image_basename)[0])

        output_subdir = None
        resolved_subdir_name = None
        for name in candidate_names:
            candidate_path = os.path.join(output_dir_abs, name)
            if os.path.isdir(candidate_path):
                output_subdir = candidate_path
                resolved_subdir_name = name
                break

        if output_subdir is None and os.path.isdir(output_dir_abs):
            subdirs = [
                d for d in os.listdir(output_dir_abs)
                if os.path.isdir(os.path.join(output_dir_abs, d))
            ]
            if len(subdirs) == 1:
                resolved_subdir_name = subdirs[0]
                output_subdir = os.path.join(output_dir_abs, subdirs[0])
        
        output_files = []
        if output_subdir and os.path.exists(output_subdir):
            try:
                all_files = os.listdir(output_subdir)
                
                # Check for nuclei mask
                nuclei_mask = [f for f in all_files if 'nuclei' in f.lower() and f.endswith('.ome.tif') and 'outlines' not in f.lower()]
                if nuclei_mask:
                    log.append(f"✓ Nuclei segmentation mask: {nuclei_mask[0]}")
                    mask_path = os.path.join(output_subdir, nuclei_mask[0])
                    log.append(f"  File size: {os.path.getsize(mask_path) / (1024*1024):.2f} MB")
                    output_files.extend(nuclei_mask)
                
                # Check for cell mask
                cell_mask = [f for f in all_files if 'cell' in f.lower() and f.endswith('.ome.tif') and 'outlines' not in f.lower()]
                if cell_mask:
                    log.append(f"✓ Cell segmentation mask: {cell_mask[0]}")
                    mask_path = os.path.join(output_subdir, cell_mask[0])
                    log.append(f"  File size: {os.path.getsize(mask_path) / (1024*1024):.2f} MB")
                    output_files.extend(cell_mask)
                
                # Check for cytoplasm mask
                if segment_cytoplasm:
                    cyto_mask = [f for f in all_files if 'cyto' in f.lower() and f.endswith('.ome.tif') and 'outlines' not in f.lower()]
                    if cyto_mask:
                        log.append(f"✓ Cytoplasm segmentation mask: {cyto_mask[0]}")
                        output_files.extend(cyto_mask)
                
                # Check for QC directory
                qc_dir = os.path.join(output_subdir, 'qc')
                if os.path.exists(qc_dir):
                    qc_files = [f for f in os.listdir(qc_dir) if f.endswith('.tif')]
                    if qc_files:
                        log.append(f"✓ QC images: {len(qc_files)} files in qc/ subdirectory")
                
                if not output_files:
                    log.append(f"⚠ No output mask files found in {output_subdir}")
                    log.append(f"  Files present: {', '.join(all_files)}")
            
            except Exception as e:
                log.append(f"⚠ Could not check output files: {e}")
        else:
            attempted = ", ".join(candidate_names)
            log.append("⚠ Output subdirectory not found.")
            if attempted:
                log.append(f"  Tried: {attempted}")
            log.append(f"  Checking {output_dir_abs}...")
            if os.path.exists(output_dir_abs):
                files_in_output = os.listdir(output_dir_abs)
                log.append(f"  Files in output directory: {', '.join(files_in_output)}")

    except subprocess.CalledProcessError as e:
        log.append(f"✗ Error running S3segmenter: {e}")
        log.append(f"  Return Code: {e.returncode}")
        if e.stdout:
            log.append(f"\n  Stdout:\n{e.stdout}")
        if e.stderr:
            log.append(f"\n  Stderr:\n{e.stderr}")
        _raise_with_log(RuntimeError)
    except FileNotFoundError:
        log.append(f"✗ Error: Container runtime command not found. Please ensure {container_type} is installed and in your PATH.")
        _raise_with_log(FileNotFoundError)
    except Exception as e:
        log.append(f"✗ An unexpected error occurred: {e}")
        _raise_with_log(RuntimeError)

    log.append("\n## Conclusion")
    
    if output_files:
        log.append(f"✓ Cell segmentation completed successfully!")
        log.append(f"  Generated {len(output_files)} segmentation mask files")
        log.append(f"  Output location: {output_subdir}")
        log.append("\nGenerated files:")
        for f in output_files:
            log.append(f"  - {f}")
        log.append("\nThese segmentation masks can now be used for:")
        log.append("  1. Single-cell feature extraction and quantification")
        log.append("  2. Spatial analysis and cell-cell interaction studies")
        log.append("  3. Cell type classification and phenotyping")
        log.append("  4. Tissue architecture analysis")
    else:
        log.append("⚠ Segmentation may be incomplete.")
        log.append("  Please check the output directory and processing logs.")

    return "\n".join(log)


def batch_segment_cells(
    input_images: list[str],
    probability_maps_dirs: list[str],
    output_base_dir: str,
    crop_method: str = "noCrop",
    mask_type: str = "tissue",
    nuclei_region: str = "watershedContourInt",
    segment_cytoplasm: bool = False,
    cytoplasm_channels: list[int] | None = None,
    cyto_method: str = "distanceTransform",
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Segment cells for multiple images in batch.

    This function processes multiple microscopy images, performing watershed segmentation
    for each one using corresponding probability maps.

    Parameters
    ----------
    input_images : list of str
        List of input microscopy image file paths.
    probability_maps_dirs : list of str
        List of directories containing probability maps, corresponding to each input image.
        Must be same length as input_images.
    output_base_dir : str
        Base directory where output subdirectories will be created for each image.
    crop_method : str, optional
        Cropping method. (default: 'noCrop')
    mask_type : str, optional
        Type of tissue mask. (default: 'tissue')
    nuclei_region : str, optional
        Nuclei segmentation method. (default: 'watershedContourInt')
    segment_cytoplasm : bool, optional
        Whether to segment cytoplasm. (default: False)
    cytoplasm_channels : list of int, optional
        Cytoplasm marker channels (1-indexed). (default: None)
    cyto_method : str, optional
        Cytoplasm segmentation method. (default: 'distanceTransform')
    singularity_image : str, optional
        Path to the S3segmenter Singularity image file. (default: None)

    Returns
    -------
    str
        A research log summarizing the batch processing results for all images.
    """
    import os
    from datetime import datetime

    # Auto-detect Singularity image path if not provided
    if singularity_image is None:
        singularity_image = os.environ.get('S3SEGMENTER_SIF', 's3segmenter_latest.sif')

    log = []
    log.append(f"# Batch S3segmenter Cell Segmentation Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Validate input lists
    if len(input_images) != len(probability_maps_dirs):
        log.append(f"✗ Error: Number of input images ({len(input_images)}) does not match number of probability map directories ({len(probability_maps_dirs)})")
        return "\n".join(log)

    log.append("## Configuration")
    log.append(f"- Number of images: {len(input_images)}")
    log.append(f"- Output base directory: {output_base_dir}")
    log.append(f"- Crop method: {crop_method}")
    log.append(f"- Mask type: {mask_type}")
    log.append(f"- Nuclei region: {nuclei_region}")
    log.append(f"- Segment cytoplasm: {segment_cytoplasm}")
    if segment_cytoplasm and cytoplasm_channels:
        log.append(f"- Cytoplasm channels: {cytoplasm_channels}")
    log.append(f"- Singularity image: {singularity_image}")

    # Ensure output base directory exists
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
        log.append(f"\nCreated output base directory: {output_base_dir}")

    log.append("\n## Processing Images")

    successful_images = []
    failed_images = []

    for i, (input_image, pm_dir) in enumerate(zip(input_images, probability_maps_dirs), 1):
        log.append(f"\n### Image {i}/{len(input_images)}: {os.path.basename(input_image)}")

        if not os.path.isfile(input_image):
            log.append(f"✗ Input image not found: {input_image}")
            failed_images.append(input_image)
            continue

        if not os.path.isdir(pm_dir):
            log.append(f"✗ Probability maps directory not found: {pm_dir}")
            failed_images.append(input_image)
            continue

        # Process this image
        result = segment_cells(
            input_image=input_image,
            probability_maps_dir=pm_dir,
            output_dir=output_base_dir,
            crop_method=crop_method,
            mask_type=mask_type,
            nuclei_region=nuclei_region,
            segment_cytoplasm=segment_cytoplasm,
            cytoplasm_channels=cytoplasm_channels,
            cyto_method=cyto_method,
            singularity_image=singularity_image,
            container_runtime=container_runtime,
        )

        # Check if processing was successful
        if "✓ Cell segmentation completed successfully" in result or "✓ Segmentation completed successfully" in result:
            log.append(f"✓ Segmented successfully → {output_base_dir}")
            successful_images.append(input_image)
        else:
            log.append(f"✗ Segmentation failed")
            failed_images.append(input_image)

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
