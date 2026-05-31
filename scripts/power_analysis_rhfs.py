#!/usr/bin/env python3
"""Estimate confirmatory-protocol power from the frozen RHFS performance matrix.

The TCC protocol uses the RHFS matrix only as a variability anchor. Differences
are centered before imposing hypothetical H1 shifts, so observed RHFS superiority
does not become evidence for the future TCC-II experiment.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon


TARGET_METHOD = "M5_ATC_EVENT"
COMPARATOR_METHODS = (
    "M0_FIFO_OFFICIAL",
    "M3_EVENT_REACTIVE",
    "M6_FIFO_PRIORITY_EVENT",
)
DEFAULT_DATA = Path("../agro_yard_dfjsp_paper/catalog/method_performance_matrix.csv")
DEFAULT_OUTPUT_DIR = Path("data")


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
        description="Bootstrap RHFS p95 differences to estimate Wilcoxon power."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--replicates", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260531)
    parser.add_argument("--alpha", type=float, default=0.05)
    return parser.parse_args()


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
        "w", newline="", encoding="utf-8"
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
        "w", newline="", encoding="utf-8"
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
                    "point_type": "H1",
                }
            )


def main() -> None:
    args = parse_args()
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
    write_summary(args.output_dir, results, replicates=args.replicates, alpha=args.alpha)

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
