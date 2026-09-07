#!/usr/bin/env python3
"""Explore power of ONE Wilcoxon test using RHFS as a variability anchor.

Median-centered differences are pooled across three RHFS contrasts and sampled
as one noise population. Hypothetical shifts are tested against zero. This does
not simulate full H1: no three-comparator conjunction, throughput noninferiority,
15-percent shifted null hypothesis, or between-stratum Holm adjustment. Pooled
pairs from the same RHFS instance are not independent experimental instances.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import scipy
from scipy.stats import wilcoxon


TARGET_METHOD = "M5_ATC_EVENT"
COMPARATOR_METHODS = (
    "M0_FIFO_OFFICIAL",
    "M3_EVENT_REACTIVE",
    "M6_FIFO_PRIORITY_EVENT",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = REPOSITORY_ROOT / "data/rhfs_method_performance_matrix.csv"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "data"
ANALYSIS_SCOPE = "exploratory_single_wilcoxon_pooled_contrast"
OUTPUT_NAMES = ("power_analysis_rhfs_summary.csv", "power_curve_reference.csv",
                "power_analysis_rhfs_metadata.json")


@dataclass(frozen=True)
class BootstrapResult:
    stratum: str
    n_effective: int
    mde80: float
    power_at_5: float
    power_at_15: float
    pair_count: int
    noise_sd_min: float
    median_comparator_p95_min: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explore ONE Wilcoxon test on pooled RHFS noise; this is not full-H1 power."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Destination without existing output files; historical outputs are preserved.")
    parser.add_argument("--replicates", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260531)
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()
    if args.replicates <= 0 or not 0 < args.alpha < 1:
        parser.error("replicates must be positive and alpha must be strictly between 0 and 1")
    return args


def load_pairs(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    methods = {TARGET_METHOD, *COMPARATOR_METHODS}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["footprint_member"] != "True":
                continue
            if row["method_name"] not in methods:
                continue
            rows[(row["instance_id"], row["method_name"])] = row

    diffs: list[float] = []
    comparator_p95: list[float] = []
    for (instance_id, method), target_row in sorted(rows.items()):
        if method != TARGET_METHOD:
            continue
        target_p95 = float(target_row["flow_p95"])
        for comparator in COMPARATOR_METHODS:
            comparator_row = rows.get((instance_id, comparator))
            if comparator_row is None:
                continue
            comparator_value = float(comparator_row["flow_p95"])
            diffs.append(target_p95 - comparator_value)
            comparator_p95.append(comparator_value)

    if not diffs:
        raise ValueError(f"No RHFS pairs found in {path}")

    centered_noise = np.asarray(diffs, dtype=float) - float(np.median(diffs))
    return centered_noise, np.asarray(comparator_p95, dtype=float)


def rejection_rate(
    noise: np.ndarray,
    comparator_p95: np.ndarray,
    *,
    n_effective: int,
    effect: float,
    replicates: int,
    alpha: float,
    rng: np.random.Generator,
) -> float:
    rejections = 0
    population_n = len(noise)
    for _ in range(replicates):
        idx = rng.integers(0, population_n, size=n_effective)
        shifted = noise[idx] - effect * comparator_p95[idx]
        p_value = wilcoxon(
            shifted,
            alternative="less",
            zero_method="wilcox",
            method="asymptotic",
        ).pvalue
        rejections += int(p_value < alpha)
    return rejections / replicates


def estimate_mde80(
    noise: np.ndarray,
    comparator_p95: np.ndarray,
    *,
    n_effective: int,
    replicates: int,
    alpha: float,
    seed: int,
) -> tuple[float, float]:
    lo, hi = 0.0, 0.20
    for _ in range(12):
        mid = (lo + hi) / 2
        rng = np.random.default_rng(seed)
        power = rejection_rate(
            noise,
            comparator_p95,
            n_effective=n_effective,
            effect=mid,
            replicates=replicates,
            alpha=alpha,
            rng=rng,
        )
        if power >= 0.80:
            hi = mid
        else:
            lo = mid

    rng = np.random.default_rng(seed)
    power_at_mde = rejection_rate(
        noise,
        comparator_p95,
        n_effective=n_effective,
        effect=hi,
        replicates=replicates,
        alpha=alpha,
        rng=rng,
    )
    return hi, power_at_mde


def run_stratum(
    name: str,
    n_effective: int,
    noise: np.ndarray,
    comparator_p95: np.ndarray,
    *,
    replicates: int,
    alpha: float,
    seed: int,
) -> tuple[BootstrapResult, float]:
    mde80, power_at_mde = estimate_mde80(
        noise,
        comparator_p95,
        n_effective=n_effective,
        replicates=replicates,
        alpha=alpha,
        seed=seed + n_effective,
    )

    def power(effect: float, offset: int) -> float:
        return rejection_rate(
            noise,
            comparator_p95,
            n_effective=n_effective,
            effect=effect,
            replicates=replicates,
            alpha=alpha,
            rng=np.random.default_rng(seed + n_effective + offset),
        )

    result = BootstrapResult(
        stratum=name,
        n_effective=n_effective,
        mde80=mde80,
        power_at_5=power(0.05, 5),
        power_at_15=power(0.15, 15),
        pair_count=len(noise),
        noise_sd_min=float(np.std(noise, ddof=1)),
        median_comparator_p95_min=float(np.median(comparator_p95)),
    )
    return result, power_at_mde


def write_summary(
    output_dir: Path,
    results: list[tuple[BootstrapResult, float]],
    *,
    replicates: int,
    alpha: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "power_analysis_rhfs_summary.csv").open(
        "x", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stratum",
                "n_effective",
                "rhfs_pair_count",
                "bootstrap_replicates",
                "alpha",
                "mde80_pct",
                "power_at_mde",
                "power_at_5_pct",
                "power_at_15_pct",
                "noise_sd_min",
                "median_comparator_p95_min",
            ],
        )
        writer.writeheader()
        for result, power_at_mde in results:
            writer.writerow(
                {
                    "stratum": result.stratum,
                    "n_effective": result.n_effective,
                    "rhfs_pair_count": result.pair_count,
                    "bootstrap_replicates": replicates,
                    "alpha": alpha,
                    "mde80_pct": 100 * result.mde80,
                    "power_at_mde": power_at_mde,
                    "power_at_5_pct": result.power_at_5,
                    "power_at_15_pct": result.power_at_15,
                    "noise_sd_min": result.noise_sd_min,
                    "median_comparator_p95_min": result.median_comparator_p95_min,
                }
            )

    with (output_dir / "power_curve_reference.csv").open(
        "x", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["stratum", "effect_pct", "power", "point_type"],
        )
        writer.writeheader()
        for result, power_at_mde in results:
            writer.writerow(
                {
                    "stratum": result.stratum,
                    "effect_pct": 100 * result.mde80,
                    "power": power_at_mde,
                    "point_type": "MDE80",
                }
            )
            writer.writerow(
                {
                    "stratum": result.stratum,
                    "effect_pct": 5.0,
                    "power": result.power_at_5,
                    "point_type": "5pct",
                }
            )
            writer.writerow(
                {
                    "stratum": result.stratum,
                    "effect_pct": 15.0,
                    "power": result.power_at_15,
                    "point_type": "15pct_hypothetical",
                }
            )


def main() -> None:
    args = parse_args()
    collisions = [args.output_dir / name for name in OUTPUT_NAMES if (args.output_dir / name).exists()]
    if collisions:
        raise FileExistsError(f"Preserving existing outputs {collisions}; choose a new --output-dir")
    source_bytes = args.input.read_bytes()
    input_sha256 = hashlib.sha256(source_bytes).hexdigest()
    noise, comparator_p95 = load_pairs(args.input)
    strata = [("Média congestão", 600), ("Alta congestão", 2800)]
    results = [
        run_stratum(
            name,
            n_effective,
            noise,
            comparator_p95,
            replicates=args.replicates,
            alpha=args.alpha,
            seed=args.seed,
        )
        for name, n_effective in strata
    ]
    if args.input.read_bytes() != source_bytes:
        raise RuntimeError(f"RHFS input changed during analysis: {args.input}")
    write_summary(args.output_dir, results, replicates=args.replicates, alpha=args.alpha)
    metadata = {
        "schema_version": 1,
        "status": "GENERATED_BY_THIS_INVOCATION",
        "analysis_scope": ANALYSIS_SCOPE,
        "full_h1_power": False,
        "excluded_from_power_model": ["conjunction of three comparators", "throughput noninferiority",
                                      "gain test shifted by 15 percent threshold", "Holm between strata"],
        "input": {"path": str(args.input.resolve()), "sha256": input_sha256, "bytes": len(source_bytes)},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parameters": {"replicates": args.replicates, "seed": args.seed, "alpha": args.alpha,
                       "target_method": TARGET_METHOD, "pooled_comparators": list(COMPARATOR_METHODS),
                       "n_effective": [600, 2800], "pooled_pair_count": len(noise),
                       "mde_search_interval": [0, 0.20], "mde_bisection_steps": 12,
                       "seed_rule": "seed+n_effective for MDE; additionally +5 or +15 for fixed effects",
                       "alternative": "less", "zero_method": "wilcox", "method": "asymptotic"},
        "sampling_unit": "pooled centered target-minus-comparator difference; ignores within-instance dependence",
        "runtime": {"python": platform.python_version(), "executable": sys.executable,
                    "numpy": np.__version__, "scipy": scipy.__version__},
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "outputs": [{"name": name, "sha256": hashlib.sha256((args.output_dir / name).read_bytes()).hexdigest()}
                    for name in OUTPUT_NAMES[:2]],
    }
    with (args.output_dir / OUTPUT_NAMES[2]).open("x", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("Exploratory single-test anchor; NOT power of full H1.")
    for result, power_at_mde in results:
        print(
            f"{result.stratum}: n={result.n_effective}; "
            f"MDE80={100 * result.mde80:.2f}%; "
            f"power@MDE={power_at_mde:.3f}; "
            f"power@5%={result.power_at_5:.3f}; "
            f"power@15%={result.power_at_15:.3f}"
        )


if __name__ == "__main__":
    main()
