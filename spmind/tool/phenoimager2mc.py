"""
PhenoImager to MCMICRO conversion tools.

This module provides wrapper functions for phenoimager2mc, a tool that formats
PhenoImager .tif output files to be compatible with the MCMICRO pipeline and ASHLAR.
"""


def convert_phenoimager_to_mcmicro(
    input_dir: str,
    output_path: str,
    num_markers: int,
    normalization: str = "99th",
    cycle: int | None = None,
) -> str:
    """Convert PhenoImager .tif files to MCMICRO-compatible OME-TIFF format.

    The PhenoImager software outputs one float32 .tif file per tile and cycle
    containing all channels. This function converts them to stacked OME-TIFF files
    that are compatible with ASHLAR and the MCMICRO pipeline.

    Conversion steps performed:
    - Extraction of metadata from unstandardized tif files
    - Creation of stacked and correct ome-tiff files readable for ASHLAR
    - Conversion from float32 to uint16
    - Normalization to max or 99th percentile (user's choice)

    Parameters
    ----------
    input_dir : str
        Path to the folder containing all .tif files from one cycle.
    output_path : str
        Output .tif file path for the converted OME-TIFF containing all tiles and channels.
    num_markers : int
        The number of markers that was used in this cycle.
    normalization : str, optional
        Normalization method for intensities per cycle. Either "99th" or "max".
        (default: "99th")
    cycle : int, optional
        Cycle number for metadata. If not provided, will be inferred from input files.
        (default: None)

    Returns
    -------
    str
        A research log summarizing the PhenoImager to MCMICRO conversion process and results.
    """
    import subprocess
    import os
    import shlex
    from datetime import datetime

    log = []
    log.append(f"# PhenoImager to MCMICRO Conversion Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Validate normalization method
    if normalization not in ["99th", "max"]:
        log.append(f"✗ Error: Invalid normalization method '{normalization}'. Must be '99th' or 'max'.")
        return "\n".join(log)

    # Ensure input directory exists
    if not os.path.isdir(input_dir):
        log.append(f"✗ Error: Input directory not found: {input_dir}")
        return "\n".join(log)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log.append(f"Created output directory: {output_dir}")

    # Build the phenoimager2mc command
    cmd = ["phenoimager2mc.py"]
    cmd.extend(["-i", input_dir])
    cmd.extend(["-o", output_path])
    cmd.extend(["-m", str(num_markers)])
    cmd.extend(["-n", normalization])

    log.append("\n## Input Parameters")
    log.append(f"- Input directory: {input_dir}")
    log.append(f"- Output path: {output_path}")
    log.append(f"- Number of markers: {num_markers}")
    log.append(f"- Normalization method: {normalization}")
    if cycle is not None:
        log.append(f"- Cycle: {cycle}")

    log.append("\n## Processing")
    full_command = shlex.join(cmd)
    log.append(f"Command: {full_command}")

    try:
        log.append("Running PhenoImager to MCMICRO conversion...")
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log.append("✓ Conversion completed successfully")
        log.append("\n### Standard Output:")
        log.append(process.stdout)
        if process.stderr:
            log.append("\n### Standard Error:")
            log.append(process.stderr)

        log.append("\n## Results")
        if os.path.exists(output_path):
            log.append(f"- Output file: {output_path}")
            log.append(f"- File size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
        else:
            log.append(f"✗ Output file not found at {output_path}")

    except subprocess.CalledProcessError as e:
        log.append(f"✗ Error running phenoimager2mc: {e}")
        log.append(f"  Return Code: {e.returncode}")
        log.append(f"  Stdout: {e.stdout}")
        log.append(f"  Stderr: {e.stderr}")
        return "\n".join(log)
    except FileNotFoundError:
        log.append(f"✗ Error: 'phenoimager2mc.py' command not found. Please ensure phenoimager2mc is installed and in your PATH.")
        return "\n".join(log)
    except Exception as e:
        log.append(f"✗ An unexpected error occurred: {e}")
        return "\n".join(log)

    log.append("\n## Conclusion")
    log.append("PhenoImager to MCMICRO conversion completed successfully.")
    log.append("The output OME-TIFF is now compatible with ASHLAR and MCMICRO pipeline.")

    return "\n".join(log)


def batch_convert_phenoimager_cycles(
    input_base_dir: str,
    output_base_dir: str,
    cycles: list[int],
    num_markers: int,
    normalization: str = "99th",
    cycle_dir_pattern: str = "cycle_{cycle}",
    output_filename_pattern: str = "cycle_{cycle}.ome.tif",
) -> str:
    """Batch convert multiple PhenoImager cycles to MCMICRO-compatible format.

    This function processes multiple cycles of PhenoImager data, converting each
    cycle's .tif files into a single MCMICRO-compatible OME-TIFF file.

    Parameters
    ----------
    input_base_dir : str
        Base directory containing cycle subdirectories with .tif files.
    output_base_dir : str
        Base directory where converted OME-TIFF files will be saved.
    cycles : list of int
        List of cycle numbers to process.
    num_markers : int
        The number of markers used in each cycle.
    normalization : str, optional
        Normalization method for intensities. Either "99th" or "max".
        (default: "99th")
    cycle_dir_pattern : str, optional
        Pattern for cycle directory names. Use {cycle} as placeholder.
        (default: "cycle_{cycle}")
    output_filename_pattern : str, optional
        Pattern for output filenames. Use {cycle} as placeholder.
        (default: "cycle_{cycle}.ome.tif")

    Returns
    -------
    str
        A research log summarizing the batch conversion process and results for all cycles.
    """
    import os
    from datetime import datetime

    log = []
    log.append(f"# Batch PhenoImager to MCMICRO Conversion Report")
    log.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    log.append("## Configuration")
    log.append(f"- Input base directory: {input_base_dir}")
    log.append(f"- Output base directory: {output_base_dir}")
    log.append(f"- Cycles to process: {cycles}")
    log.append(f"- Number of markers: {num_markers}")
    log.append(f"- Normalization method: {normalization}")

    # Ensure output base directory exists
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
        log.append(f"\nCreated output base directory: {output_base_dir}")

    log.append("\n## Processing Cycles")

    successful_cycles = []
    failed_cycles = []

    for cycle in cycles:
        log.append(f"\n### Cycle {cycle}")

        # Construct input and output paths
        cycle_dir_name = cycle_dir_pattern.format(cycle=cycle)
        input_dir = os.path.join(input_base_dir, cycle_dir_name)

        output_filename = output_filename_pattern.format(cycle=cycle)
        output_path = os.path.join(output_base_dir, output_filename)

        if not os.path.isdir(input_dir):
            log.append(f"✗ Input directory not found: {input_dir}")
            failed_cycles.append(cycle)
            continue

        # Convert this cycle
        result = convert_phenoimager_to_mcmicro(
            input_dir=input_dir,
            output_path=output_path,
            num_markers=num_markers,
            normalization=normalization,
            cycle=cycle,
        )

        # Check if conversion was successful
        if "✓ Conversion completed successfully" in result:
            log.append(f"✓ Cycle {cycle} converted successfully → {output_path}")
            successful_cycles.append(cycle)
        else:
            log.append(f"✗ Cycle {cycle} conversion failed")
            failed_cycles.append(cycle)
            # Include the detailed error log
            log.append("\nDetailed error log:")
            log.append(result)

    log.append("\n## Summary")
    log.append(f"- Total cycles: {len(cycles)}")
    log.append(f"- Successful: {len(successful_cycles)} {successful_cycles}")
    log.append(f"- Failed: {len(failed_cycles)} {failed_cycles}")

    if len(successful_cycles) == len(cycles):
        log.append("\n✓ All cycles converted successfully!")
    elif len(successful_cycles) > 0:
        log.append("\n⚠ Some cycles converted successfully, but some failed.")
    else:
        log.append("\n✗ All cycles failed to convert.")

    return "\n".join(log)

