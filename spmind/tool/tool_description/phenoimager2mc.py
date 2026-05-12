"""
Tool descriptions for PhenoImager to MCMICRO conversion functions.
"""

description = [
    {
        "name": "convert_phenoimager_to_mcmicro",
        "description": "Convert PhenoImager .tif files to MCMICRO-compatible OME-TIFF format. The PhenoImager software outputs one float32 .tif file per tile and cycle containing all channels. This function converts them to stacked OME-TIFF files that are compatible with ASHLAR and the MCMICRO pipeline. Conversion steps include: metadata extraction, creation of stacked OME-TIFF files, conversion from float32 to uint16, and normalization.",
        "required_parameters": [
            {
                "name": "input_dir",
                "type": "str",
                "default": None,
                "description": "Path to the folder containing all .tif files from one cycle."
            },
            {
                "name": "output_path",
                "type": "str",
                "default": None,
                "description": "Output .tif file path for the converted OME-TIFF containing all tiles and channels."
            },
            {
                "name": "num_markers",
                "type": "int",
                "default": None,
                "description": "The number of markers that was used in this cycle."
            }
        ],
        "optional_parameters": [
            {
                "name": "normalization",
                "type": "str",
                "default": "99th",
                "description": "Normalization method for intensities per cycle. Either '99th' or 'max'."
            },
            {
                "name": "cycle",
                "type": "int",
                "default": None,
                "description": "Cycle number for metadata. If not provided, will be inferred from input files."
            }
        ]
    },
    {
        "name": "batch_convert_phenoimager_cycles",
        "description": "Batch convert multiple PhenoImager cycles to MCMICRO-compatible format. This function processes multiple cycles of PhenoImager data, converting each cycle's .tif files into a single MCMICRO-compatible OME-TIFF file. Useful for processing entire multi-cycle imaging experiments.",
        "required_parameters": [
            {
                "name": "input_base_dir",
                "type": "str",
                "default": None,
                "description": "Base directory containing cycle subdirectories with .tif files."
            },
            {
                "name": "output_base_dir",
                "type": "str",
                "default": None,
                "description": "Base directory where converted OME-TIFF files will be saved."
            },
            {
                "name": "cycles",
                "type": "List[int]",
                "default": None,
                "description": "List of cycle numbers to process."
            },
            {
                "name": "num_markers",
                "type": "int",
                "default": None,
                "description": "The number of markers used in each cycle."
            }
        ],
        "optional_parameters": [
            {
                "name": "normalization",
                "type": "str",
                "default": "99th",
                "description": "Normalization method for intensities. Either '99th' or 'max'."
            },
            {
                "name": "cycle_dir_pattern",
                "type": "str",
                "default": "cycle_{cycle}",
                "description": "Pattern for cycle directory names. Use {cycle} as placeholder."
            },
            {
                "name": "output_filename_pattern",
                "type": "str",
                "default": "cycle_{cycle}.ome.tif",
                "description": "Pattern for output filenames. Use {cycle} as placeholder."
            }
        ]
    }
]

