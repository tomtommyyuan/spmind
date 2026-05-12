"""
Tool descriptions for UNetCoreograph TMA dearraying functions.
"""

description = [
    {
        "name": "dearray_tma",
        "description": "Dearray a tissue microarray (TMA) image into individual tissue cores using UNetCoreograph, a deep learning model based on UNet. The tool identifies complete and incomplete tissue cores on TMA slides and generates individual core images, binary tissue masks for each core, and a TMA map showing core labels and outlines for quality control. Trained on 9 TMA slides of different sizes and tissue types. Uses active contours to generate tissue masks that aid downstream single cell segmentation. GPU is not required but will reduce computation time.",
        "required_parameters": [
            {
                "name": "input_image",
                "type": "str",
                "default": None,
                "description": "Path to the input TMA image file. Should be TIF or OME-TIFF format."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": None,
                "description": "Directory where output files will be saved. Will be created if it doesn't exist. Output includes individual core TIFF files, mask/ subdirectory with binary masks, TMA_MAP.tif/jpg for QC, and centroidsY-X.txt with core positions."
            }
        ],
        "optional_parameters": [
            {
                "name": "downsample_factor",
                "type": "int",
                "default": 5,
                "description": "How many times to downsample the raw image file. Lower values (1-3) work better for high-resolution images. Higher values (5-10) work for lower resolution images. If 0 cores are detected, try adjusting this parameter. WARNING: For tissue splitting, set to higher than 5."
            },
            {
                "name": "channel",
                "type": "int",
                "default": 0,
                "description": "Which channel to feed into UNet for probability map generation. This is usually a DAPI or nuclear staining channel."
            },
            {
                "name": "buffer",
                "type": "float",
                "default": 2.0,
                "description": "Extra space around a core before cropping it. A value of 2 means there is twice the width of the core added as buffer around it."
            },
            {
                "name": "output_channels",
                "type": "str",
                "default": "-1",
                "description": "Range of channels to export. '-1' exports all channels (takes longer). Can specify single channel '0' or range '0 10' for channels 0-10 inclusive."
            },
        ]
    },
    {
        "name": "batch_dearray_tma",
        "description": "Dearray multiple tissue microarray (TMA) images in batch using UNetCoreograph. This function processes multiple TMA images, dearraying each one into individual tissue cores. Each TMA gets its own output subdirectory. Useful for processing entire TMA experiments or cohorts at once.",
        "required_parameters": [
            {
                "name": "input_images",
                "type": "List[str]",
                "default": None,
                "description": "List of input TMA image file paths."
            },
            {
                "name": "output_base_dir",
                "type": "str",
                "default": None,
                "description": "Base directory where output subdirectories will be created for each TMA. Each TMA will get its own subdirectory named after the input file."
            }
        ],
        "optional_parameters": [
            {
                "name": "downsample_factor",
                "type": "int",
                "default": 5,
                "description": "How many times to downsample the raw image files. Lower values for high-resolution images, higher for lower resolution."
            },
            {
                "name": "channel",
                "type": "int",
                "default": 0,
                "description": "Which channel to use for core detection, usually DAPI or nuclear staining."
            },
            {
                "name": "buffer",
                "type": "float",
                "default": 2.0,
                "description": "Extra space around cores before cropping."
            },
            {
                "name": "output_channels",
                "type": "str",
                "default": "-1",
                "description": "Range of channels to export. '-1' for all channels, or specify range like '0 10'."
            }
        ]
    }
]
