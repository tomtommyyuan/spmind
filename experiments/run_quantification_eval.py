#!/usr/bin/env python3
"""
Compare MCquant output with GT CSV using segmentation-agnostic metrics.

Metrics (matching paper Section X):
  1. Pearson r on marker sums  - Linear correlation of marker abundances
  2. Spearman ρ on marker sums - Rank correlation of marker abundances
  3. Correlation matrix cosine similarity - Marker-marker co-expression preservation
  4. MMD on phenotype vectors  - Multivariate cell population similarity
  5. Grid-based Spatial Spearman - Spatial anchoring (signal in correct location)

Usage:
    python run_quantification_eval.py --mcquant mcquant.csv --gt gt.csv
    python run_quantification_eval.py --mcquant mcquant.csv --gt gt.csv --output results.csv
    python run_quantification_eval.py --mcquant mcquant.csv --gt gt.csv --tile-size 100 --seed 42
"""

import argparse
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import cdist, cosine


def extract_marker_name_from_gt(col_name):
    """Extract the short marker name from GT column name."""
    match = re.search(r'([^:]+):Cyc_\d+_ch_\d+', col_name)
    if match:
        full_name = match.group(1).strip()
        if ' - ' in full_name:
            return full_name.split(' - ')[0].strip()
        return full_name
    return None


def get_gt_marker_columns(gt_df):
    """Get mapping of marker names to GT column names."""
    marker_to_col = {}
    for col in gt_df.columns:
        marker = extract_marker_name_from_gt(col)
        if marker:
            marker_to_col[marker] = col
    return marker_to_col


def arcsinh_transform(x, cofactor=5):
    """Apply arcsinh transform commonly used in cytometry."""
    return np.arcsinh(x / cofactor)


def compute_grid_spatial_correlation(mcquant_df, gt_df, matched_markers,
                                      mcquant_x='X_centroid', mcquant_y='Y_centroid',
                                      gt_x='X:X', gt_y='Y:Y',
                                      tile_size=100):
    """
    Compute grid-based spatial Spearman correlation (segmentation-agnostic).

    For each tile, computes the mean intensity per marker (not sum), normalizing
    by cell count to be robust to segmentation density differences. Reports the
    median Spearman correlation across all valid markers.
    """
    if mcquant_x not in mcquant_df.columns or mcquant_y not in mcquant_df.columns:
        return {'valid': False, 'reason': f'MCquant missing {mcquant_x} or {mcquant_y}'}
    if gt_x not in gt_df.columns or gt_y not in gt_df.columns:
        return {'valid': False, 'reason': f'GT missing {gt_x} or {gt_y}'}

    all_x = np.concatenate([mcquant_df[mcquant_x].values, gt_df[gt_x].values])
    all_y = np.concatenate([mcquant_df[mcquant_y].values, gt_df[gt_y].values])

    x_min, x_max = all_x.min(), all_x.max()
    y_min, y_max = all_y.min(), all_y.max()

    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size))

    mcquant_tile_x = ((mcquant_df[mcquant_x] - x_min) / tile_size).astype(int)
    mcquant_tile_y = ((mcquant_df[mcquant_y] - y_min) / tile_size).astype(int)
    mcquant_tile_id = mcquant_tile_x * n_tiles_y + mcquant_tile_y

    gt_tile_x = ((gt_df[gt_x] - x_min) / tile_size).astype(int)
    gt_tile_y = ((gt_df[gt_y] - y_min) / tile_size).astype(int)
    gt_tile_id = gt_tile_x * n_tiles_y + gt_tile_y

    mcquant_df_temp = mcquant_df.copy()
    gt_df_temp = gt_df.copy()
    mcquant_df_temp['_tile_id'] = mcquant_tile_id
    gt_df_temp['_tile_id'] = gt_tile_id

    per_marker_results = []
    spearman_list = []

    for m in matched_markers:
        marker = m['mcquant_col']
        gt_col = m['gt_col']

        mcquant_tile_means = mcquant_df_temp.groupby('_tile_id')[marker].mean()
        gt_tile_means = gt_df_temp.groupby('_tile_id')[gt_col].mean()

        common_tiles = mcquant_tile_means.index.intersection(gt_tile_means.index)

        if len(common_tiles) < 5:
            per_marker_results.append({
                'marker': marker, 'spearman': np.nan,
                'n_tiles': len(common_tiles), 'valid': False,
            })
            continue

        mcquant_vals = mcquant_tile_means[common_tiles].values
        gt_vals = gt_tile_means[common_tiles].values

        spearman_r, _ = stats.spearmanr(mcquant_vals, gt_vals)

        per_marker_results.append({
            'marker': marker, 'spearman': spearman_r,
            'n_tiles': len(common_tiles), 'valid': True,
        })

        if not np.isnan(spearman_r):
            spearman_list.append(spearman_r)

    return {
        'valid': True,
        'tile_size': tile_size,
        'n_tiles_x': n_tiles_x,
        'n_tiles_y': n_tiles_y,
        'per_marker': per_marker_results,
        'mean_spearman': np.mean(spearman_list) if spearman_list else np.nan,
        'median_spearman': np.median(spearman_list) if spearman_list else np.nan,
        'n_markers_valid': len(spearman_list),
    }


def compute_mmd_rbf(X, Y, gamma=None, rng=None):
    """
    Compute MMD^2 with RBF kernel using the unbiased U-statistic estimator.

    Bandwidth is set via the median heuristic on a 1000-cell subsample.
    """
    X = np.asarray(X)
    Y = np.asarray(Y)

    if rng is None:
        rng = np.random.default_rng(42)

    if gamma is None:
        n_sample = min(1000, len(X), len(Y))
        X_sample = X[rng.choice(len(X), n_sample, replace=False)]
        Y_sample = Y[rng.choice(len(Y), n_sample, replace=False)]
        combined = np.vstack([X_sample, Y_sample])
        dists = cdist(combined, combined, 'euclidean')
        median_dist = np.median(dists[dists > 0])
        gamma = 1.0 / (2 * median_dist ** 2) if median_dist > 0 else 1.0

    def rbf_kernel_mean(A, B, gamma_val, chunk_size=1000):
        total = 0.0
        count = 0
        for i in range(0, len(A), chunk_size):
            A_chunk = A[i:i+chunk_size]
            for j in range(0, len(B), chunk_size):
                B_chunk = B[j:j+chunk_size]
                dists_sq = cdist(A_chunk, B_chunk, 'sqeuclidean')
                K_chunk = np.exp(-gamma_val * dists_sq)
                total += K_chunk.sum()
                count += K_chunk.size
        return total / count if count > 0 else 0.0

    n_x, n_y = len(X), len(Y)

    # E[k(X, X')] — unbiased (diagonal excluded)
    if n_x > 1:
        K_XX = 0.0
        for i in range(0, n_x, 500):
            X_chunk = X[i:i+500]
            dists_sq = cdist(X_chunk, X, 'sqeuclidean')
            K = np.exp(-gamma * dists_sq)
            for k, idx in enumerate(range(i, min(i+500, n_x))):
                if k < len(K):
                    K[k, idx] = 0
            K_XX += K.sum()
        mean_K_XX = K_XX / (n_x * (n_x - 1))
    else:
        mean_K_XX = 0.0

    # E[k(Y, Y')] — unbiased (diagonal excluded)
    if n_y > 1:
        K_YY = 0.0
        for i in range(0, n_y, 500):
            Y_chunk = Y[i:i+500]
            dists_sq = cdist(Y_chunk, Y, 'sqeuclidean')
            K = np.exp(-gamma * dists_sq)
            for k, idx in enumerate(range(i, min(i+500, n_y))):
                if k < len(K):
                    K[k, idx] = 0
            K_YY += K.sum()
        mean_K_YY = K_YY / (n_y * (n_y - 1))
    else:
        mean_K_YY = 0.0

    mean_K_XY = rbf_kernel_mean(X, Y, gamma)
    mmd_sq = mean_K_XX + mean_K_YY - 2 * mean_K_XY

    return max(0, mmd_sq), gamma


def compute_correlation_matrix_similarity(mcquant_df, gt_df, matched_markers):
    """
    Compute cosine similarity between marker-marker Spearman correlation matrices.

    Uses upper triangle only (excluding diagonal) to avoid inflation from
    self-correlations that are always 1.
    """
    mcquant_cols = [m['mcquant_col'] for m in matched_markers]
    gt_cols = [m['gt_col'] for m in matched_markers]

    mcquant_transformed = mcquant_df[mcquant_cols].apply(arcsinh_transform)
    gt_transformed = gt_df[gt_cols].apply(arcsinh_transform)

    mcquant_corr = mcquant_transformed.corr(method='spearman').values
    gt_corr = gt_transformed.corr(method='spearman').values

    mcquant_corr = np.nan_to_num(mcquant_corr, nan=0.0)
    gt_corr = np.nan_to_num(gt_corr, nan=0.0)

    n = len(matched_markers)
    upper_idx = np.triu_indices(n, k=1)

    mcquant_upper = mcquant_corr[upper_idx]
    gt_upper = gt_corr[upper_idx]

    cos_sim = 1 - cosine(mcquant_upper, gt_upper)

    return {
        'cosine_similarity': cos_sim,
        'n_pairs': len(mcquant_upper),
    }


def compare_quantification(mcquant_csv, gt_csv, output_csv=None, tile_size=100, seed=42):
    """
    Compare MCquant output with GT using segmentation-agnostic metrics.

    Computes all five metrics described in the paper: Pearson r, Spearman rho,
    correlation matrix cosine similarity, MMD, and grid-based spatial Spearman.
    """
    rng = np.random.default_rng(seed)
    print(f"\n{'='*70}")
    print("Quantification Comparison: MCquant vs GT")
    print("(Segmentation-Agnostic Metrics)")
    print(f"{'='*70}")

    print(f"\nLoading MCquant: {os.path.basename(mcquant_csv)}")
    mcquant_df = pd.read_csv(mcquant_csv)
    print(f"  Cells: {len(mcquant_df)}")

    print(f"\nLoading GT: {os.path.basename(gt_csv)}")
    gt_df = pd.read_csv(gt_csv)
    print(f"  Cells: {len(gt_df)}")

    gt_marker_map = get_gt_marker_columns(gt_df)
    print(f"\nFound {len(gt_marker_map)} markers in GT")

    # Match markers between MCquant and GT
    matched_markers = []
    mcquant_sums = []
    gt_sums = []

    print(f"\n{'='*70}")
    print("PER-MARKER ANALYSIS")
    print(f"{'='*70}")
    print(f"\n{'Marker':<16} {'MCquant Sum':>12} {'GT Sum':>12} {'Ratio':>8}")
    print("-" * 52)

    for marker, gt_col in sorted(gt_marker_map.items()):
        if marker not in mcquant_df.columns:
            continue

        mcquant_sum = mcquant_df[marker].sum()
        gt_sum = gt_df[gt_col].sum()
        ratio = mcquant_sum / gt_sum if gt_sum != 0 else np.inf

        print(f"{marker:<16} {mcquant_sum:>12.1f} {gt_sum:>12.1f} {ratio:>8.3f}")

        matched_markers.append({
            'marker': marker,
            'mcquant_col': marker,
            'gt_col': gt_col,
            'mcquant_sum': mcquant_sum,
            'gt_sum': gt_sum,
            'ratio': ratio,
        })

        mcquant_sums.append(mcquant_sum)
        gt_sums.append(gt_sum)

    print("-" * 52)
    print(f"Matched markers: {len(matched_markers)}")

    # ================================================================
    # COMPUTE METRICS
    # ================================================================
    print(f"\n{'='*70}")
    print("SEGMENTATION-AGNOSTIC QUALITY METRICS")
    print(f"{'='*70}")

    metrics = {}
    mcquant_arr = np.array(mcquant_sums)
    gt_arr = np.array(gt_sums)

    # --- Metric 1: Pearson r ---
    pearson_r, pearson_p = stats.pearsonr(mcquant_arr, gt_arr)
    metrics['pearson_r'] = pearson_r
    metrics['pearson_p'] = pearson_p

    print(f"\n[1] Pearson r (marker sums)")
    print(f"    r = {pearson_r:.4f}  (p = {pearson_p:.2e})")
    if pearson_r > 0.9:
        print(f"    Excellent linear agreement")
    elif pearson_r > 0.7:
        print(f"    Good linear agreement")
    else:
        print(f"    Moderate linear agreement")

    # --- Metric 2: Spearman ρ ---
    spearman_r, spearman_p = stats.spearmanr(mcquant_arr, gt_arr)
    metrics['spearman_rho'] = spearman_r
    metrics['spearman_p'] = spearman_p

    print(f"\n[2] Spearman rho (marker sums)")
    print(f"    rho = {spearman_r:.4f}  (p = {spearman_p:.2e})")
    if spearman_r > 0.9:
        print(f"    Excellent rank agreement")
    elif spearman_r > 0.7:
        print(f"    Good rank agreement")
    else:
        print(f"    Moderate rank agreement")

    # --- Metric 3: Correlation Matrix Similarity ---
    corr_sim = compute_correlation_matrix_similarity(mcquant_df, gt_df, matched_markers)
    metrics['corr_matrix_cosine'] = corr_sim['cosine_similarity']

    print(f"\n[3] Marker Correlation Matrix Similarity")
    print(f"    Cosine similarity = {corr_sim['cosine_similarity']:.4f}")
    if corr_sim['cosine_similarity'] > 0.9:
        print(f"    Excellent: co-expression patterns preserved")
    elif corr_sim['cosine_similarity'] > 0.7:
        print(f"    Good: co-expression patterns largely preserved")
    else:
        print(f"    Moderate: some co-expression differences")

    # --- Metric 4: MMD on Phenotype Vectors ---
    print(f"\n[4] MMD on Phenotype Vectors (arcsinh-transformed)")
    print(f"    Computing multivariate population distance...")

    mcquant_cols = [m['mcquant_col'] for m in matched_markers]
    gt_cols = [m['gt_col'] for m in matched_markers]

    mcquant_phenotypes = arcsinh_transform(mcquant_df[mcquant_cols].values)
    gt_phenotypes = arcsinh_transform(gt_df[gt_cols].values)

    mcquant_phenotypes = mcquant_phenotypes[~np.isnan(mcquant_phenotypes).any(axis=1)]
    gt_phenotypes = gt_phenotypes[~np.isnan(gt_phenotypes).any(axis=1)]

    mmd_sq, gamma = compute_mmd_rbf(mcquant_phenotypes, gt_phenotypes, rng=rng)
    mmd = np.sqrt(mmd_sq)

    metrics['mmd'] = mmd
    metrics['mmd_squared'] = mmd_sq
    metrics['mmd_gamma'] = gamma
    metrics['random_seed'] = seed

    print(f"    MMD = {mmd:.4f}  (MMD^2 = {mmd_sq:.6f})")
    print(f"    RBF gamma = {gamma:.6f} (median heuristic)")
    if mmd < 0.1:
        print(f"    Excellent: cell populations nearly identical")
    elif mmd < 0.2:
        print(f"    Good: cell populations similar")
    elif mmd < 0.4:
        print(f"    Moderate: some population differences")
    else:
        print(f"    Poor: significant population differences")

    # --- Metric 5: Grid-Based Spatial Spearman ---
    print(f"\n[5] Grid-Based Spatial Correlation (tile={tile_size}px)")

    spatial_result = compute_grid_spatial_correlation(
        mcquant_df, gt_df, matched_markers, tile_size=tile_size
    )

    if spatial_result['valid']:
        median_spatial = spatial_result['median_spearman']
        mean_spatial = spatial_result['mean_spearman']

        metrics['spatial_spearman_median'] = median_spatial
        metrics['spatial_spearman_mean'] = mean_spatial
        metrics['spatial_tile_size'] = tile_size

        print(f"    Median Spearman = {median_spatial:.4f}")
        print(f"    Mean Spearman   = {mean_spatial:.4f}")
        print(f"    Valid markers   = {spatial_result['n_markers_valid']}/{len(matched_markers)}")

        if median_spatial > 0.7:
            print(f"    Good: signal spatially anchored correctly")
        elif median_spatial > 0.5:
            print(f"    Moderate: partial spatial agreement")
        else:
            print(f"    Poor: weak spatial correlation")
    else:
        median_spatial = np.nan
        print(f"    Cannot compute: {spatial_result.get('reason', 'missing coordinates')}")
        metrics['spatial_spearman_median'] = np.nan
        metrics['spatial_spearman_mean'] = np.nan

    # ================================================================
    # SUMMARY TABLE
    # ================================================================
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"\n  {'Metric':<35} {'Value':>10}")
    print(f"  {'-'*47}")
    print(f"  {'Pearson r':<35} {pearson_r:>10.4f}")
    print(f"  {'Spearman rho':<35} {spearman_r:>10.4f}")
    print(f"  {'Corr Matrix Cosine Sim':<35} {corr_sim['cosine_similarity']:>10.4f}")
    print(f"  {'MMD':<35} {mmd:>10.4f}")
    if not np.isnan(median_spatial):
        print(f"  {'Spatial Spearman (median)':<35} {median_spatial:>10.4f}")
    else:
        print(f"  {'Spatial Spearman (median)':<35} {'N/A':>10}")

    # Save results
    results_df = pd.DataFrame(matched_markers)

    if output_csv:
        results_df.to_csv(output_csv, index=False)
        print(f"\nPer-marker results saved to: {output_csv}")

        metrics_csv = output_csv.replace('.csv', '_metrics.csv')
        pd.DataFrame([metrics]).to_csv(metrics_csv, index=False)
        print(f"Summary metrics saved to: {metrics_csv}")

    return results_df, metrics


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate quantification accuracy using segmentation-agnostic metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Metrics computed:
  1. Pearson r           Linear correlation of marker abundances
  2. Spearman rho        Rank correlation of marker abundances
  3. Corr Matrix         Marker co-expression pattern similarity (cosine)
  4. MMD                 Multivariate phenotype population similarity
  5. Spatial Spearman    Grid-based spatial anchoring (median across markers)
""",
    )
    parser.add_argument("--mcquant", required=True, help="Path to MCquant output CSV")
    parser.add_argument("--gt", required=True, help="Path to ground truth CSV")
    parser.add_argument("--output", default=None, help="Path to save per-marker results CSV")
    parser.add_argument("--tile-size", type=int, default=100, help="Grid tile size in pixels (default: 100)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")

    args = parser.parse_args()

    compare_quantification(
        mcquant_csv=args.mcquant,
        gt_csv=args.gt,
        output_csv=args.output,
        tile_size=args.tile_size,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
