"""
ASHLAR image stitching and registration tools.

This module provides wrapper functions for ASHLAR (Alignment by Simultaneous 
Harmonization of Layer/Adjacency Registration), a tool for fast, high-quality 
stitching of microscopy images and co-registration of multiple rounds of cyclic 
imaging for methods such as CyCIF and CODEX.
"""


def stitch_and_register_tiles_ashlar(
    input_files,
    output_path="ashlar_output.ome.tif",
    align_channel=0,
    maximum_shift=15,
    filter_sigma=None,
    tile_size=1024,
    ffp_files=None,
    dfp_files=None,
    flip_x=False,
    flip_y=False,
    output_dir="./",
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Stitch and register multi-tile microscopy images using ASHLAR.
    
    ASHLAR performs fast, high-quality stitching of microscopy images and co-registers
    multiple rounds of cyclic imaging for methods such as CyCIF and CODEX. It can read
    image data directly from BioFormats-supported microscope vendor file formats as well
    as plain TIFF files. Output is saved as pyramidal, tiled OME-TIFF.
    
    Parameters
    ----------
    input_files : list of str
        List of image file paths to be processed, one per cycle. Can be BioFormats-supported
        vendor formats or plain TIFF files.
    output_path : str, optional
        Output file path. If ends in .ome.tif, writes pyramidal OME-TIFF. 
        Default: "ashlar_output.ome.tif"
    align_channel : int, optional
        Reference channel number for image alignment. Numbering starts at 0. Default: 0
    maximum_shift : float, optional
        Maximum allowed per-tile corrective shift in microns. Default: 15
    filter_sigma : float, optional
        Filter images before alignment using Gaussian kernel with this standard deviation
        in pixels. Default: None (no filtering)
    tile_size : int, optional
        Pyramid tile size for OME-TIFF output. Default: 1024
    ffp_files : list of str, optional
        Flat field profile image file(s) for illumination correction. Specify one common
        file for all cycles or one per cycle. Default: None
    dfp_files : list of str, optional
        Dark field profile image file(s) for illumination correction. Specify one common
        file for all cycles or one per cycle. Default: None
    flip_x : bool, optional
        Flip tile positions left-to-right. Default: False
    flip_y : bool, optional
        Flip tile positions top-to-bottom. Default: False
    output_dir : str, optional
        Directory to save output files. Default: "./"
    singularity_image : str, optional
        Path to the ASHLAR Singularity/Apptainer image file (.sif).
        If not provided, will look for ASHLAR_SIF environment variable,
        or default to "ashlar_latest.sif" in current directory.
        Only used when container_runtime is 'apptainer' or 'singularity'.
        (default: None)
    container_runtime : str, optional
        Container runtime to use: 'auto', 'apptainer', 'singularity', or 'docker'.
        'auto' will detect available runtime (prefers apptainer/singularity over docker).
        (default: 'auto')
        
    Returns
    -------
    str
        Research log summarizing the stitching and registration process
        
    Examples
    --------
    >>> # Stitch tiles from a single cycle
    >>> log = stitch_and_register_tiles_ashlar(
    ...     input_files=['cycle1_tile1.tif', 'cycle1_tile2.tif'],
    ...     output_path='stitched.ome.tif'
    ... )
    
    >>> # Register multiple cycles with flat field correction
    >>> log = stitch_and_register_tiles_ashlar(
    ...     input_files=['cycle1.rcpnl', 'cycle2.rcpnl'],
    ...     ffp_files=['ffp.tif'],
    ...     align_channel=1,
    ...     maximum_shift=30
    ... )
    
    Notes
    -----
    - Requires unstitched individual "tile" images as input
    - Supports BioFormats-compatible vendor formats and plain TIFF
    - Output is pyramidal OME-TIFF for efficient viewing and analysis
    - This function requires Singularity to be installed
    """
    import os
    import subprocess
    import shlex
    import shutil
    from datetime import datetime
    
    # Initialize research log
    log = []
    log.append("# ASHLAR Image Stitching and Registration")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Detect container runtime
    container_type = None
    container_cmd = None
    docker_image = "labsyspharm/ashlar:latest"
    
    if container_runtime == "auto":
        # Try apptainer/singularity first, then docker
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
        log.append(f"  Please install one of: apptainer, singularity, or docker")
        return "\n".join(log)
    
    # For apptainer/singularity, check .sif file exists
    if container_type in ("apptainer", "singularity"):
        if singularity_image is None:
            singularity_image = os.environ.get('ASHLAR_SIF', 'ashlar_latest.sif')
        log.append(f"Using Singularity image: {singularity_image}")
        if not os.path.isfile(singularity_image):
            log.append(f"✗ Error: Singularity image not found: {singularity_image}")
            log.append(f"  Please pull it first: singularity pull docker://labsyspharm/ashlar:latest")
            return "\n".join(log)
    else:
        log.append(f"Using Docker image: {docker_image}")
    
    # Validate inputs
    if not input_files:
        log.append("✗ Error: No input files provided")
        return "\n".join(log)
    
    if not isinstance(input_files, list):
        input_files = [input_files]
    
    # Get absolute paths and check files exist
    input_files_abs = []
    missing_files = []
    for f in input_files:
        if not os.path.exists(f):
            missing_files.append(f)
        else:
            input_files_abs.append(os.path.abspath(f))
    
    if missing_files:
        log.append(f"✗ Error: Input files not found: {missing_files}")
        return "\n".join(log)
    
    # Create output directory if it doesn't exist
    output_dir_abs = os.path.abspath(output_dir)
    os.makedirs(output_dir_abs, exist_ok=True)
    
    # Get absolute path for output
    full_output_path = os.path.abspath(os.path.join(output_dir, output_path))
    
    # Collect all directories that need to be mounted
    mount_dirs = set()
    for f in input_files_abs:
        mount_dirs.add(os.path.dirname(f))
    mount_dirs.add(output_dir_abs)
    
    # Handle flat field and dark field profile files
    ffp_files_abs = []
    if ffp_files:
        if not isinstance(ffp_files, list):
            ffp_files = [ffp_files]
        for f in ffp_files:
            if os.path.exists(f):
                abs_path = os.path.abspath(f)
                ffp_files_abs.append(abs_path)
                mount_dirs.add(os.path.dirname(abs_path))
    
    dfp_files_abs = []
    if dfp_files:
        if not isinstance(dfp_files, list):
            dfp_files = [dfp_files]
        for f in dfp_files:
            if os.path.exists(f):
                abs_path = os.path.abspath(f)
                dfp_files_abs.append(abs_path)
                mount_dirs.add(os.path.dirname(abs_path))
    
    # Find common parent directory for bind mount
    all_paths = list(mount_dirs)
    if len(all_paths) == 1:
        common_parent = all_paths[0]
    else:
        common_parent = os.path.commonpath(all_paths)
    
    # Create relative paths for use inside container
    input_rel = [os.path.relpath(f, common_parent) for f in input_files_abs]
    output_rel = os.path.relpath(full_output_path, common_parent)
    
    log.append("## Input Parameters")
    log.append(f"- Number of input files: {len(input_files)}")
    log.append(f"- Output path: {output_path}")
    log.append(f"- Alignment channel: {align_channel}")
    log.append(f"- Maximum shift: {maximum_shift} microns")
    if filter_sigma:
        log.append(f"- Gaussian filter sigma: {filter_sigma} pixels")
    log.append(f"- Tile size: {tile_size} pixels")
    
    # Build the ashlar command based on container type
    if container_type == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{common_parent}:/data",
            docker_image,
            "ashlar"
        ]
    else:  # apptainer or singularity
        cmd = [
            container_cmd, "exec",
            "--bind", f"{common_parent}:/data",
            singularity_image,
            "ashlar"
        ]
    
    # Add input files (with /data prefix)
    for f_rel in input_rel:
        cmd.append(f"/data/{f_rel}")
    
    # Add output path
    cmd.extend(["-o", f"/data/{output_rel}"])
    
    # Add alignment channel
    cmd.extend(["-c", str(align_channel)])
    
    # Add maximum shift
    cmd.extend(["-m", str(maximum_shift)])
    
    # Add filter sigma if specified
    if filter_sigma is not None:
        cmd.extend(["--filter-sigma", str(filter_sigma)])
    
    # Add tile size
    cmd.extend(["--tile-size", str(tile_size)])
    
    # Add flat field profiles if specified
    if ffp_files_abs:
        ffp_rel = [os.path.relpath(f, common_parent) for f in ffp_files_abs]
        cmd.append("--ffp")
        for f_rel in ffp_rel:
            cmd.append(f"/data/{f_rel}")
        log.append(f"- Flat field profiles: {len(ffp_files_abs)} file(s)")
    
    # Add dark field profiles if specified
    if dfp_files_abs:
        dfp_rel = [os.path.relpath(f, common_parent) for f in dfp_files_abs]
        cmd.append("--dfp")
        for f_rel in dfp_rel:
            cmd.append(f"/data/{f_rel}")
        log.append(f"- Dark field profiles: {len(dfp_files_abs)} file(s)")
    
    # Add flip options
    if flip_x:
        cmd.append("--flip-x")
        log.append("- Flip X: enabled")
    if flip_y:
        cmd.append("--flip-y")
        log.append("- Flip Y: enabled")
    
    # Add quiet flag to reduce output
    cmd.append("-q")
    
    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}\n")
    
    # Run ASHLAR
    try:
        log.append("Running ASHLAR stitching and registration...")
        log.append("This may take several minutes to hours depending on image size and number of tiles...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        log.append("✓ ASHLAR completed successfully\n")
        
        # Log stdout if available
        if result.stdout:
            log.append("## ASHLAR Output")
            stdout_lines = result.stdout.strip().split('\n')
            # Show abbreviated output if very long
            if len(stdout_lines) > 30:
                log.append("Abbreviated output:")
                log.append('\n'.join(stdout_lines[:15]))
                log.append(f"\n... ({len(stdout_lines) - 20} lines omitted) ...\n")
                log.append('\n'.join(stdout_lines[-5:]))
            else:
                log.append(result.stdout)
        
        # Check output file exists
        if os.path.exists(full_output_path):
            file_size = os.path.getsize(full_output_path) / (1024**2)  # Size in MB
            log.append("\n## Results")
            log.append(f"✓ Output file: {full_output_path}")
            log.append(f"  File size: {file_size:.2f} MB")
        else:
            log.append("\n⚠ Warning: Output file not found at expected location")
            log.append(f"  Expected: {full_output_path}")
        
    except subprocess.CalledProcessError as e:
        log.append(f"\n✗ Error: ASHLAR failed with exit code {e.returncode}")
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
        return "\n".join(log)
    
    log.append("\n## Conclusion")
    log.append("Image stitching and registration completed successfully.")
    log.append(f"Registered image saved to: {full_output_path}")
    log.append("\nThe output OME-TIFF can be:")
    log.append("  - Viewed in ImageJ/Fiji, QuPath, or other OME-TIFF viewers")
    log.append("  - Used for downstream quantification and analysis")
    log.append("  - Imported into MCMICRO pipeline for further processing")
    
    return "\n".join(log)


def align_cyclic_images_ashlar(
    cycle_files,
    output_path="registered_cycles.ome.tif",
    align_channel=0,
    maximum_shift=30,
    output_dir="./",
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Align multiple rounds of cyclic imaging (e.g., CyCIF, CODEX) using ASHLAR.
    
    This is a simplified wrapper specifically for multi-cycle registration, which is
    common in cyclic immunofluorescence methods.
    
    Parameters
    ----------
    cycle_files : list of str
        List of image files, one per imaging cycle, in order
    output_path : str, optional
        Output OME-TIFF file path. Default: "registered_cycles.ome.tif"
    align_channel : int, optional
        Channel to use for alignment across cycles. Default: 0
    maximum_shift : float, optional
        Maximum shift between cycles in microns. Default: 30
    output_dir : str, optional
        Output directory. Default: "./"
    singularity_image : str, optional
        Path to the ASHLAR Singularity image file. (default: None)
    container_runtime : str, optional
        Container runtime: 'auto', 'apptainer', 'singularity', or 'docker'. (default: 'auto')
        
    Returns
    -------
    str
        Research log summarizing the registration
    """
    return stitch_and_register_tiles_ashlar(
        input_files=cycle_files,
        output_path=output_path,
        align_channel=align_channel,
        maximum_shift=maximum_shift,
        output_dir=output_dir,
        singularity_image=singularity_image,
        container_runtime=container_runtime,
    )


def stitch_microscopy_tiles_ashlar(
    tile_directory,
    output_path="stitched.ome.tif",
    file_pattern="*.tif",
    maximum_shift=15,
    filter_sigma=None,
    output_dir="./",
    singularity_image=None,
    container_runtime: str = "auto",
):
    """Stitch microscopy tiles from a directory using ASHLAR.
    
    Convenience function for stitching tiles from a single imaging round when
    all tiles are in one directory.
    
    Parameters
    ----------
    tile_directory : str
        Directory containing image tiles
    output_path : str, optional
        Output file name. Default: "stitched.ome.tif"
    file_pattern : str, optional
        Glob pattern to match tile files. Default: "*.tif"
    maximum_shift : float, optional
        Maximum corrective shift in microns. Default: 15
    filter_sigma : float, optional
        Gaussian filter sigma for pre-alignment filtering. Default: None
    output_dir : str, optional
        Output directory. Default: "./"
    singularity_image : str, optional
        Path to the ASHLAR Singularity image file. (default: None)
    container_runtime : str, optional
        Container runtime: 'auto', 'apptainer', 'singularity', or 'docker'. (default: 'auto')
        
    Returns
    -------
    str
        Research log
    """
    import glob
    import os
    
    # Find all matching files in directory
    pattern = os.path.join(tile_directory, file_pattern)
    tile_files = sorted(glob.glob(pattern))
    
    if not tile_files:
        return f"Error: No files matching pattern '{file_pattern}' found in {tile_directory}"
    
    return stitch_and_register_tiles_ashlar(
        input_files=tile_files,
        output_path=output_path,
        maximum_shift=maximum_shift,
        filter_sigma=filter_sigma,
        output_dir=output_dir,
        singularity_image=singularity_image,
        container_runtime=container_runtime,
    )

