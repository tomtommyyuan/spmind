"""
Tool descriptions for S3segmenter watershed-based cell segmentation functions.
"""

description = [
    {
        "name": "segment_cells",
        "description": "Segment cells using S3segmenter, a watershed-based segmentation tool that generates single-cell (nuclei and cytoplasm) label masks from probability maps. Uses marker-controlled watershed constrained by nuclei contours from UnMicst or similar tools. Finds local maxima from nuclei foreground probability map and uses these as seeds for watershed. Can segment nuclei only or include cytoplasm segmentation using cytoplasmic markers. Generates label masks and QC images with outlines.",
        "required_parameters": [
            {
                "name": "input_image",
                "type": "str",
                "default": None,
                "description": "Path to the input microscopy image file (TIF or OME-TIFF). This is the original image, not the probability maps."
            },
            {
                "name": "probability_maps_dir",
                "type": "str",
                "default": None,
                "description": "Directory containing probability map files from UnMicst or similar tools. Should contain NucleiPM (nuclei foreground) and ContoursPM (nuclei contours) files."
            },
            {
                "name": "output_dir",
                "type": "str",
                "default": None,
                "description": "Directory where output segmentation masks will be saved. Will be created if it doesn't exist. Creates subdirectory named after input file containing nuclei.ome.tif and optionally cell.ome.tif and cyto.ome.tif files."
            }
        ],
        "optional_parameters": [
            {
                "name": "contours_pm",
                "type": "str",
                "default": None,
                "description": "Path to nuclei contours probability map file. If None, will auto-detect from probability_maps_dir by searching for files containing 'ContoursPM'."
            },
            {
                "name": "nuclei_pm",
                "type": "str",
                "default": None,
                "description": "Path to nuclei foreground probability map file. If None, will auto-detect from probability_maps_dir by searching for files containing 'NucleiPM'."
            },
            {
                "name": "crop_method",
                "type": "str",
                "default": "noCrop",
                "description": "Cropping method: 'noCrop' (no cropping), 'dearray' (for TMA cores), 'autoCrop' (middle third region), or 'plate' (for multi-well plates)."
            },
            {
                "name": "mask_type",
                "type": "str",
                "default": "tissue",
                "description": "Type of tissue mask: 'tissue' (automatic tissue detection), 'TMA' (for tissue microarray cores), or 'none' (no tissue masking)."
            },
            {
                "name": "nuclei_region",
                "type": "str",
                "default": "watershedContourInt",
                "description": "Nuclei segmentation method: 'watershedContourInt' (marker-controlled watershed using intensity, default), 'watershedContourDist' (using distance transform), 'watershedBWDist' (binary distance watershed), 'dilation' (simple dilation), or 'bypass' (use external segmentation)."
            },
            {
                "name": "nuclei_filter",
                "type": "str",
                "default": "IntPM",
                "description": "Feature for nuclei filtering: 'IntPM' (intensity of probability map, default), 'Int' (DAPI intensity), 'LoG' (Laplacian of Gaussian), or 'none' (accept all nuclei)."
            },
            {
                "name": "segment_cytoplasm",
                "type": "bool",
                "default": False,
                "description": "Whether to segment cytoplasm in addition to nuclei. If True, requires cytoplasm_channels to be specified."
            },
            {
                "name": "cytoplasm_channels",
                "type": "List[int]",
                "default": None,
                "description": "List of channel indices (1-indexed) to use for cytoplasm segmentation. Required if segment_cytoplasm=True. Example: [2, 3] for channels 2 and 3."
            },
            {
                "name": "cyto_method",
                "type": "str",
                "default": "distanceTransform",
                "description": "Cytoplasm segmentation method: 'distanceTransform' (distance-based expansion from nuclei), 'ring' (3-pixel annulus around nuclei), 'hybrid' (combination), or 'bwdistanceTransform' (binary distance transform)."
            },
            {
                "name": "cyto_dilation",
                "type": "int",
                "default": 5,
                "description": "Dilation size for cytoplasm segmentation in pixels."
            },
            {
                "name": "log_sigma",
                "type": "List[int]",
                "default": None,
                "description": "Range of nuclei diameters in pixels [min, max] for Laplacian of Gaussian filter. Default: [3, 60]."
            },
            {
                "name": "tissue_mask_channel",
                "type": "int",
                "default": 1,
                "description": "Channel to use for tissue mask generation (1-indexed). Usually a DNA or membrane marker channel."
            }
        ]
    },
    {
        "name": "batch_segment_cells",
        "description": "Segment cells for multiple microscopy images in batch using S3segmenter watershed-based segmentation. This function processes multiple images with their corresponding probability maps, performing watershed segmentation for each one. Each image gets its own output subdirectory. Useful for processing entire imaging experiments or cohorts at once.",
        "required_parameters": [
            {
                "name": "input_images",
                "type": "List[str]",
                "default": None,
                "description": "List of input microscopy image file paths."
            },
            {
                "name": "probability_maps_dirs",
                "type": "List[str]",
                "default": None,
                "description": "List of directories containing probability maps, corresponding to each input image. Must be same length as input_images."
            },
            {
                "name": "output_base_dir",
                "type": "str",
                "default": None,
                "description": "Base directory where output subdirectories will be created for each image."
            }
        ],
        "optional_parameters": [
            {
                "name": "crop_method",
                "type": "str",
                "default": "noCrop",
                "description": "Cropping method for all images."
            },
            {
                "name": "mask_type",
                "type": "str",
                "default": "tissue",
                "description": "Type of tissue mask for all images."
            },
            {
                "name": "nuclei_region",
                "type": "str",
                "default": "watershedContourInt",
                "description": "Nuclei segmentation method for all images."
            },
            {
                "name": "segment_cytoplasm",
                "type": "bool",
                "default": False,
                "description": "Whether to segment cytoplasm for all images."
            },
            {
                "name": "cytoplasm_channels",
                "type": "List[int]",
                "default": None,
                "description": "Cytoplasm marker channels (1-indexed) for all images."
            },
            {
                "name": "cyto_method",
                "type": "str",
                "default": "distanceTransform",
                "description": "Cytoplasm segmentation method for all images."
            }
        ]
    }
]

