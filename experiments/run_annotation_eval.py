#!/usr/bin/env python3
"""
Cell Annotation Challenge evaluation (SP-Mind paper, Appendix D).

Self-contained re-implementation of the semantic annotation metric used in the
paper. No external CyteOnto package required. The pipeline is exactly the three
steps described in the paper:

    1. Describe   each unique cell-type label is expanded into a structured
                  biological description with an LLM (Claude Sonnet 4).
    2. Embed      each description is encoded with Qwen3-Embedding-8B
                  (4096-dim, L2-normalized) via sentence-transformers.
    3. Score      per cluster, cosine similarity between the agent-label and
                  ground-truth-label description embeddings, warped by a
                  Gaussian Heat Kernel (GHK) centered at 1.0 with sigma=0.25.

Matching is done at the cluster level (all cells in a cluster share one agent
label; the ground-truth cluster label is the per-cluster mode). The headline
metric reported in Table 3 is the GHK similarity averaged across all cells
(i.e. each cluster's GHK weighted by its cell count).

Usage:
    # Single dataset via config
    python run_annotation_eval.py --config annotation_configs/chl1_mibi.yaml

    # All datasets
    python run_annotation_eval.py --config annotation_configs/*.yaml

    # Explicit paths (overrides config)
    python run_annotation_eval.py \
        --gt data/annotation/gt/cHL_1_MIBI_gt.csv \
        --pred data/annotation/predictions/cHL_1_MIBI_pred.csv

    # Quick debug without LLM descriptions (embeds raw labels; NOT the paper metric)
    python run_annotation_eval.py --config annotation_configs/chl1_mibi.yaml --no-descriptions

Dependencies:
    pip install sentence-transformers torch anthropic openai numpy pandas pyyaml
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import yaml
except ImportError:
    yaml = None

# Optional .env support for API keys.
try:
    from dotenv import load_dotenv

    _env = Path(__file__).parent / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass


# ============================================================
# Defaults (match the paper's Cell Annotation Challenge setup)
# ============================================================

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
LLM_PROVIDER = "anthropic"
LLM_MODEL = "claude-sonnet-4-20250514"
SIGMA = 0.25
THRESHOLD = 0.80

# Structured description prompt (5 components), following the CyteOnto schema
# referenced in the paper.
DESCRIPTION_PROMPT = """You are a cell biology expert. Generate a structured description for the cell type "{cell_name}".

Provide the following 5 components:
1. Descriptive name: A descriptive and concise name for the cell type.
2. Functional characteristics: Primary cellular functions and roles.
3. Markers: Marker genes that are commonly associated with the cell type (comma-separated gene symbols).
4. Disease relevance: Associations with diseases or pathological conditions.
5. Developmental stage: Typical developmental stage or lineage of the cell type.

Output format (concatenate into one paragraph):
[Cell Name] is a [descriptive name]. [Functional characteristics]. [Disease relevance]. [Developmental stage]. The marker genes are [markers].

Be scientifically accurate and specific. Output only the final concatenated description, no headers or extra text."""


# ============================================================
# Column resolution / cluster aggregation
# ============================================================

def _find_column(df: pd.DataFrame, target: str, alternatives: list[str]) -> Optional[str]:
    """Find a column case-insensitively, trying ``target`` then ``alternatives``."""
    lower_map = {c.lower(): c for c in df.columns}
    for name in [target, *alternatives]:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _resolve_columns(
    df_gt: pd.DataFrame,
    df_ai: pd.DataFrame,
    cell_id_col: str,
    cluster_col: str,
    annotation_col: str,
) -> tuple[str, str, str, str]:
    """Resolve cell-id, cluster, and annotation column names in both files."""
    ann_alts = ["Annotation", "annotation", "label", "Label", "cell_type", "CellType"]
    gt_ann = _find_column(df_gt, annotation_col, ann_alts)
    ai_ann = _find_column(df_ai, annotation_col, ann_alts)
    if gt_ann is None:
        raise ValueError(f"No annotation column in GT file. Columns: {list(df_gt.columns)}")
    if ai_ann is None:
        raise ValueError(f"No annotation column in AI file. Columns: {list(df_ai.columns)}")

    clust = _find_column(df_ai, cluster_col, ["cluster", "Cluster", "cluster_id", "ClusterID"])
    if clust is None:
        raise ValueError(f"No cluster column in AI file. Columns: {list(df_ai.columns)}")

    id_alts = ["cell_id", "cellLabel", "CellLabel", "cell_label", "identifier", "CellID", "ID", "id"]
    if cell_id_col != "auto":
        resolved_id = _find_column(df_gt, cell_id_col, [])
    else:
        resolved_id = _find_column(df_gt, "", id_alts)
    # Fall back to row index when no usable id column exists in both files.
    if resolved_id is None or resolved_id not in df_ai.columns:
        resolved_id = "_row_index"

    return resolved_id, clust, gt_ann, ai_ann


def _validate_consistency(df: pd.DataFrame, cluster_col: str, annotation_col: str) -> None:
    """Reject AI files where a cluster has more than one distinct annotation (paper D.4)."""
    bad = []
    for cid, grp in df.groupby(cluster_col):
        uniq = grp[annotation_col].dropna().unique()
        if len(uniq) > 1:
            bad.append((cid, grp[annotation_col].value_counts().to_dict()))
    if bad:
        details = "\n".join(f"  cluster {cid}: {counts}" for cid, counts in bad[:10])
        raise ValueError(
            f"AI file has {len(bad)} cluster(s) with inconsistent annotations. "
            f"All cells in a cluster must share one label.\n{details}"
        )


def _cluster_mode_labels(df: pd.DataFrame, cluster_col: str, label_col: str) -> dict:
    """Most-common label per cluster."""
    return {
        cid: Counter(grp[label_col]).most_common(1)[0][0]
        for cid, grp in df.groupby(cluster_col)
    }


# ============================================================
# Step 1: LLM descriptions
# ============================================================

def generate_descriptions(
    labels: list[str],
    use_llm: bool,
    provider: str,
    model: str,
    cache_path: Optional[Path] = None,
) -> dict[str, str]:
    """Map each label to a description. Without an LLM, the label is its own description."""
    if not use_llm:
        print("  [descriptions] LLM disabled; embedding raw labels (not the paper metric)")
        return {label: label for label in labels}

    cache: dict[str, str] = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())

    todo = [l for l in labels if l not in cache]
    if todo:
        print(f"  [descriptions] generating {len(todo)} via {provider}:{model} "
              f"({len(labels) - len(todo)} cached)")
        generate = _describe_anthropic if provider == "anthropic" else _describe_openai
        for i, label in enumerate(todo, 1):
            try:
                cache[label] = generate(label, model, provider)
                print(f"    [{i}/{len(todo)}] {label}: {cache[label][:70]}...")
            except Exception as e:  # noqa: BLE001
                print(f"    [{i}/{len(todo)}] {label}: ERROR ({e}); using label text")
                cache[label] = label
        if cache_path:
            cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))

    return {label: cache.get(label, label) for label in labels}


def _describe_anthropic(label: str, model: str, _provider: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": DESCRIPTION_PROMPT.format(cell_name=label)}],
    )
    return resp.content[0].text.strip()


def _describe_openai(label: str, model: str, provider: str) -> str:
    from openai import OpenAI

    if provider == "kimi":
        client = OpenAI(api_key=os.environ.get("KIMI_API_KEY"), base_url="https://api.moonshot.ai/v1")
        model = "moonshot-v1-32k" if model == LLM_MODEL else model
    else:
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
        model = "gpt-4o" if model == LLM_MODEL else model
    resp = client.chat.completions.create(
        model=model,
        max_tokens=300,
        temperature=0.7,
        messages=[{"role": "user", "content": DESCRIPTION_PROMPT.format(cell_name=label)}],
    )
    return resp.choices[0].message.content.strip()


# ============================================================
# Step 2: embeddings (Qwen3-Embedding-8B)
# ============================================================

def embed_labels(
    labels: list[str],
    descriptions: dict[str, str],
    model_name: str,
) -> dict[str, np.ndarray]:
    """Encode each label's description into an L2-normalized embedding."""
    from sentence_transformers import SentenceTransformer

    print(f"  [embed] loading {model_name}")
    model = SentenceTransformer(model_name, model_kwargs={"torch_dtype": "auto"})
    texts = [descriptions[label] for label in labels]
    vecs = model.encode(texts, normalize_embeddings=True)
    return {label: np.asarray(vecs[i], dtype=np.float64) for i, label in enumerate(labels)}


# ============================================================
# Step 3: cosine + GHK
# ============================================================

def ghk(cosine: float, sigma: float) -> float:
    """Gaussian Heat Kernel centered at 1.0 (paper Eq. 2)."""
    return float(np.exp(-((cosine - 1.0) ** 2) / (2.0 * sigma**2)))


# ============================================================
# Pipeline
# ============================================================

def run_single(
    gt: str,
    pred: str,
    output: Optional[str] = None,
    dataset: str = "dataset",
    *,
    cell_id_col: str = "auto",
    cluster_col: str = "cluster",
    annotation_col: str = "Annotation",
    model: str = EMBEDDING_MODEL,
    sigma: float = SIGMA,
    threshold: float = THRESHOLD,
    generate_desc: bool = True,
    llm_provider: str = LLM_PROVIDER,
    llm_model: str = LLM_MODEL,
) -> dict:
    """Evaluate one (ground-truth, prediction) pair and return the metrics dict."""
    gt_path, pred_path = Path(gt), Path(pred)
    if not gt_path.exists():
        print(f"ERROR: ground truth not found: {gt_path}", file=sys.stderr)
        sys.exit(1)
    if not pred_path.exists():
        print(f"ERROR: prediction not found: {pred_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print(f"Dataset: {dataset}")
    print("=" * 70)

    df_gt = pd.read_csv(gt_path)
    df_ai = pd.read_csv(pred_path)
    print(f"  GT: {len(df_gt)} cells | AI: {len(df_ai)} cells")

    id_col, clust_col, gt_ann, ai_ann = _resolve_columns(
        df_gt, df_ai, cell_id_col, cluster_col, annotation_col
    )
    if id_col == "_row_index":
        df_gt = df_gt.assign(_row_index=df_gt.index)
        df_ai = df_ai.assign(_row_index=df_ai.index)

    _validate_consistency(df_ai, clust_col, ai_ann)

    # Build a per-cell table with both annotations and the AI cluster id.
    if len(df_gt) == len(df_ai):
        merged = pd.DataFrame({
            clust_col: df_ai[clust_col].values,
            "ai_annotation": df_ai[ai_ann].values,
            "gt_annotation": df_gt[gt_ann].values,
        })
    else:
        merged = (
            df_ai[[id_col, clust_col, ai_ann]]
            .rename(columns={ai_ann: "ai_annotation"})
            .merge(
                df_gt[[id_col, gt_ann]].rename(columns={gt_ann: "gt_annotation"}),
                on=id_col, how="inner",
            )
        )
        if merged.empty:
            raise ValueError(f"No cells matched between GT and AI on '{id_col}'.")
    print(f"  matched {len(merged)} cells across {merged[clust_col].nunique()} clusters")

    gt_labels = _cluster_mode_labels(merged, clust_col, "gt_annotation")
    ai_labels = _cluster_mode_labels(merged, clust_col, "ai_annotation")
    cell_counts = merged.groupby(clust_col).size().to_dict()

    unique_labels = sorted(set(gt_labels.values()) | set(ai_labels.values()))
    print(f"  {len(unique_labels)} unique labels")

    cache_path = Path(output).with_name(f"{dataset}_descriptions.json") if output else None
    descriptions = generate_descriptions(
        unique_labels, generate_desc, llm_provider, llm_model, cache_path
    )
    embeddings = embed_labels(unique_labels, descriptions, model)

    clusters = []
    total_cells = 0
    sum_ghk_cells = sum_cos_cells = 0.0
    sum_ghk_clust = sum_cos_clust = 0.0
    exact_clust = sem_clust = 0
    exact_cells = sem_cells = 0

    for cid in sorted(gt_labels):
        gt_label, ai_label = gt_labels[cid], ai_labels[cid]
        n = cell_counts[cid]
        cos = float(np.dot(embeddings[gt_label], embeddings[ai_label]))
        g = ghk(cos, sigma)
        exact = gt_label.strip().lower() == ai_label.strip().lower()
        semantic = cos >= threshold

        total_cells += n
        sum_ghk_cells += g * n
        sum_cos_cells += cos * n
        sum_ghk_clust += g
        sum_cos_clust += cos
        exact_clust += int(exact)
        sem_clust += int(semantic)
        exact_cells += n * int(exact)
        sem_cells += n * int(semantic)

        marker = "=" if exact else ("~" if semantic else "x")
        print(f"  [{marker}] cluster {cid}: GT='{gt_label[:24]}' AI='{ai_label[:24]}' "
              f"cos={cos:.3f} ghk={g:.3f}")
        clusters.append({
            "cluster_id": int(cid) if str(cid).lstrip("-").isdigit() else str(cid),
            "n_cells": int(n),
            "gt_label": gt_label,
            "ai_label": ai_label,
            "gt_description": descriptions[gt_label],
            "ai_description": descriptions[ai_label],
            "cosine": cos,
            "ghk": g,
            "exact_match": exact,
            "semantic_match": semantic,
        })

    n_clusters = len(gt_labels)
    summary = {
        # Headline metric reported in the paper (Table 3): GHK averaged over all cells.
        "ghk_cell_weighted": sum_ghk_cells / total_cells if total_cells else 0.0,
        "ghk_cluster_mean": sum_ghk_clust / n_clusters if n_clusters else 0.0,
        "cosine_cell_weighted": sum_cos_cells / total_cells if total_cells else 0.0,
        "cosine_cluster_mean": sum_cos_clust / n_clusters if n_clusters else 0.0,
        "exact_accuracy_cluster": exact_clust / n_clusters if n_clusters else 0.0,
        "semantic_accuracy_cluster": sem_clust / n_clusters if n_clusters else 0.0,
        "exact_accuracy_cell": exact_cells / total_cells if total_cells else 0.0,
        "semantic_accuracy_cell": sem_cells / total_cells if total_cells else 0.0,
        "total_clusters": n_clusters,
        "total_cells": int(total_cells),
        "sigma": sigma,
        "threshold": threshold,
        "embedding_model": model,
        "llm_model": llm_model if generate_desc else None,
        "generate_descriptions": generate_desc,
    }

    print("-" * 70)
    print(f"  GHK (cell-weighted, headline): {summary['ghk_cell_weighted']:.4f}")
    print(f"  GHK (cluster mean):            {summary['ghk_cluster_mean']:.4f}")
    print(f"  mean cosine (cell-weighted):   {summary['cosine_cell_weighted']:.4f}")
    print(f"  exact acc (cluster):           {summary['exact_accuracy_cluster']:.2%}")
    print(f"  semantic acc (cluster):        {summary['semantic_accuracy_cluster']:.2%}")

    results = {"dataset": dataset, "summary": summary, "clusters": clusters}
    if output:
        Path(output).write_text(json.dumps(results, indent=2))
        print(f"  saved: {output}")
    return results


# ============================================================
# CLI
# ============================================================

def load_config(path: str) -> dict:
    if yaml is None:
        raise ImportError("PyYAML is required for config files: pip install pyyaml")
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Cell Annotation Challenge evaluation (LLM descriptions -> Qwen3-8B -> cosine+GHK).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", nargs="+", metavar="YAML", help="One or more YAML config files")
    parser.add_argument("--gt", help="Ground truth CSV (overrides config)")
    parser.add_argument("--pred", help="Prediction CSV (overrides config)")
    parser.add_argument("--output-dir", default="results", help="Directory for result JSONs")

    cols = parser.add_argument_group("column names (override config)")
    cols.add_argument("--cell-id-col", default=None, help="Cell ID column (default: auto-detect)")
    cols.add_argument("--cluster-col", default=None, help="Cluster column (default: cluster)")
    cols.add_argument("--annotation-col", default=None, help="Annotation column (default: Annotation)")

    ev = parser.add_argument_group("evaluation parameters (override config)")
    ev.add_argument("--model", help=f"Embedding model (default: {EMBEDDING_MODEL})")
    ev.add_argument("--sigma", type=float, help=f"GHK sigma (default: {SIGMA})")
    ev.add_argument("--threshold", type=float, help=f"Cosine semantic-match threshold (default: {THRESHOLD})")
    ev.add_argument("--no-descriptions", action="store_true",
                    help="Disable LLM descriptions (embed raw labels; NOT the paper metric)")
    ev.add_argument("--llm-provider", choices=["anthropic", "openai", "kimi"])
    ev.add_argument("--llm-model", help="LLM model for description generation")

    args = parser.parse_args()

    if not args.config and not (args.gt and args.pred):
        parser.error("Provide either --config or both --gt and --pred")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.config:
        configs = [load_config(p) for p in args.config]
    else:
        configs = [{"dataset": "custom", "gt": args.gt, "pred": args.pred}]

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
        run_single(
            gt=cfg["gt"],
            pred=cfg["pred"],
            output=str(out_dir / f"{dataset}_results.json"),
            dataset=dataset,
            cell_id_col=cfg.get("cell_id_col", "auto"),
            cluster_col=cfg.get("cluster_col", "cluster"),
            annotation_col=cfg.get("annotation_col", "Annotation"),
            model=cfg.get("model", EMBEDDING_MODEL),
            sigma=cfg.get("sigma", SIGMA),
            threshold=cfg.get("threshold", THRESHOLD),
            generate_desc=cfg.get("generate_descriptions", True),
            llm_provider=cfg.get("llm_provider", LLM_PROVIDER),
            llm_model=cfg.get("llm_model", LLM_MODEL),
        )

    print(f"\nAll evaluations complete. Results in: {out_dir}/")


if __name__ == "__main__":
    main()
