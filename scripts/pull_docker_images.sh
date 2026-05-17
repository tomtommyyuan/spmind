#!/bin/bash
# Pull all Docker images used by SP-Mind tools (x86_64).
# For Linux and Mac (Intel) workstations with Docker installed.
# For ARM64 (Apple Silicon), use pull_docker_images_arm64.sh instead.
# For HPC with Singularity/Apptainer, use pull_singularity_images.sh instead.

set -e

echo "Pulling Docker images for SP-Mind tools (x86_64)..."
echo "================================================"

IMAGES=(
    "labsyspharm/basic-illumination:latest"                    # basic_illumination.py
    "labsyspharm/ashlar:latest"                                # registration.py
    "labsyspharm/unmicst:latest"                               # segmentation_unmicst.py
    "labsyspharm/s3segmenter:latest"                           # segmentation_s3segmenter.py
    "labsyspharm/mcquant:latest"                               # quantification.py
    "labsyspharm/scimap:latest"                                # clustering.py
    "labsyspharm/unetcoreograph:latest"                        # unetcoreograph.py
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
docker images | grep -E "labsyspharm|schapirolabor"
