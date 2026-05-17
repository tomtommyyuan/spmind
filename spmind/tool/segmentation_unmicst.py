"""
UnMicst nuclei probability map generation tools.

This module provides wrapper functions for UnMicst (Universal Models for Identifying 
Cells and Segmenting Tissue), a deep learning tool that generates probability maps for 
nuclei segmentation using UNet architecture. The probability maps can be used with 
downstream watershed algorithms for final cell segmentation.
"""


def generate_probability_maps(
    input_image: str,
    output_dir: str,
    channel: int = 1,
    model: str = "unmicst-solo",
    scaling_factor: float = 1.0,
    mean: float = -1.0,
    std: float = -1.0,
    stack_output: bool = True,
    gpu_id: int = -1,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Generate nuclei probability maps using UnMicst deep learning model.

    This function uses UnMicst to generate probability maps for nuclei segmentation.
    UnMicst separates nuclei foreground from background and identifies nuclei contours.
    The output probability maps can be used with watershed algorithms (e.g., S3segmenter)
    for final cell segmentation.

    The model has been trained on 7 diverse tissue types with various morphologies and
    includes real augmentations (defocused planes, saturated pixels) for robustness.

    Parameters
    ----------
    input_image : str
        Path to the input microscopy image file (TIF or OME-TIFF).
        Preferably flat-field corrected, minimal saturated pixels, and in focus.
        Model trained on images at 0.65 µm/px resolution.
    output_dir : str
        Directory where output probability maps will be saved.
        Will be created if it doesn't exist.
    channel : int, optional
        Channel number to use for inference (1-indexed).
        Usually the DNA/DAPI channel. (default: 1)
    model : str, optional
        Which UnMicst model to use:
        - 'unmicst-solo': DNA channel only (default, recommended)
        - 'unmicst-duo': DNA + nuclear envelope staining (lamin/nucleoporin)
        - 'unmicst-legacy': Older mouse model (deprecated)
        - 'UnMicstCyto2': Cytoplasm segmentation model
        (default: 'unmicst-solo')
    scaling_factor : float, optional
        Upsample/downsample factor if pixel size differs from 0.65 µm/px.
        For example, use 2.0 if your images are at 1.3 µm/px.
        (default: 1.0)
    mean : float, optional
        Mean intensity of input image for normalization.
        Use -1 to use model's default. (default: -1.0)
    std : float, optional
        Standard deviation of input image for normalization.
        Use -1 to use model's default. (default: -1.0)
    stack_output : bool, optional
        If True, saves probability maps as separate files (NucleiPM, ContoursPM).
        If False, saves as a single concatenated stack. (default: True)
    gpu_id : int, optional
        GPU device ID to use (0-indexed). Use -1 for CPU. (default: -1)
    singularity_image : str, optional
        Path to the UnMicst Singularity image file.
        If not provided, will look for UNMICST_SIF environment variable,
        or default to "unmicst_latest.sif" in current directory.
        Only used when container_runtime is 'apptainer' or 'singularity'.
        (default: None)
    container_runtime : str, optional
        Container runtime to use: 'auto', 'apptainer', 'singularity', or 'docker'.
        'auto' will detect available runtime (prefers apptainer/singularity over docker).
        (default: 'auto')

    Returns
    -------
    str
        A research log summarizing the probability map generation process and results.

    Notes
    -----
    - GPU is optional but significantly faster than CPU
    - Model performs best on images at 0.65 µm/px (adjust scaling_factor if needed)
    - Output files: <basename>_NucleiPM_<channel>.tif, <basename>_ContoursPM_<channel>.tif
    - For duo model, provide two channels (DNA and nuclear envelope)
    - Probability maps can be used with S3segmenter or similar tools for final segmentation

    Examples
    --------
    >>> # Generate probability maps from DNA channel
    >>> result = generate_probability_maps(
    ...     input_image="tissue_scan.ome.tif",
    ...     output_dir="./probability_maps",
    ...     channel=1,
    ...     model="unmicst-solo"
    ... )
    
    >>> # Use DNA + nuclear envelope (duo model)
    >>> result = generate_probability_maps(
    ...     input_image="tissue_scan.ome.tif",
    ...     output_dir="./probability_maps",
    ...     channel=1,  # First channel for DNA
    ...     model="unmicst-duo"
    ... )
    """
    import subprocess
    import os
    import shlex
    import shutil
    from datetime import datetime

    log = []
    
    def _raise_with_log(exception: type[Exception]) -> None:
        """Raise exception with the accumulated log."""
        raise exception("\n".join(log))

    log.append(f"# UnMicst Probability Map Generation Report")
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
        docker_image = "tomyuanyucheng/unmicst:arm64"
        log.append(f"Detected ARM64 platform ({machine}), using ARM-native image")
    else:
        docker_image = "labsyspharm/unmicst:latest"
    
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
            singularity_image = os.environ.get('UNMICST_SIF', 'unmicst_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/unmicst:latest")
            _raise_with_log(FileNotFoundError)
    else:
        log.append(f"Using Docker image: {docker_image}")

    # Validate inputs
    if not os.path.isfile(input_image):
        log.append(f"✗ Error: Input image not found: {input_image}")
        _raise_with_log(FileNotFoundError)

    # Validate model choice
    valid_models = ['unmicst-solo', 'unmicst-duo', 'unmicst-legacy', 'UnMicstCyto2']
    if model not in valid_models:
        log.append(f"✗ Error: Invalid model '{model}'. Choose from: {', '.join(valid_models)}")
        _raise_with_log(ValueError)

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
        ]
        # Add GPU support for Docker if gpu_id >= 0
        if gpu_id >= 0:
            cmd.extend(["--gpus", "all"])
        cmd.extend([
            docker_image,
            "python", "/app/unmicstWrapper.py",
            "--tool", model,
            f"/data/{input_rel}",
            "--outputPath", f"/data/{output_rel}",
            "--channel", str(channel),
            "--scalingFactor", str(scaling_factor),
            "--mean", str(mean),
            "--std", str(std),
            "--GPU", str(gpu_id + 1)  # unmicstWrapper uses 1-indexed GPU
        ])
    else:  # apptainer or singularity
        cmd = [
                container_cmd, "exec",
            "--nv",  # Enable GPU support
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "python", "/app/unmicstWrapper.py",
            "--tool", model,
            f"/data/{input_rel}",
            "--outputPath", f"/data/{output_rel}",
            "--channel", str(channel),
            "--scalingFactor", str(scaling_factor),
            "--mean", str(mean),
            "--std", str(std),
            "--GPU", str(gpu_id + 1)  # unmicstWrapper uses 1-indexed GPU
        ]

    # Add stack output flag if requested
    if not stack_output:
        cmd.append("--stackOutput")

    log.append("## Input Parameters")
    log.append(f"- Input image: {input_image}")
    log.append(f"- Output directory: {output_dir}")
    log.append(f"- Channel: {channel} (DNA/DAPI channel)")
    log.append(f"- Model: {model}")
    if model == 'unmicst-solo':
        log.append("  (DNA channel only - recommended for most tissues)")
    elif model == 'unmicst-duo':
        log.append("  (DNA + nuclear envelope staining)")
    log.append(f"- Scaling factor: {scaling_factor}x")
    if scaling_factor != 1.0:
        log.append(f"  ⚠ Adjusting for pixel size difference from 0.65 µm/px")
    log.append(f"- Mean/Std: {mean}/{std} {'(using model defaults)' if mean == -1 else '(custom)'}")
    log.append(f"- Stack output: {stack_output}")
    log.append(f"- GPU: {gpu_id} {'(CPU mode)' if gpu_id == -1 else ''}")
    log.append(f"- Singularity image: {singularity_image}")

    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}")

    try:
        log.append("Running UnMicst probability map generation...")
        log.append("This may take several minutes depending on image size...")
        if gpu_id >= 0:
            log.append("GPU acceleration enabled for faster processing.")
        
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log.append("✓ Probability map generation completed successfully")
        
        log.append("\n### Processing Output:")
        if process.stdout:
            # Parse output for key information
            stdout_lines = process.stdout.strip().split('\n')
            for line in stdout_lines:
                if 'Using GPU' in line or 'Model restored' in line or 'Inference' in line:
                    log.append(f"  {line}")
            
            # Show abbreviated output
            if len(stdout_lines) > 30:
                log.append("\nAbbreviated output (showing first and last 10 lines):")
                log.append('\n'.join(stdout_lines[:10]))
                log.append(f"\n... ({len(stdout_lines) - 20} lines omitted) ...\n")
                log.append('\n'.join(stdout_lines[-10:]))
            else:
                log.append("\nFull output:")
                log.append(process.stdout)
        
        if process.stderr:
            log.append("\n### Warnings/Messages:")
            # Filter out common non-critical warnings
            stderr_lines = process.stderr.strip().split('\n')
            critical_lines = [line for line in stderr_lines 
                             if not 'deprecated' in line.lower()
                             and not 'UserWarning' in line]
            if critical_lines:
                log.append('\n'.join(critical_lines))

        log.append("\n## Results")
        
        # Check for output files
        import time
        time.sleep(1)  # Brief pause for file system
        
        output_files = []
        stacked_files = []
        try:
            all_files = os.listdir(output_dir_abs)
            # Look for probability map files
            basename = os.path.splitext(os.path.basename(input_image))[0]
            if basename.lower().endswith('.ome'):
                basename = os.path.splitext(basename)[0]
            basename_lower = basename.lower()

            lowercase_map = {fname: fname.lower() for fname in all_files}

            def pick_files(keyword: str) -> list[str]:
                matches = [fname for fname, lower in lowercase_map.items() if keyword in lower]
                scoped = [fname for fname in matches if basename_lower in lowercase_map[fname]]
                return scoped or matches

            nuclei_pm = pick_files('nucleipm')
            contours_pm = pick_files('contourspm')
            probability_stacks = pick_files('probabilities')
            
            if nuclei_pm:
                log.append(f"✓ Nuclei probability map: {nuclei_pm[0]}")
                nuclei_path = os.path.join(output_dir_abs, nuclei_pm[0])
                log.append(f"  File size: {os.path.getsize(nuclei_path) / (1024*1024):.2f} MB")
                output_files.extend(nuclei_pm)
            else:
                log.append(f"⚠ Nuclei probability map not found")
            
            if contours_pm:
                log.append(f"✓ Contours probability map: {contours_pm[0]}")
                contours_path = os.path.join(output_dir_abs, contours_pm[0])
                log.append(f"  File size: {os.path.getsize(contours_path) / (1024*1024):.2f} MB")
                output_files.extend(contours_pm)
            else:
                log.append(f"⚠ Contours probability map not found")

            if probability_stacks:
                log.append(f"✓ Combined probability map stack: {probability_stacks[0]}")
                stack_path = os.path.join(output_dir_abs, probability_stacks[0])
                log.append(f"  File size: {os.path.getsize(stack_path) / (1024*1024):.2f} MB")
                stacked_files.extend(probability_stacks)
                if not (nuclei_pm and contours_pm):
                    log.append("  Note: Only stacked probabilities detected. Rerun with stack_output=False to generate separate NucleiPM and ContoursPM files required by downstream tools.")
            
            # Check for QC directory
            qc_dir = os.path.join(output_dir_abs, 'qc')
            if os.path.exists(qc_dir):
                qc_files = os.listdir(qc_dir)
                if qc_files:
                    log.append(f"✓ QC files: {len(qc_files)} files in qc/ subdirectory")
            
            # Calculate total output size
            if output_files:
                total_size = sum(
                    os.path.getsize(os.path.join(output_dir_abs, f))
                    for f in output_files
                )
                log.append(f"\n  Total output size: {total_size / (1024*1024):.2f} MB")
            elif stacked_files:
                total_size = sum(
                    os.path.getsize(os.path.join(output_dir_abs, f))
                    for f in stacked_files
                )
                log.append(f"\n  Total stacked output size: {total_size / (1024*1024):.2f} MB")
        
        except Exception as e:
            log.append(f"⚠ Could not check output files: {e}")

    except subprocess.CalledProcessError as e:
        log.append(f"✗ Error running UnMicst: {e}")
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
        log.append(f"✓ Probability map generation completed successfully!")
        log.append(f"  Generated {len(output_files)} probability map files")
        log.append(f"  Output saved to: {output_dir}")
        log.append("\nGenerated files:")
        for f in output_files:
            log.append(f"  - {f}")
        if stacked_files:
            log.append("\nAdditional combined probability map stacks:")
            for f in stacked_files:
                log.append(f"  - {f}")
        log.append("\nThese probability maps can now be used for:")
        log.append("  1. Watershed segmentation (e.g., S3segmenter)")
        log.append("  2. Instance segmentation with deep learning models")
        log.append("  3. Cell counting and analysis")
        log.append("  4. Quality control and manual curation")
    elif stacked_files:
        log.append("⚠ Only combined probability stack generated.")
        log.append("  Rerun with stack_output=False to produce separate NucleiPM and ContoursPM files required by S3segmenter.")
        log.append(f"  Output saved to: {output_dir}")
        log.append("\nGenerated stack files:")
        for f in stacked_files:
            log.append(f"  - {f}")
    else:
        log.append("⚠ Probability map generation may be incomplete.")
        log.append("  Please check the output directory and processing logs.")

    return "\n".join(log)


def batch_generate_probability_maps(
    input_images: list[str],
    output_base_dir: str,
    channel: int = 1,
    model: str = "unmicst-solo",
    scaling_factor: float = 1.0,
    mean: float = -1.0,
    std: float = -1.0,
    stack_output: bool = True,
    gpu_id: int = -1,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Generate probability maps for multiple images in batch.

    This function processes multiple microscopy images, generating nuclei probability
    maps for each one using UnMicst.

    Parameters
    ----------
    input_images : list of str
        List of input microscopy image file paths.
    output_base_dir : str
        Base directory where output subdirectories will be created for each image.
        Each image will get its own subdirectory.
    channel : int, optional
        Channel number to use for inference (1-indexed). (default: 1)
    model : str, optional
        Which UnMicst model to use. (default: 'unmicst-solo')
    scaling_factor : float, optional
        Upsample/downsample factor for pixel size differences. (default: 1.0)
    mean : float, optional
        Mean intensity for normalization. (default: -1.0)
    std : float, optional
        Standard deviation for normalization. (default: -1.0)
    stack_output : bool, optional
        Save as separate probability map files. (default: True)
    gpu_id : int, optional
        GPU device ID to use. (default: 0)
    singularity_image : str, optional
        Path to the UnMicst Singularity image file. (default: None)

    Returns
    -------
    str
        A research log summarizing the batch processing results for all images.
    """
    import os
    from datetime import datetime

    # Auto-detect Singularity image path if not provided
    if singularity_image is None:
        singularity_image = os.environ.get('UNMICST_SIF', 'unmicst_latest.sif')

    log = []
    log.append(f"# Batch UnMicst Probability Map Generation Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    log.append("## Configuration")
    log.append(f"- Number of images: {len(input_images)}")
    log.append(f"- Output base directory: {output_base_dir}")
    log.append(f"- Channel: {channel}")
    log.append(f"- Model: {model}")
    log.append(f"- Scaling factor: {scaling_factor}")
    log.append(f"- GPU: {gpu_id}")
    log.append(f"- Singularity image: {singularity_image}")

    # Ensure output base directory exists
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
        log.append(f"\nCreated output base directory: {output_base_dir}")

    log.append("\n## Processing Images")

    successful_images = []
    failed_images = []

    for i, input_image in enumerate(input_images, 1):
        log.append(f"\n### Image {i}/{len(input_images)}: {os.path.basename(input_image)}")

        if not os.path.isfile(input_image):
            log.append(f"✗ Input image not found: {input_image}")
            failed_images.append(input_image)
            continue

        # Create output directory for this image
        image_basename = os.path.splitext(os.path.basename(input_image))[0]
        output_dir = os.path.join(output_base_dir, image_basename)

        # Process this image
        result = generate_probability_maps(
            input_image=input_image,
            output_dir=output_dir,
            channel=channel,
            model=model,
            scaling_factor=scaling_factor,
            mean=mean,
            std=std,
            stack_output=stack_output,
            gpu_id=gpu_id,
            singularity_image=singularity_image,
            container_runtime=container_runtime,
        )

        # Check if processing was successful
        if "✓ Probability map generation completed successfully" in result:
            log.append(f"✓ Generated probability maps → {output_dir}")
            successful_images.append(input_image)
        else:
            log.append(f"✗ Probability map generation failed")
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
