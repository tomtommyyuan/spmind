#!/bin/bash
# Pull all Singularity/Apptainer images used by SP-Mind tools.
# For HPC environments with Singularity or Apptainer.
# For Mac/Linux workstations with Docker, use pull_docker_images.sh instead.
#
# Usage:
#   bash scripts/pull_singularity_images.sh [output_dir]
#
# Images are saved to output_dir (default: ./simg/).
# After pulling, set the paths in your .env file (see .env.example).

set -e

OUTPUT_DIR="${1:-./simg}"
mkdir -p "$OUTPUT_DIR"

echo "Pulling Singularity images for SP-Mind tools..."
echo "Output directory: $OUTPUT_DIR"
echo "================================================"

# Detect runtime
if command -v apptainer &> /dev/null; then
    RUNTIME="apptainer"
elif command -v singularity &> /dev/null; then
    RUNTIME="singularity"
else
    echo "ERROR: Neither apptainer nor singularity found in PATH."
    exit 1
fi
echo "Using runtime: $RUNTIME"
echo ""

# image_name -> docker_uri
declare -A IMAGES=(
    ["ashlar_latest.sif"]="docker://labsyspharm/ashlar:latest"
    ["basic-illumination_latest.sif"]="docker://labsyspharm/basic-illumination:latest"
    ["background_subtraction_latest.sif"]="docker://ghcr.io/schapirolabor/background_subtraction:latest"
    ["unetcoreograph_latest.sif"]="docker://labsyspharm/unetcoreograph:latest"
    ["unmicst_latest.sif"]="docker://labsyspharm/unmicst:latest"
    ["s3segmenter_latest.sif"]="docker://labsyspharm/s3segmenter:latest"
    ["quantification_latest.sif"]="docker://labsyspharm/mcquant:latest"
    ["scimap_latest.sif"]="docker://labsyspharm/scimap:latest"
)

for sif_name in "${!IMAGES[@]}"; do
    uri="${IMAGES[$sif_name]}"
    dest="$OUTPUT_DIR/$sif_name"

    echo "Pulling: $uri"
    echo "    -> $dest"
    if $RUNTIME pull "$dest" "$uri"; then
        echo "OK: $sif_name"
    else
        echo "FAILED: $sif_name"
    fi
    echo ""
done

echo "================================================"
echo "Done. Images saved to: $OUTPUT_DIR"
echo ""
ls -lh "$OUTPUT_DIR"/*.sif 2>/dev/null
echo ""
echo "Add the following to your .env file:"
echo ""
echo "  SIMG_DIR=$(cd "$OUTPUT_DIR" && pwd)"
echo "  ASHLAR_SIF=\$SIMG_DIR/ashlar_latest.sif"
echo "  BASIC_ILLUMINATION_SIF=\$SIMG_DIR/basic-illumination_latest.sif"
echo "  BACKGROUND_SUBTRACTION_SIF=\$SIMG_DIR/background_subtraction_latest.sif"
echo "  UNETCOREOGRAPH_SIF=\$SIMG_DIR/unetcoreograph_latest.sif"
echo "  UNMICST_SIF=\$SIMG_DIR/unmicst_latest.sif"
echo "  S3SEGMENTER_SIF=\$SIMG_DIR/s3segmenter_latest.sif"
echo "  MCQUANT_SIF=\$SIMG_DIR/quantification_latest.sif"
echo "  SCIMAP_SIF=\$SIMG_DIR/scimap_latest.sif"
