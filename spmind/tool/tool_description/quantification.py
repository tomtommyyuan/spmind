description = [
    {
        "name": "quantify_cells",
        "description": "Extract single-cell quantification data from segmented microscopy images using mcquant. Quantifies marker intensities for each segmented cell in multi-channel images, extracting spatial features and intensity measurements. Output CSV structure is aligned with histoCAT format for downstream analysis.",
        "required_parameters": [
            {
                "name": "image_path",
                "type": "str",
                "default": None,
                "description": "Path to the multi-channel image file for quantification. Supports .tif, .tiff, .h5, or .hdf5 formats. This should be the registered/stitched image from ASHLAR or similar preprocessing."
            },
            {
                "name": "mask_paths",
                "type": "Union[str, List[str]]",
                "default": None,
                "description": "Path(s) to segmentation mask file(s). Can be a single mask file path or a list of mask paths. If multiple masks are provided, the first mask will be used for spatial feature extraction but all will be quantified. Typically outputs from S3segmenter, Ilastik, or similar segmentation tools."
            },
            {
                "name": "channel_names",
                "type": "Union[str, List[str]]",
                "default": None,
                "description": "Either a path to a CSV file containing channel names (one name per line) or a list of channel names as strings. The number of channels must match the image. Channel names identify the markers/antibodies used (e.g., ['DAPI', 'CD3', 'CD8', 'CD20'])."
            }
        ],
        "optional_parameters": [
            {
                "name": "output_dir",
                "type": "str",
                "default": "./quantification",
                "description": "Directory to save output CSV files containing single-cell quantification data."
            },
            {
                "name": "mask_props",
                "type": "List[str]",
                "default": None,
                "description": "Additional mask properties to calculate for each cell. These are metrics that depend only on the cell mask shape (e.g., 'perimeter', 'convex_area', 'euler_number'). See scikit-image regionprops documentation for available properties."
            },
            {
                "name": "intensity_props",
                "type": "List[str]",
                "default": None,
                "description": "Additional intensity properties to calculate for each marker. Options include 'intensity_median', 'intensity_sum', 'gini_index'. By default, only 'intensity_mean' is calculated. Use 'intensity_sum' for counting RNA molecules in FISH images."
            },
        ]
    },
    {
        "name": "batch_quantify_cells",
        "description": "Batch quantification of multiple images with their corresponding segmentation masks. Convenient wrapper for processing multiple images in a single call, creating organized output directories for each image.",
        "required_parameters": [
            {
                "name": "image_mask_pairs",
                "type": "List[Tuple[str, Union[str, List[str]]]]",
                "default": None,
                "description": "List of (image_path, mask_paths) tuples. Each tuple contains the path to an image and the corresponding mask path(s). Example: [('image1.tif', 'mask1.tif'), ('image2.tif', 'mask2.tif')]"
            },
            {
                "name": "channel_names",
                "type": "Union[str, List[str]]",
                "default": None,
                "description": "Channel names file path or list of channel names. This will be used for all images in the batch (assumes same markers across all images)."
            }
        ],
        "optional_parameters": [
            {
                "name": "output_dir",
                "type": "str",
                "default": "./quantification",
                "description": "Base output directory. Each image will create a subdirectory within this directory named after the image file."
            },
            {
                "name": "mask_props",
                "type": "List[str]",
                "default": None,
                "description": "Additional mask properties to calculate for all images."
            },
            {
                "name": "intensity_props",
                "type": "List[str]",
                "default": None,
                "description": "Additional intensity properties to calculate for all images."
            },
        ]
    }
]

