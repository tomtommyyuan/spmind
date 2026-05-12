"""
Tool descriptions for background subtraction functions.
"""

description = [
    {
        "name": "subtract_background",
        "description": "Subtract background from microscopy image using pixel-by-pixel channel subtraction scaled by exposure times. Performs background (autofluorescence) subtraction for multichannel microscopy images on a pixel-to-pixel basis. The most precise way of subtracting background for improved segmentation, quantification, and visualization of images from tissues with high autofluorescence (FFPE). Uses the formula: Marker_corrected = Marker_raw - (Background / Exposure_Background) * Exposure_Marker. Requires a markers.csv file with columns: marker_name, background, exposure, and optionally remove.",
        "required_parameters": [
            {
                "name": "input_image",
                "type": "str",
                "default": None,
                "description": "Path to the input microscopy image file (OME-TIFF)."
            },
            {
                "name": "markers_file",
                "type": "str",
                "default": None,
                "description": "Path to the markers.csv file containing channel information. Must have columns: marker_name (unique names), background (marker name to subtract), exposure (exposure time in consistent units), and optionally remove (TRUE for channels to exclude)."
            },
            {
                "name": "output_image",
                "type": "str",
                "default": None,
                "description": "Path for the output background-subtracted OME-TIFF image."
            }
        ],
        "optional_parameters": [
            {
                "name": "output_markers",
                "type": "str",
                "default": None,
                "description": "Path for the output markers CSV file. If not provided, will use {output_image_basename}_markers.csv in the same directory."
            },
            {
                "name": "pixel_size",
                "type": "float",
                "default": None,
                "description": "Pixel size of the input image. If not specified, will be read from metadata."
            },
            {
                "name": "tile_size",
                "type": "int",
                "default": 1024,
                "description": "Tile size for the pyramidal output image. Adjust to smaller value (e.g. 512) if output file is unexpectedly large."
            },
            {
                "name": "chunk_size",
                "type": "int",
                "default": 5000,
                "description": "Chunk size for delayed calculation execution. Lower values increase execution time, higher values increase RAM usage."
            }
        ]
    },
    {
        "name": "batch_subtract_background",
        "description": "Subtract background from multiple microscopy images in batch. This function processes multiple microscopy images, performing background subtraction for each one using corresponding markers files. Useful for processing entire multi-cycle imaging experiments where each cycle needs background correction.",
        "required_parameters": [
            {
                "name": "input_images",
                "type": "List[str]",
                "default": None,
                "description": "List of input microscopy image file paths."
            },
            {
                "name": "markers_files",
                "type": "List[str]",
                "default": None,
                "description": "List of markers CSV file paths, corresponding to each input image. Must be same length as input_images."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": None,
                "description": "Directory where all output images and markers files will be saved."
            }
        ],
        "optional_parameters": [
            {
                "name": "pixel_size",
                "type": "float",
                "default": None,
                "description": "Pixel size of the input images. If not specified, will be read from metadata."
            },
            {
                "name": "tile_size",
                "type": "int",
                "default": 1024,
                "description": "Tile size for the pyramidal output images."
            },
            {
                "name": "chunk_size",
                "type": "int",
                "default": 5000,
                "description": "Chunk size for delayed calculation execution."
            }
        ]
    }
]

