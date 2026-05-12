description = [
    {
        "name": "stitch_and_register_tiles_ashlar",
        "description": "Stitch and register multi-tile microscopy images using ASHLAR. Performs fast, high-quality stitching and co-registers multiple rounds of cyclic imaging for CyCIF, CODEX, and similar methods.",
        "required_parameters": [
            {
                "name": "input_files",
                "type": "List[str]",
                "default": None,
                "description": "List of image file paths to be processed, one per cycle. Can be BioFormats-supported vendor formats or plain TIFF files."
            }
        ],
        "optional_parameters": [
            {
                "name": "output_path",
                "type": "str",
                "default": "ashlar_output.ome.tif",
                "description": "Output file path. If ends in .ome.tif, writes pyramidal OME-TIFF."
            },
            {
                "name": "align_channel",
                "type": "int",
                "default": 0,
                "description": "Reference channel number for image alignment. Numbering starts at 0."
            },
            {
                "name": "maximum_shift",
                "type": "float",
                "default": 15,
                "description": "Maximum allowed per-tile corrective shift in microns."
            },
            {
                "name": "filter_sigma",
                "type": "float",
                "default": None,
                "description": "Filter images before alignment using Gaussian kernel with this standard deviation in pixels."
            },
            {
                "name": "tile_size",
                "type": "int",
                "default": 1024,
                "description": "Pyramid tile size for OME-TIFF output."
            },
            {
                "name": "ffp_files",
                "type": "List[str]",
                "default": None,
                "description": "Flat field profile image file(s) for illumination correction. One common file or one per cycle."
            },
            {
                "name": "dfp_files",
                "type": "List[str]",
                "default": None,
                "description": "Dark field profile image file(s) for illumination correction. One common file or one per cycle."
            },
            {
                "name": "flip_x",
                "type": "bool",
                "default": False,
                "description": "Flip tile positions left-to-right."
            },
            {
                "name": "flip_y",
                "type": "bool",
                "default": False,
                "description": "Flip tile positions top-to-bottom."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": "./",
                "description": "Directory to save output files."
            },
        ]
    },
    {
        "name": "align_cyclic_images_ashlar",
        "description": "Align multiple rounds of cyclic imaging (e.g., CyCIF, CODEX) using ASHLAR. Simplified wrapper specifically for multi-cycle registration in cyclic immunofluorescence methods.",
        "required_parameters": [
            {
                "name": "cycle_files",
                "type": "List[str]",
                "default": None,
                "description": "List of image files, one per imaging cycle, in order."
            }
        ],
        "optional_parameters": [
            {
                "name": "output_path",
                "type": "str",
                "default": "registered_cycles.ome.tif",
                "description": "Output OME-TIFF file path."
            },
            {
                "name": "align_channel",
                "type": "int",
                "default": 0,
                "description": "Channel to use for alignment across cycles."
            },
            {
                "name": "maximum_shift",
                "type": "float",
                "default": 30,
                "description": "Maximum shift between cycles in microns."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": "./",
                "description": "Output directory."
            }
        ]
    },
    {
        "name": "stitch_microscopy_tiles_ashlar",
        "description": "Stitch microscopy tiles from a directory using ASHLAR. Convenience function for stitching tiles from a single imaging round when all tiles are in one directory.",
        "required_parameters": [
            {
                "name": "tile_directory",
                "type": "str",
                "default": None,
                "description": "Directory containing image tiles."
            }
        ],
        "optional_parameters": [
            {
                "name": "output_path",
                "type": "str",
                "default": "stitched.ome.tif",
                "description": "Output file name."
            },
            {
                "name": "file_pattern",
                "type": "str",
                "default": "*.tif",
                "description": "Glob pattern to match tile files."
            },
            {
                "name": "maximum_shift",
                "type": "float",
                "default": 15,
                "description": "Maximum corrective shift in microns."
            },
            {
                "name": "filter_sigma",
                "type": "float",
                "default": None,
                "description": "Gaussian filter sigma for pre-alignment filtering."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": "./",
                "description": "Output directory."
            }
        ]
    }
]

