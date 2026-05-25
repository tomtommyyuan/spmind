#!/usr/bin/env python3
"""
Run CyteOnto annotation accuracy evaluation against SPMind predictions.

Accepts either a YAML config file or explicit CLI arguments.

Usage:
    # Single dataset via config
    python run_annotation_eval.py --config annotation_configs/chl1_mibi.yaml

    # All datasets
    python run_annotation_eval.py --config annotation_configs/*.yaml

    # Explicit paths (overrides config)
    python run_annotation_eval.py --gt data/gt/cHL_1_MIBI_gt.csv --pred data/predictions/cHL_1_MIBI_pred.csv

    # Override config defaults
    python run_annotation_eval.py --config annotation_configs/chl1_mibi.yaml --sigma 0.3 --no-descriptions
"""

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def load_config(path: str) -> dict:
    if yaml is None:
        raise ImportError("PyYAML is required to use config files: pip install pyyaml")
    with open(path) as f:
        return yaml.safe_load(f)


def run_single(
    gt: str,
    pred: str,
    output: str | None = None,
    *,
    cell_id_col: str = "auto",
    cluster_col: str = "cluster",
    annotation_col: str = "Annotation",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    sigma: float = 0.25,
    threshold: float = 0.80,
    generate_descriptions: bool = False,
    llm_provider: str = "anthropic",
    llm_model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Run evaluation for a single dataset by calling CyteOnto."""
    try:
        from cytonto.annotation_accuracy import run_evaluation
    except ImportError:
        print(
            "ERROR: CyteOnto is not installed.\n"
            "Install it with:\n"
            "  pip install git+https://github.com/<org>/CyteOnto.git\n"
            "or:\n"
            "  pip install cytonto",
            file=sys.stderr,
        )
        sys.exit(1)

    gt_path = Path(gt)
    pred_path = Path(pred)

    if not gt_path.exists():
        print(f"ERROR: Ground truth file not found: {gt_path}", file=sys.stderr)
        sys.exit(1)
    if not pred_path.exists():
        print(f"ERROR: Prediction file not found: {pred_path}", file=sys.stderr)
        sys.exit(1)

    return run_evaluation(
        gt_csv_path=str(gt_path),
        ai_csv_path=str(pred_path),
        cell_id_col=cell_id_col,
        cluster_col=cluster_col,
        annotation_col=annotation_col,
        output_path=output,
        sigma=sigma,
        similarity_threshold=threshold,
        embedding_model_name=model,
        save_embeddings=False,
        generate_descriptions=generate_descriptions,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run CyteOnto annotation accuracy evaluation on SPMind predictions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        nargs="+",
        metavar="YAML",
        help="One or more YAML config files (e.g. annotation_configs/*.yaml)",
    )
    parser.add_argument("--gt", help="Path to ground truth CSV (overrides config)")
    parser.add_argument("--pred", help="Path to prediction CSV (overrides config)")
    parser.add_argument("--output-dir", default="results", help="Directory for result JSONs")

    col_group = parser.add_argument_group("column names (override config)")
    col_group.add_argument(
        "--cell-id-col", default=None,
        help="Cell ID column name (default: auto-detect from cellLabel, cell_id, identifier, etc.)",
    )
    col_group.add_argument("--cluster-col", default=None, help="Cluster column name (default: cluster)")
    col_group.add_argument("--annotation-col", default=None, help="Annotation column name (default: Annotation)")

    eval_group = parser.add_argument_group("evaluation parameters (override config)")
    eval_group.add_argument("--model", help="Embedding model name")
    eval_group.add_argument("--sigma", type=float, help="GHK sigma")
    eval_group.add_argument("--threshold", type=float, help="Cosine similarity threshold")
    eval_group.add_argument(
        "--no-descriptions",
        action="store_true",
        help="Disable LLM description generation",
    )
    eval_group.add_argument("--llm-provider", choices=["anthropic", "openai", "kimi"])
    eval_group.add_argument("--llm-model", help="LLM model name for description generation")

    args = parser.parse_args()

    if not args.config and not (args.gt and args.pred):
        parser.error("Provide either --config or both --gt and --pred")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    configs: list[dict] = []

    if args.config:
        for cfg_path in args.config:
            configs.append(load_config(cfg_path))
    else:
        configs.append({"dataset": "custom", "gt": args.gt, "pred": args.pred})

    for cfg in configs:
        if args.gt:
            cfg["gt"] = args.gt
        if args.pred:
            cfg["pred"] = args.pred
        if args.cell_id_col:
            cfg["cell_id_col"] = args.cell_id_col
        if args.cluster_col:
            cfg["cluster_col"] = args.cluster_col
        if args.annotation_col:
            cfg["annotation_col"] = args.annotation_col
        if args.model:
            cfg["model"] = args.model
        if args.sigma is not None:
            cfg["sigma"] = args.sigma
        if args.threshold is not None:
            cfg["threshold"] = args.threshold
        if args.no_descriptions:
            cfg["generate_descriptions"] = False
        if args.llm_provider:
            cfg["llm_provider"] = args.llm_provider
        if args.llm_model:
            cfg["llm_model"] = args.llm_model

    for cfg in configs:
        dataset = cfg.get("dataset", "unknown")
        print(f"\n{'=' * 60}")
        print(f"Dataset: {dataset}")
        print(f"{'=' * 60}")

        output_path = str(out_dir / f"{dataset}_results.json")

        run_single(
            gt=cfg["gt"],
            pred=cfg["pred"],
            output=output_path,
            cell_id_col=cfg.get("cell_id_col", "auto"),
            cluster_col=cfg.get("cluster_col", "cluster"),
            annotation_col=cfg.get("annotation_col", "Annotation"),
            model=cfg.get("model", "sentence-transformers/all-MiniLM-L6-v2"),
            sigma=cfg.get("sigma", 0.25),
            threshold=cfg.get("threshold", 0.80),
            generate_descriptions=cfg.get("generate_descriptions", False),
            llm_provider=cfg.get("llm_provider", "anthropic"),
            llm_model=cfg.get("llm_model", "claude-sonnet-4-20250514"),
        )

        print(f"\nResults saved to: {output_path}")

    print(f"\nAll evaluations complete. Results in: {out_dir}/")


if __name__ == "__main__":
    main()
