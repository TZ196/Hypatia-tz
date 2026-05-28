"""Low-rank OD traffic matrix generation for backbone-style traffic matrix completion experiments.

Generates an N×N traffic matrix T = U @ V^T where U, V are N×k factor matrices
sampled from a log-normal distribution. The result is a low-rank matrix with
heavy-tailed traffic distribution — mimicking the gravity-model structure of
real backbone networks.
"""

import numpy as np


def generate_factor_matrix(n: int, k: int, distribution: str, rng: np.random.Generator) -> np.ndarray:
    """Sample an n×k factor matrix from the specified distribution.

    Args:
        n: number of rows (ground stations)
        k: number of columns (rank / latent factors)
        distribution: "lognormal", "pareto", or "uniform"
        rng: numpy random generator for reproducibility
    """
    if distribution == "lognormal":
        return rng.lognormal(mean=0.0, sigma=1.0, size=(n, k))
    elif distribution == "pareto":
        # Pareto with shape=2: heavy-tailed, finite mean, infinite variance
        return rng.pareto(a=2.0, size=(n, k))
    elif distribution == "uniform":
        return rng.uniform(low=0.1, high=2.0, size=(n, k))
    else:
        raise ValueError(f"Unknown distribution: {distribution}. "
                         f"Choose from: lognormal, pareto, uniform")


def generate_od_matrix(n: int, rank: int, density: float,
                       distribution: str = "lognormal",
                       noise_sigma: float = 0.1,
                       seed: int = 123456789) -> tuple[list[tuple[int, int]], list[int], np.ndarray]:
    """Generate an N×N OD traffic matrix using low-rank factorization.

    Algorithm:
      1. Sample U (N×k), V (N×k) from the specified distribution
      2. T_clean = U @ V^T  →  N×N matrix (exact rank ≤ k)
      3. Zero out diagonal (no self-traffic)
      4. Add log-normal noise: T[i,j] *= exp(ε), ε ~ N(0, noise_sigma²)
      5. Keep top density fraction of entries, zero the rest
      6. Quantize to integer byte sizes

    Args:
        n: number of ground stations
        rank: rank of the low-rank matrix (k ≥ 1)
        density: fraction of OD pairs with non-zero traffic (0 < density ≤ 1)
        distribution: factor distribution — "lognormal", "pareto", or "uniform"
        noise_sigma: standard deviation of multiplicative log-noise
        seed: random seed for reproducibility

    Returns:
        (list_from_to, list_flow_sizes, T_clean):
          - list_from_to: list of (from_idx, to_idx) where from_idx/to_idx are
            0-based local indices (actual node ID = idx + gs_start_id)
          - list_flow_sizes: list of flow sizes in bytes (rounded from noisy+truncated T)
          - T_clean: the N×N low-rank matrix before noise and truncation (ground truth)
    """
    if rank < 1:
        raise ValueError(f"rank must be >= 1, got {rank}")
    if density <= 0 or density > 1:
        raise ValueError(f"density must be in (0, 1], got {density}")

    rng = np.random.default_rng(seed)

    # Step 1: sample factor matrices
    U = generate_factor_matrix(n, rank, distribution, rng)
    V = generate_factor_matrix(n, rank, distribution, rng)

    # Step 2: construct traffic matrix T = U @ V^T (exact rank ≤ k)
    T_clean = U @ V.T  # shape: N×N
    np.fill_diagonal(T_clean, 0.0)

    # Step 3: make a copy for the noisy/truncated version
    T = T_clean.copy()

    # Step 4: multiplicative log-noise
    noise = rng.lognormal(mean=0.0, sigma=noise_sigma, size=(n, n))
    T = T * noise
    np.fill_diagonal(T, 0.0)  # re-zero diagonal after noise

    # Step 5: density control — keep top (density * N * (N-1)) entries
    off_diagonal = T[~np.eye(n, dtype=bool)]
    num_keep = round(density * len(off_diagonal))
    if num_keep == 0:
        num_keep = 1  # at least one flow
    threshold = np.partition(off_diagonal, -num_keep)[-num_keep]
    if threshold <= 0:
        positive = off_diagonal[off_diagonal > 0]
        if len(positive) > 0:
            threshold = np.min(positive)
    T[T < threshold] = 0.0

    # Step 6: quantize to integer flow sizes (1-byte minimum)
    list_from_to: list[tuple[int, int]] = []
    list_flow_sizes: list[int] = []

    rows, cols = np.nonzero(T)
    for i, j in zip(rows, cols):
        if i == j:
            continue
        flow_size = max(1, round(float(T[i, j])))
        list_from_to.append((int(i), int(j)))
        list_flow_sizes.append(flow_size)

    return list_from_to, list_flow_sizes, T_clean
