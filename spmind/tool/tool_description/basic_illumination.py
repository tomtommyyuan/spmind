"""
Tool descriptions for BaSiC illumination correction functions.
"""

description = [
    {
        "name": "generate_illumination_profiles",
        "description": "Generate flat-field and dark-field illumination correction profiles using BaSiC (Bayesian Shading Correction) algorithm. This function uses ImageJ/Fiji with the BaSiC plugin to compute illumination correction profiles from microscopy images. The output profiles can be used with ASHLAR to correct for uneven illumination during image stitching. The BaSiC algorithm analyzes the image stack to identify flat-field (FFP) patterns capturing uneven illumination and dark-field (DFP) patterns capturing camera baseline signal/noise.",
        "required_parameters": [
            {
                "name": "input_image",
                "type": "str",
                "default": None,
                "description": "Path to the input microscopy image file (e.g., OME-TIFF). Must be a BioFormats-compatible file format."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": None,
                "description": "Directory where output profiles will be saved. Must exist before calling this function."
            }
        ],
        "optional_parameters": [
            {
                "name": "experiment_name",
                "type": "str",
                "default": None,
                "description": "Base name for output files. If not provided, will be derived from input filename. Output files will be named: {experiment_name}-ffp.tif and {experiment_name}-dfp.tif"
            },
            {
                "name": "lambda_flat",
                "type": "float",
                "default": 0.1,
                "description": "Flat-field smoothing parameter. Set to 0 for automatic estimation."
            },
            {
                "name": "lambda_dark",
                "type": "float",
                "default": 0.01,
                "description": "Dark-field smoothing parameter. Set to 0 for automatic estimation."
            }
        ]
    },
    {
        "name": "batch_generate_illumination_profiles",
        "description": "Generate illumination profiles for multiple microscopy images in batch. This function processes multiple microscopy images, generating flat-field and dark-field correction profiles for each one using the BaSiC algorithm. Useful for processing entire multi-cycle imaging experiments where each cycle needs illumination correction.",
        "required_parameters": [
            {
                "name": "input_images",
                "type": "List[str]",
                "default": None,
                "description": "List of input microscopy image file paths."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": None,
                "description": "Directory where all output profiles will be saved. Must exist before calling this function."
            }
        ],
        "optional_parameters": [
            {
                "name": "lambda_flat",
                "type": "float",
                "default": 0.1,
                "description": "Flat-field smoothing parameter. Set to 0 for automatic estimation."
            },
            {
                "name": "lambda_dark",
                "type": "float",
                "default": 0.01,
                "description": "Dark-field smoothing parameter. Set to 0 for automatic estimation."
            }
        ]
    }
]
