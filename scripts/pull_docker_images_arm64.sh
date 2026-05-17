#!/bin/bash
# Pull all Docker images used by SP-Mind tools (ARM64).
# For Apple Silicon Macs and ARM64 Linux.
# For x86_64 (Intel/AMD), use pull_docker_images.sh instead.
# For HPC with Singularity/Apptainer, use pull_singularity_images.sh instead.

set -e

echo "Pulling Docker images for SP-Mind tools (ARM64)..."
echo "================================================"

IMAGES=(
    "labsyspharm/basic-illumination:latest"                    # basic_illumination.py
    "labsyspharm/ashlar:latest"                                # registration.py
    "tomyuanyucheng/unmicst:arm64"                             # segmentation_unmicst.py
    "tomyuanyucheng/s3segmenter:arm64"                         # segmentation_s3segmenter.py
    "tomyuanyucheng/mcquant:arm64"                             # quantification.py
    "tomyuanyucheng/scimap:arm64"                              # clustering.py
    "labsyspharm/unetcoreograph:2.4.3-arm"                    # unetcoreograph.py
    "ghcr.io/schapirolabor/background_subtraction:latest"      # background_subtraction.py
)

for image in "${IMAGES[@]}"; do
    echo ""
    echo "Pulling: $image"
    echo "----------------------------------------"
    if docker pull "$image"; then
        echo "OK: $image"
    else
        echo "FAILED: $image"
    fi
done

echo ""
echo "================================================"
echo "Done. Pulled images:"
echo ""
docker images | grep -E "labsyspharm|schapirolabor|tomyuanyucheng"
