"""
BaSiC illumination correction profile generation tools.

This module provides wrapper functions for basic-illumination, a tool that generates
flat-field and dark-field correction profiles using the BaSiC (Bayesian Shading Correction)
algorithm. These profiles are used by ASHLAR for illumination correction during image stitching.
"""


def generate_illumination_profiles(
    input_image: str,
    output_dir: str,
    experiment_name: str | None = None,
    lambda_flat: float = 0.1,
    lambda_dark: float = 0.01,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Generate flat-field and dark-field illumination correction profiles using BaSiC.

    This function uses the BaSiC (Bayesian Shading Correction) algorithm implemented
    in ImageJ/Fiji to compute illumination correction profiles from microscopy images.
    The output profiles can be used with ASHLAR to correct for uneven illumination
    during image stitching.

    The BaSiC algorithm analyzes the image stack to identify:
    - Flat-field (FFP): Captures uneven illumination patterns
    - Dark-field (DFP): Captures camera baseline signal/noise

    Parameters
    ----------
    input_image : str
        Path to the input microscopy image file (e.g., OME-TIFF).
        Must be a BioFormats-compatible file format.
    output_dir : str
        Directory where output profiles will be saved.
        Must exist before calling this function.
    experiment_name : str, optional
        Base name for output files. If not provided, will be derived from input filename.
        Output files will be named: {experiment_name}-ffp.tif and {experiment_name}-dfp.tif
    lambda_flat : float, optional
        Flat-field smoothing parameter. Set to 0 for automatic estimation.
        (default: 0.1)
    lambda_dark : float, optional
        Dark-field smoothing parameter. Set to 0 for automatic estimation.
        (default: 0.01)
    singularity_image : str, optional
        Path to Singularity image file, or Docker image name for Docker runtime.
        If not provided, will auto-detect based on container_runtime.
        (default: None)
    container_runtime : str, optional
        Container runtime to use: 'auto' (detect), 'docker', 'singularity', or 'apptainer'.
        'auto' will try Docker first (for Mac compatibility), then singularity/apptainer.
        (default: 'auto')

    Returns
    -------
    str
        A research log summarizing the illumination profile generation process and results.

    Notes
    -----
    - Both lambda_flat and lambda_dark must be zero (automatic), or both non-zero (manual).
    - Supports Docker (recommended for Mac) or Singularity/Apptainer (for HPC).
    - The input image must be accessible from within the container.
    """
    import subprocess
    import os
    import shlex
    import shutil
    from datetime import datetime

    log = []
    log.append(f"# BaSiC Illumination Profile Generation Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Validate lambda parameters
    if (lambda_flat == 0) ^ (lambda_dark == 0):
        log.append("✗ Error: Both lambda_flat and lambda_dark must be zero (automatic), or both non-zero (manual).")
        return "\n".join(log)

    # Ensure input file exists
    if not os.path.isfile(input_image):
        log.append(f"✗ Error: Input image not found: {input_image}")
        return "\n".join(log)

    # Ensure output directory exists
    if not os.path.isdir(output_dir):
        log.append(f"✗ Error: Output directory not found: {output_dir}")
        log.append(f"  Please create it first: mkdir -p {output_dir}")
        return "\n".join(log)

    # Derive experiment name from filename if not provided
    if experiment_name is None:
        experiment_name = os.path.splitext(os.path.basename(input_image))[0]

    # Get absolute paths for bind mounting
    input_image_abs = os.path.abspath(input_image)
    output_dir_abs = os.path.abspath(output_dir)

    # Determine parent directory for bind mount
    input_dir = os.path.dirname(input_image_abs)
    common_parent = os.path.commonpath([input_dir, output_dir_abs])
    input_rel = os.path.relpath(input_image_abs, common_parent)
    output_rel = os.path.relpath(output_dir_abs, common_parent)

    # Detect container runtime
    docker_image = "labsyspharm/basic-illumination"
    runtime = None
    
    if container_runtime == "auto":
        # Try Docker first (better for Mac), then singularity/apptainer
        if shutil.which("docker"):
            runtime = "docker"
        elif shutil.which("apptainer"):
            runtime = "apptainer"
        elif shutil.which("singularity"):
            runtime = "singularity"
    elif container_runtime == "docker":
        runtime = "docker" if shutil.which("docker") else None
    elif container_runtime in ["singularity", "apptainer"]:
        runtime = container_runtime if shutil.which(container_runtime) else None
    else:
        runtime = container_runtime
    
    if runtime is None:
        log.append("✗ Error: No container runtime found.")
        log.append("  For Mac: Install Docker Desktop and run: docker pull labsyspharm/basic-illumination")
        log.append("  For HPC: Ensure singularity/apptainer is in PATH")
        return "\n".join(log)
    
    log.append(f"Using container runtime: {runtime}")

    # Build command based on runtime
    if runtime == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{common_parent}:/data",
            docker_image,
            "ImageJ-linux64", "--ij2", "--headless",
            "--run", "/opt/fiji/imagej_basic_ashlar.py",
            f"filename='/data/{input_rel}',output_dir='/data/{output_rel}/',experiment_name='{experiment_name}',lambda_flat={lambda_flat},lambda_dark={lambda_dark}"
        ]
        container_image = docker_image
    else:
        # Singularity/Apptainer
        if singularity_image is None:
            singularity_image = os.environ.get('BASIC_ILLUMINATION_SIF', 'basic-illumination_latest.sif')
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it: singularity pull docker://labsyspharm/basic-illumination")
            return "\n".join(log)
        cmd = [
            runtime, "exec",
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "ImageJ-linux64", "--ij2", "--headless",
            "--run", "/opt/fiji/imagej_basic_ashlar.py",
            f"filename='/data/{input_rel}',output_dir='/data/{output_rel}/',experiment_name='{experiment_name}',lambda_flat={lambda_flat},lambda_dark={lambda_dark}"
        ]
        container_image = singularity_image

    log.append("## Input Parameters")
    log.append(f"- Input image: {input_image}")
    log.append(f"- Output directory: {output_dir}")
    log.append(f"- Experiment name: {experiment_name}")
    log.append(f"- Lambda flat: {lambda_flat} {'(automatic)' if lambda_flat == 0 else '(manual)'}")
    log.append(f"- Lambda dark: {lambda_dark} {'(automatic)' if lambda_dark == 0 else '(manual)'}")
    log.append(f"- Container image: {container_image}")

    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}")

    try:
        log.append("Running BaSiC illumination profile generation...")
        log.append("This may take several minutes depending on image size...")
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log.append("✓ BaSiC completed successfully")
        
        log.append("\n### ImageJ Output:")
        if process.stdout:
            log.append(process.stdout)
        if process.stderr:
            log.append("\n### Warnings/Errors:")
            log.append(process.stderr)

        log.append("\n## Results")
        ffp_path = os.path.join(output_dir, f"{experiment_name}-ffp.tif")
        dfp_path = os.path.join(output_dir, f"{experiment_name}-dfp.tif")
        
        if os.path.exists(ffp_path):
            log.append(f"✓ Flat-field profile: {ffp_path}")
            log.append(f"  File size: {os.path.getsize(ffp_path) / (1024*1024):.2f} MB")
        else:
            log.append(f"✗ Flat-field profile not found at {ffp_path}")
        
        if os.path.exists(dfp_path):
            log.append(f"✓ Dark-field profile: {dfp_path}")
            log.append(f"  File size: {os.path.getsize(dfp_path) / (1024*1024):.2f} MB")
        else:
            log.append(f"✗ Dark-field profile not found at {dfp_path}")

    except subprocess.CalledProcessError as e:
        log.append(f"✗ Error running BaSiC: {e}")
        log.append(f"  Return Code: {e.returncode}")
        if e.stdout:
            log.append(f"  Stdout: {e.stdout}")
        if e.stderr:
            log.append(f"  Stderr: {e.stderr}")
        return "\n".join(log)
    except FileNotFoundError:
        log.append(f"✗ Error: 'singularity' command not found. Please ensure Singularity is installed and in your PATH.")
        return "\n".join(log)
    except Exception as e:
        log.append(f"✗ An unexpected error occurred: {e}")
        return "\n".join(log)

    log.append("\n## Conclusion")
    log.append("Illumination profile generation completed successfully.")
    log.append("These profiles can now be used with ASHLAR for illumination correction:")
    log.append(f"  ashlar input.tif --ffp {ffp_path} --dfp {dfp_path} -o output.ome.tif")

    return "\n".join(log)


def batch_generate_illumination_profiles(
    input_images: list[str],
    output_dir: str,
    lambda_flat: float = 0.1,
    lambda_dark: float = 0.01,
    singularity_image: str | None = None,
    container_runtime: str = "auto",
) -> str:
    """Generate illumination profiles for multiple microscopy images in batch.

    This function processes multiple microscopy images, generating flat-field and
    dark-field correction profiles for each one using the BaSiC algorithm.

    Parameters
    ----------
    input_images : list of str
        List of input microscopy image file paths.
    output_dir : str
        Directory where all output profiles will be saved.
        Must exist before calling this function.
    lambda_flat : float, optional
        Flat-field smoothing parameter. Set to 0 for automatic estimation.
        (default: 0.1)
    lambda_dark : float, optional
        Dark-field smoothing parameter. Set to 0 for automatic estimation.
        (default: 0.01)
    singularity_image : str, optional
        Path to the basic-illumination Singularity image file.
        If not provided, will look for BASIC_ILLUMINATION_SIF environment variable,
        or default to "basic-illumination_latest.sif" in current directory.
        (default: None)
    container_runtime : str, optional
        Container runtime: 'auto', 'docker', 'singularity', or 'apptainer'.
        (default: 'auto')

    Returns
    -------
    str
        A research log summarizing the batch processing results for all images.
    """
    import os
    from datetime import datetime
    
    # Auto-detect Singularity image path if not provided
    if singularity_image is None:
        singularity_image = os.environ.get('BASIC_ILLUMINATION_SIF', 'basic-illumination_latest.sif')

    log = []
    log.append(f"# Batch BaSiC Illumination Profile Generation Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    log.append("## Configuration")
    log.append(f"- Number of images: {len(input_images)}")
    log.append(f"- Output directory: {output_dir}")
    log.append(f"- Lambda flat: {lambda_flat}")
    log.append(f"- Lambda dark: {lambda_dark}")
    log.append(f"- Singularity image: {singularity_image}")

    # Ensure output directory exists
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
        log.append(f"\nCreated output directory: {output_dir}")

    log.append("\n## Processing Images")

    successful_images = []
    failed_images = []

    for i, input_image in enumerate(input_images, 1):
        log.append(f"\n### Image {i}/{len(input_images)}: {os.path.basename(input_image)}")

        if not os.path.isfile(input_image):
            log.append(f"✗ Input image not found: {input_image}")
            failed_images.append(input_image)
            continue

        # Derive experiment name from filename
        experiment_name = os.path.splitext(os.path.basename(input_image))[0]

        # Generate profiles for this image
        result = generate_illumination_profiles(
            input_image=input_image,
            output_dir=output_dir,
            experiment_name=experiment_name,
            lambda_flat=lambda_flat,
            lambda_dark=lambda_dark,
            singularity_image=singularity_image,
            container_runtime=container_runtime,
        )

        # Check if generation was successful
        if "✓ BaSiC completed successfully" in result:
            log.append(f"✓ Profiles generated successfully")
            successful_images.append(input_image)
        else:
            log.append(f"✗ Profile generation failed")
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