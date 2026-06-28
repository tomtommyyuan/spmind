# SPMind Experiments

Reproduce the three evaluation tracks from the SPMind paper:

| Track | What it measures | Script |
|-------|-----------------|--------|
| **SP-Bench** | End-to-end spatial proteomics pipeline execution | `benchmark/` (repo root) |
| **Cell Annotation** | Cell-type labelling accuracy (CyteOnto similarity) | `run_annotation_eval.py` |
| **Cell Quantification** | Marker quantification fidelity (5 metrics) | `run_quantification_eval.py` |

---

## Prerequisites

### Install dependencies

```bash
pip install pyyaml numpy pandas scipy
# Cell-annotation eval (LLM descriptions -> Qwen3-Embedding-8B -> cosine + GHK):
pip install sentence-transformers torch anthropic
```

The annotation metric is implemented self-contained in `run_annotation_eval.py`
(no external package needed). Note `Qwen/Qwen3-Embedding-8B` is a large model
(~16 GB) downloaded on first run; ensure adequate disk and GPU/VRAM, and set
`ANTHROPIC_API_KEY` for description generation.

### Download datasets

The SP-Bench and cell annotation datasets are hosted on
[Hugging Face](https://huggingface.co/datasets/tomyuanyucheng/spmind):

```bash
pip install huggingface_hub

# Download the full dataset
huggingface-cli download tomyuanyucheng/spmind --repo-type dataset --local-dir data
```

After download the `data/` directory will contain:

```
data/
├── background_subtraction_input/       # ── SP-Bench task inputs ──
├── clustering_input/
├── dearray_input/
├── illumination_input/
├── probability_mapping_input/
├── quantification_input/
├── registration_input/
├── segmentation_input/
├── annotation/                         # ── Cell annotation data ──
│   ├── gt/                             #   Expert ground truth
│   │   ├── cHL_1_MIBI_gt.csv
│   │   ├── cHL_2_MIBI_5_gt.csv
│   │   ├── cHL_CODEX_gt.csv
│   │   └── jonathan_pdac_imc_gt.csv
│   └── input/                          #   Marker expression (no labels)
│       ├── cHL_1_MIBI_input.csv
│       ├── cHL_2_MIBI_5_input.csv
│       ├── cHL_CODEX_input.csv
│       └── jonathan_pdac_imc_input.csv
└── README.md
```

### Set API keys

```bash
export ANTHROPIC_API_KEY="your-key"   # for running the SPMind agent & LLM-enriched eval
# or
export OPENAI_API_KEY="your-key"      # with --llm-provider openai
```

---

## 1. SP-Bench

SP-Bench evaluates whether the agent can correctly orchestrate spatial proteomics
tool chains of varying complexity (basic / intermediate / challenging / advanced).

### Benchmark queries

The task queries live in `benchmark/sp_bench.jsonl` at the repo root. Each entry
specifies the query, tier, category, and which pipeline stages are involved.

You can list all categories with:

```bash
python benchmark/create_benchmark.py --list-categories
```

### Running the benchmark

For each query in the benchmark, launch the SPMind agent and judge whether the
pipeline executed successfully:

```bash
# Run a single SP-Bench task
python run_agent.py "Generate the illumination correction profiles for the 10 cycles \
  of raw OME-TIFF images located in data/spbench_dataset/illumination_input/ folder. \
  All resulting flat-field and dark-field profiles should be stored in output/illumination/ \
  folder for use in the subsequent stitching step."
```

Replace the `{input_dir}` / `{output_dir}` / `{markers_csv}` placeholders in each
benchmark query with your desired path

---

## 2. Cell Annotation

Evaluate SPMind's cell-type annotation accuracy against expert ground truth
using [CyteOnto](https://github.com/NygenAnalytics/CyteOnto) semantic similarity.

### Generate predictions

Run the SPMind agent on each input dataset to produce prediction CSVs:

```bash
python run_agent.py "Perform cell type annotation on the single-cell data located at \
  data/annotation/input/cHL_1_MIBI_input.csv. The data contains a 'cluster' column with \
  numeric cluster IDs and multiple protein marker columns. Analyze the marker expression \
  profiles for each cluster and assign biologically meaningful cell type labels. Add only \
  a single new column called 'annotation' to the output. Each unique cluster ID must \
  correspond to exactly one annotation label (all cells within the same cluster must have \
  the same annotation). Save the annotated results to data/annotation/predictions/cHL_1_MIBI_pred.csv."
```

Repeat for each dataset: `cHL_1_MIBI`, `cHL_2_MIBI_5`, `cHL_CODEX`, `jonathan_pdac_imc`.

**Prediction format** (one row per cluster):

| Column | Type | Description |
|--------|------|-------------|
| cluster | int | Cluster ID |
| Annotation | str | Predicted cell-type label |

### Run evaluation

```bash
cd experiments

# Single dataset
python run_annotation_eval.py --config annotation_configs/chl1_mibi.yaml

# All datasets at once
python run_annotation_eval.py --config annotation_configs/*.yaml

# Custom paths (no config needed)
python run_annotation_eval.py \
    --gt data/annotation/gt/cHL_1_MIBI_gt.csv \
    --pred data/annotation/predictions/cHL_1_MIBI_pred.csv \
    --no-descriptions

# Override parameters
python run_annotation_eval.py \
    --config annotation_configs/chl1_mibi.yaml \
    --sigma 0.3 --threshold 0.85
```

### Metrics

The result JSON reports the following:

| Key | Level | Description |
|-----|-------|-------------|
| `ghk_cell_weighted` | Cell | Per-cluster GHK averaged across all cells (weighted by cluster size) |
| `ghk_cluster_mean` | Cluster | Unweighted mean GHK across clusters |
| `cosine_cell_weighted` / `cosine_cluster_mean` | Cell / Cluster | Raw cosine similarity, cell-weighted and cluster-mean |
| `exact_accuracy_cluster` / `exact_accuracy_cell` | Cluster / Cell | Fraction with identical GT/predicted labels |
| `semantic_accuracy_cluster` / `semantic_accuracy_cell` | Cluster / Cell | Fraction with cosine >= threshold (default 0.80) |

GHK = Gaussian Heat Kernel transform of cosine similarity, centered at 1.0 with
sigma=0.25: `exp(-(cos-1)^2 / (2*sigma^2))`.

### Config files

Each YAML config in `annotation_configs/` specifies a dataset:

```yaml
dataset: cHL_1_MIBI
gt: data/annotation/gt/cHL_1_MIBI_gt.csv
pred: data/annotation/predictions/cHL_1_MIBI_pred.csv

model: Qwen/Qwen3-Embedding-8B
sigma: 0.25
threshold: 0.80
generate_descriptions: true
llm_provider: anthropic
llm_model: claude-sonnet-4-20250514
```

All parameters can be overridden via CLI flags (`python run_annotation_eval.py --help`).

---

## 3. Cell Quantification

Compare MCquant output against ground truth using five segmentation-agnostic
metrics.

### Download the CRC CODEX dataset

The quantification ground truth comes from the colorectal cancer (CRC) CODEX
dataset published in:

> Schürch, C. M., Bhate, S. S., Barlow, G. L., Phillips, D. J., Noti, L.,
> Zlobec, I., Chu, P., Black, S., Demeter, J., McIlwain, D. R., et al.
> *Coordinated cellular neighborhoods orchestrate antitumoral immunity at the
> colorectal cancer invasive front.* Cell, 182(5):1341–1359, 2020.

Download the `crc_codex_quant/` folder, which contains 10 TMA regions
(5 from TMA-A, 5 from TMA-B). Each region has two files:

| File | Description |
|------|-------------|
| `TMA_{A,B}_reg00N_X01_Y01_Z*.tif` | Multi-channel CODEX image (~170–240 MB each) |
| `TMA_{A,B}_reg00N_X01_Y01_Z*_markers.csv` | Marker metadata (channel, cycle, marker name, filter) |

### Prepare data

For each TMA region you need two CSVs:

- **MCquant output** — the quantification CSV produced by running the SPMind
  agent's full pipeline (segmentation + quantification) on one of the
  `crc_codex_quant/` images above.
- **Ground truth CSV** — expert-curated quantification with columns of the form
  `MarkerName:Cyc_N_ch_M` (containing per-cell spatial coordinates and marker
  intensities).

### Run evaluation

```bash
cd experiments

python run_quantification_eval.py \
    --mcquant path/to/mcquant_output.csv \
    --gt path/to/gt_quantification.csv \
    --output results/quant_results.csv

# Custom tile size for spatial metric
python run_quantification_eval.py \
    --mcquant mcquant.csv --gt gt.csv \
    --tile-size 50 --seed 42
```

### Metrics

| # | Metric | What it captures |
|---|--------|-----------------|
| 1 | Pearson r (marker sums) | Linear correlation of marker abundances |
| 2 | Spearman rho (marker sums) | Rank correlation of marker abundances |
| 3 | Correlation matrix cosine sim | Marker-marker co-expression preservation |
| 4 | MMD (RBF kernel) | Multivariate cell population similarity |
| 5 | Grid-based spatial Spearman | Whether signal is in the correct spatial location |

---

## Reference

If you use these evaluations, please cite:

- **SPMind**:

```bibtex
@misc{yuan2026spmindautonomousreasoningagent,
      title={SP-Mind: An Autonomous Reasoning Agent for Spatial Proteomics Analysis}, 
      author={Yucheng Yuan and Yuanfeng Ji and Zhongxiao Li and Ruijiang Li},
      year={2026},
      eprint={2606.24235},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2606.24235}, 
}
```

- **CyteOnto**: 

```bibtex
@article{cytetype2025,
  title={Multi-agent AI enables evidence-based cell annotation in single-cell transcriptomics},
  author={Gautam Ahuja, Alex Antill, Yi Su, Giovanni Marco Dall'Olio, Sukhitha Basnayake, Göran Karlsson, Parashar Dhapola},
  journal={bioRxiv},
  year={2025},
  doi={10.1101/2025.11.06.686964},
  url={https://www.biorxiv.org/content/10.1101/2025.11.06.686964v1}
}
```
