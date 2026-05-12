"""
Tool descriptions for UnMicst nuclei probability map generation functions.
"""

description = [
    {
        "name": "generate_probability_maps",
        "description": "Generate nuclei probability maps using UnMicst (Universal Models for Identifying Cells and Segmenting Tissue), a deep learning tool based on UNet architecture. UnMicst generates probability maps for nuclei segmentation by identifying nuclei foreground/background and nuclei contours. The model has been trained on 7 diverse tissue types and includes real augmentations for robustness. Output probability maps can be used with watershed algorithms (e.g., S3segmenter) or other segmentation tools for final cell segmentation. Model trained on images at 0.65 micron/pixel resolution.",
        "required_parameters": [
            {
                "name": "input_image",
                "type": "str",
                "default": None,
                "description": "Path to the input microscopy image file (TIF or OME-TIFF). Preferably flat-field corrected, minimal saturated pixels, and in focus. Model trained on images at 0.65 µm/px resolution."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": None,
                "description": "Directory where output probability maps will be saved. Will be created if it doesn't exist. Output includes NucleiPM (nuclei foreground) and ContoursPM (nuclei boundaries) files."
            }
        ],
        "optional_parameters": [
            {
                "name": "channel",
                "type": "int",
                "default": 1,
                "description": "Channel number to use for inference (1-indexed). Usually the DNA/DAPI channel."
            },
            {
                "name": "model",
                "type": "str",
                "default": "unmicst-solo",
                "description": "Which UnMicst model to use: 'unmicst-solo' (DNA channel only, recommended), 'unmicst-duo' (DNA + nuclear envelope staining), 'unmicst-legacy' (older mouse model, deprecated), or 'UnMicstCyto2' (cytoplasm segmentation)."
            },
            {
                "name": "scaling_factor",
                "type": "float",
                "default": 1.0,
                "description": "Upsample/downsample factor if pixel size differs from 0.65 µm/px. For example, use 2.0 if your images are at 1.3 µm/px."
            },
            {
                "name": "mean",
                "type": "float",
                "default": -1.0,
                "description": "Mean intensity of input image for normalization. Use -1 to use model's default."
            },
            {
                "name": "std",
                "type": "float",
                "default": -1.0,
                "description": "Standard deviation of input image for normalization. Use -1 to use model's default."
            },
            {
                "name": "stack_output",
                "type": "bool",
                "default": True,
                "description": "If True, saves probability maps as separate files (NucleiPM, ContoursPM). If False, saves as a single concatenated stack."
            },
            {
                "name": "gpu_id",
                "type": "int",
                "default": -1,
                "description": "GPU device ID to use (0-indexed). Use -1 for CPU mode (default, recommended for Mac). Set to 0 or higher for GPU acceleration on Linux with CUDA."
            }
        ]
    },
    {
        "name": "batch_generate_probability_maps",
        "description": "Generate nuclei probability maps for multiple microscopy images in batch using UnMicst. This function processes multiple images, generating nuclei probability maps for each one. Each image gets its own output subdirectory. Useful for processing entire imaging experiments or cohorts at once.",
        "required_parameters": [
            {
                "name": "input_images",
                "type": "List[str]",
                "default": None,
                "description": "List of input microscopy image file paths."
            },
            {
                "name": "output_base_dir",
                "type": "str",
                "default": None,
                "description": "Base directory where output subdirectories will be created for each image. Each image will get its own subdirectory named after the input file."
            }
        ],
        "optional_parameters": [
            {
                "name": "channel",
                "type": "int",
                "default": 1,
                "description": "Channel number to use for inference (1-indexed), usually DNA/DAPI."
            },
            {
                "name": "model",
                "type": "str",
                "default": "unmicst-solo",
                "description": "Which UnMicst model to use: unmicst-solo, unmicst-duo, unmicst-legacy, or UnMicstCyto2."
            },
            {
                "name": "scaling_factor",
                "type": "float",
                "default": 1.0,
                "description": "Upsample/downsample factor for pixel size differences from 0.65 µm/px."
            },
            {
                "name": "mean",
                "type": "float",
                "default": -1.0,
                "description": "Mean intensity for normalization. Use -1 for model default."
            },
            {
                "name": "std",
                "type": "float",
                "default": -1.0,
                "description": "Standard deviation for normalization. Use -1 for model default."
            },
            {
                "name": "stack_output",
                "type": "bool",
                "default": True,
                "description": "Save as separate probability map files."
            },
            {
                "name": "gpu_id",
                "type": "int",
                "default": -1,
                "description": "GPU device ID to use (0-indexed). Use -1 for CPU mode (default, recommended for Mac). Set to 0+ for GPU on Linux."
            }
        ]
    }
]

