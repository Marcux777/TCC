"""Confirmatory paired statistics for the PequiFlux experiment.

The analysis boundary is deliberately strict: rows must describe one complete,
paired protocol grid and every row must carry the same configuration digest.
No cell is inferred from another run and no missing observation is replaced by
a default.  The long form accepted here mirrors ``results.csv`` while the
small paired form is useful for already materialised analysis tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
from statistics import median as decimal_median
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

from .config import (
    ExperimentConfig,
    ScenarioConfig,
    config_hash,
    factorial_scenarios,
    validate_confirmatory_config,
)


PRIMARY_COMPARATORS: tuple[str, ...] = (
    "fifo_flow_faithful",
    "priority_local",
    "fixed_score",
)
TREATMENT_POLICY = "lexicographic"
# ``fifo_strict`` remains a required panel policy and is persisted in the
# confirmatory matrix, but main.tex reserves it as a descriptive control.  It
# is deliberately not one of the three substantive H1 contrasts above.
STRATA: tuple[str, ...] = ("medium", "high")
ALPHA = 0.05
TARGET_RELATIVE_IMPROVEMENT = 0.15
BOOTSTRAP_SEED = 20260901
BOOTSTRAP_ITERATIONS = 2000
INVALID_INPUT = "INVALID_INPUT"

class PairingError(ValueError):
    """Raised when a confirmatory table reaches the ``INVALID_INPUT`` boundary."""

    boundary = INVALID_INPUT

    def __init__(self, message: str) -> None:
        if not isinstance(message, str) or not message:
            raise TypeError("PairingError message must be a non-empty string")
        self.reason = message
        super().__init__(f"{INVALID_INPUT}: {message}")


def _finite_array(name: str, values: Sequence[Any]) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PairingError(f"{name} must contain numeric values") from exc
    if array.ndim != 1 or array.size == 0:
        raise PairingError(f"{name} must be a non-empty one-dimensional vector")
    if not np.all(np.isfinite(array)):
        raise PairingError(f"{name} must contain only finite values")
    return array


def _total_trucks(value: Any) -> int:
    """Validate the configuration-level N used by the throughput margin."""

    if isinstance(value, bool):
        raise PairingError("total_trucks must be a positive integer")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PairingError("total_trucks must be a positive integer") from exc
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        raise PairingError("total_trucks must be a positive integer")
    return int(number)


def _normalise_stratum(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PairingError("stratum must be a non-empty string")
    normalised = value.strip().lower().replace("_", "-")
    aliases = {
        "medium": "medium",
        "mid": "medium",
        "moderate": "medium",
        "médio": "medium",
        "medio": "medium",
        "high": "high",
        "heavy": "high",
        "alta": "high",
        "alto": "high",
    }
    try:
        return aliases[normalised]
    except KeyError as exc:
        raise PairingError(
            f"unsupported stratum {value!r}; expected medium and high"
        ) from exc


def _first_column(frame: pd.DataFrame, names: Sequence[str], *, required: bool) -> str | None:
    for name in names:
        if name in frame.columns:
            return name
    if required:
        raise PairingError(
            "paired results are missing required field; expected one of: "
            + ", ".join(names)
        )
    return None


def _as_frame(results: Any) -> pd.DataFrame:
    """Materialise supported row containers without discovering other files."""

    if hasattr(results, "results") and not isinstance(results, (pd.DataFrame, Mapping)):
        results = results.results
    if isinstance(results, pd.DataFrame):
        frame = results.copy(deep=True)
    elif isinstance(results, Mapping):
        frame = pd.DataFrame([dict(results)])
    else:
        try:
            values = list(results)
        except TypeError as exc:
            raise TypeError("results must be a DataFrame or an iterable of mappings") from exc
        if not values:
            raise PairingError("paired results must not be empty")
        if any(not isinstance(value, Mapping) for value in values):
            raise TypeError("results must contain mappings")
        frame = pd.DataFrame([dict(value) for value in values])
    if frame.empty:
        raise PairingError("paired results must not be empty")
    return frame.reset_index(drop=True)


def _canonical_protocol_error(config: ExperimentConfig) -> str | None:
    """Return a diagnostic when ``config`` is not the frozen H1 protocol."""
    try:
        validate_confirmatory_config(config)
    except ValueError as exc:
        return str(exc)
    return None


def _require_canonical_confirmatory_config(config: ExperimentConfig) -> ExperimentConfig:
    """Cross the confirmatory-config boundary without fabricating a decision."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    try:
        return validate_confirmatory_config(config)
    except ValueError as exc:
        raise PairingError(str(exc)) from exc


def _derived_stratum(scenario: ScenarioConfig) -> str:
    """Derive the protocol stratum from the scenario's frozen capacity levels."""

    rho = scenario.truck_count / min(
        36 * scenario.hopper_count,
        72 * scenario.scale_count,
    )
    if not math.isfinite(rho):
        raise PairingError(
            "canonical scenario produced a non-finite nominal load index: "
            f"scenario_id={scenario.scenario_id}"
        )
    if rho < 0.70:
        return "low"
    if rho < 0.85:
        return "medium"
    return "high"


def canonical_scenario_metadata(
    config: ExperimentConfig,
) -> Mapping[str, Mapping[str, Any]]:
    """Return the immutable, protocol-derived metadata for all 72 scenarios.

    The mapping is built from :func:`factorial_scenarios`, never from row
    declarations.  It is public so the execution boundary can persist the
    same derived ``regime``/``total_trucks``/``stratum`` values that the
    confirmatory statistic consumes.
    """

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    mismatch = _canonical_protocol_error(config)
    if mismatch is not None:
        raise PairingError(mismatch)
    scenarios = factorial_scenarios(config)
    if len(scenarios) != 72 or len({scenario.scenario_id for scenario in scenarios}) != 72:
        raise PairingError(
            "canonical confirmatory scenario mapping must contain 72 unique scenario IDs"
        )
    metadata: dict[str, Mapping[str, Any]] = {}
    for scenario in scenarios:
        metadata[scenario.scenario_id] = MappingProxyType(
            {
                "scenario_id": scenario.scenario_id,
                "truck_count": scenario.truck_count,
                "hopper_count": scenario.hopper_count,
                "scale_count": scenario.scale_count,
                "regime": scenario.regime,
                "stratum": _derived_stratum(scenario),
            }
        )
    return MappingProxyType(metadata)


def _hashes(frame: pd.DataFrame, config: ExperimentConfig) -> str:
    expected = config_hash(config)
    hash_columns = [
        name for name in ("config_hash", "protocol_hash") if name in frame.columns
    ]
    if not hash_columns:
        raise PairingError(
            "paired results are missing required field; expected one of: config_hash, protocol_hash"
        )
    observed_values: list[str] = []
    for column in hash_columns:
        values = frame[column]
        if values.isna().any() or any(
            not isinstance(value, str) or not value for value in values
        ):
            raise PairingError("paired results contain missing config hash")
        unique = tuple(dict.fromkeys(str(value) for value in values))
        if len(unique) != 1:
            raise PairingError(f"mixed config hash values: {unique!r}")
        observed_values.append(unique[0])
    if any(value != expected for value in observed_values):
        raise PairingError(
            f"config hash does not match supplied configuration: expected={expected} observed={tuple(observed_values)!r}"
        )
    if len(set(observed_values)) != 1:
        raise PairingError(f"mixed config hash values: {tuple(observed_values)!r}")
    return observed_values[0]


def _pair_identifier(row: Mapping[str, Any], columns: set[str]) -> tuple[Any, ...]:
    if "pair_id" in columns:
        value = row.get("pair_id")
        if value is None or (isinstance(value, float) and math.isnan(value)):
            raise PairingError("paired results contain a missing pair_id")
        return ("pair", str(value))
    if "replicate_id" in columns:
        value = row.get("replicate_id")
        if value is None or (isinstance(value, float) and math.isnan(value)):
            raise PairingError("paired results contain a missing replicate_id")
        return ("replicate", str(value))
    if "scenario_id" not in columns or "seed" not in columns:
        raise PairingError(
            "paired results need scenario_id and seed (or an explicit pair_id)"
        )
    scenario_id = row.get("scenario_id")
    seed = row.get("seed")
    if scenario_id is None or seed is None:
        raise PairingError("paired results contain a missing scenario_id or seed")
    if isinstance(seed, bool):
        raise PairingError("seed must not be bool")
    try:
        numeric_seed = int(seed)
    except (TypeError, ValueError) as exc:
        raise PairingError("seed must be an integer") from exc
    if isinstance(seed, float) and not seed.is_integer():
        raise PairingError("seed must be an integer")
    return ("scenario", str(scenario_id), "seed", numeric_seed)


def _metric_column(frame: pd.DataFrame, *, kind: str, treatment: bool = False) -> str:
    if kind == "artifact":
        # The protocol has one primary outcome.  Do not accept an alternate
        # metric or a renamed p95 column at this boundary.
        names = (
            ("treatment_p95_wait_minutes",)
            if treatment
            else ("comparator_p95_wait_minutes",)
        )
    elif kind == "throughput":
        if treatment:
            names = ("treatment_throughput",)
        else:
            names = ("comparator_throughput",)
    else:
        raise ValueError(f"unsupported paired metric kind: {kind}")
    return _first_column(frame, names, required=True)  # type: ignore[return-value]


def _long_metric_column(frame: pd.DataFrame, kind: str) -> str:
    names = {
        "artifact": ("p95_wait_minutes",),
        "throughput": ("throughput",),
        "p95": ("p95_wait_minutes",),
    }.get(kind)
    if names is None:
        raise ValueError(f"unsupported long-form metric kind: {kind}")
    return _first_column(frame, names, required=True)  # type: ignore[return-value]


def _validate_source_p95(values: pd.Series) -> None:
    """Reject malformed primary outcomes before any grid aggregation."""

    if any(isinstance(value, bool) for value in values.tolist()):
        raise PairingError("p95_wait_minutes must be numeric, not bool")
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise PairingError(
            "p95_wait_minutes must contain only finite numeric values"
        )
    if (numeric < 0).any():
        raise PairingError("p95_wait_minutes must be non-negative")


def _positive_integer(name: str, value: Any) -> int:
    """Parse a persisted integer without accepting booleans or fractions."""

    if isinstance(value, bool):
        raise PairingError(f"{name} must be a positive integer")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PairingError(f"{name} must be a positive integer") from exc
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        raise PairingError(f"{name} must be a positive integer")
    return int(number)


def _validate_source_numeric(
    values: pd.Series,
    *,
    name: str,
    non_negative: bool,
) -> None:
    """Validate every source metric before selecting H1 policies."""

    if any(isinstance(value, bool) for value in values.tolist()):
        raise PairingError(f"{name} must be numeric, not bool")
    numeric = pd.to_numeric(values, errors="coerce")
    try:
        finite = np.isfinite(numeric.to_numpy(dtype=float))
    except (TypeError, ValueError) as exc:
        raise PairingError(f"{name} must contain only finite numeric values") from exc
    if numeric.isna().any() or not finite.all():
        raise PairingError(f"{name} must contain only finite numeric values")
    if non_negative and (numeric < 0).any():
        raise PairingError(f"{name} must be non-negative")


def _extract_pair_frame(
    frame: pd.DataFrame,
    config: ExperimentConfig,
) -> tuple[pd.DataFrame, str]:
    """Validate and materialise the complete frozen confirmatory grid.

    Unlike the validation/pilot matrix producer, this boundary never treats a
    declared stratum, truck count or pair identifier as authoritative.  The
    canonical scenario ID is resolved against the 72 factorial scenarios,
    metadata are derived from that scenario, and every scenario/seed/policy
    cell (18,000 rows) must be present exactly once.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    mismatch = _canonical_protocol_error(config)
    if mismatch is not None:
        raise PairingError(mismatch)

    checksum = _hashes(frame, config)
    columns = set(frame.columns)
    required = {"scenario_id", "seed", "policy", "p95_wait_minutes", "throughput"}
    missing = sorted(required - columns)
    if missing:
        raise PairingError(
            "canonical confirmatory results are missing required fields: "
            + ", ".join(missing)
        )
    if "pair_id" in columns or "replicate_id" in columns:
        raise PairingError(
            "canonical confirmatory grid requires scenario_id and seed; "
            "pair_id/replicate_id are not accepted"
        )

    metadata = canonical_scenario_metadata(config)
    expected_scenario_ids = tuple(metadata)
    expected_scenario_set = set(expected_scenario_ids)
    expected_policies = tuple(config.policies)
    expected_row_count = len(expected_scenario_ids) * len(config.seeds) * len(expected_policies)
    _validate_source_p95(frame["p95_wait_minutes"])
    _validate_source_numeric(
        frame["throughput"], name="throughput", non_negative=True
    )

    if len(frame) != expected_row_count:
        raise PairingError(
            "incomplete paired grid: canonical confirmatory grid "
            f"expected 72 scenarios x 50 seeds x 5 policies = {expected_row_count} rows "
            f"observed={len(frame)}"
        )

    # Aliases are read only to cross-check persisted metadata.  The derived
    # values below always replace them in the canonical frame used by H1.
    metadata_columns: dict[str, tuple[str, ...]] = {
        "stratum": (
            "stratum",
            "congestion_stratum",
            "congestion",
            "congestion_level",
            "level",
        ),
        "total_trucks": ("total_trucks",),
        "hopper_count": ("hopper_count", "hoppers"),
        "scale_count": ("scale_count", "scales"),
        "regime": ("regime",),
    }
    observed_keys: set[tuple[str, int, str]] = set()
    normalised_rows: list[dict[str, Any]] = []

    for index, (_, row) in enumerate(frame.iterrows(), start=1):
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id not in expected_scenario_set:
            raise PairingError(
                "canonical confirmatory grid contains unknown scenario_id: "
                f"row={index} scenario_id={scenario_id!r}"
            )
        seed = _positive_integer("seed", row.get("seed"))
        if seed not in config.seeds:
            raise PairingError(
                "canonical confirmatory grid contains seed outside 101..150: "
                f"row={index} seed={seed}"
            )
        policy = row.get("policy")
        if not isinstance(policy, str) or policy not in expected_policies:
            raise PairingError(
                "canonical confirmatory grid contains unknown policy: "
                f"row={index} policy={policy!r}"
            )
        key = (scenario_id, seed, policy)
        if key in observed_keys:
            raise PairingError(
                "duplicate canonical confirmatory cell: "
                f"scenario_id={scenario_id} seed={seed} policy={policy}"
            )
        observed_keys.add(key)

        expected = metadata[scenario_id]
        for field_name, aliases in metadata_columns.items():
            for column in aliases:
                if column not in columns:
                    continue
                declared = row.get(column)
                if field_name == "stratum":
                    if not isinstance(declared, str) or declared != expected[field_name]:
                        raise PairingError(
                            "stratum disagrees with canonical confirmatory mapping: "
                            f"scenario_id={scenario_id} expected={expected[field_name]!r} "
                            f"observed={declared!r}"
                        )
                elif field_name == "regime":
                    if not isinstance(declared, str) or declared != expected[field_name]:
                        raise PairingError(
                            "regime disagrees with canonical scenario_id mapping: "
                            f"scenario_id={scenario_id} expected={expected[field_name]!r} "
                            f"observed={declared!r}"
                        )
                else:
                    parsed = _positive_integer(field_name, declared)
                    if parsed != expected[
                        "truck_count" if field_name == "total_trucks" else field_name
                    ]:
                        raise PairingError(
                            "metadata disagrees with canonical scenario_id mapping and "
                            "configured truck_counts: "
                            f"scenario_id={scenario_id} field={field_name} "
                            f"expected={expected['truck_count' if field_name == 'total_trucks' else field_name]!r} "
                            f"observed={parsed!r}"
                        )

        canonical = dict(row)
        canonical.update(
            {
                "scenario_id": scenario_id,
                "seed": seed,
                "policy": policy,
                "stratum": expected["stratum"],
                "total_trucks": expected["truck_count"],
                "hopper_count": expected["hopper_count"],
                "scale_count": expected["scale_count"],
                "regime": expected["regime"],
                "config_hash": checksum,
            }
        )
        normalised_rows.append(canonical)

    expected_keys = {
        (scenario_id, seed, policy)
        for scenario_id in expected_scenario_ids
        for seed in config.seeds
        for policy in expected_policies
    }
    if observed_keys != expected_keys:
        missing_keys = sorted(expected_keys - observed_keys, key=repr)
        extra_keys = sorted(observed_keys - expected_keys, key=repr)
        raise PairingError(
            "incomplete paired grid: canonical confirmatory grid "
            f"missing={missing_keys[:3]!r} extra={extra_keys[:3]!r}"
        )

    grouped: dict[tuple[str, tuple[Any, ...]], dict[str, Mapping[str, Any]]] = {}
    for row in normalised_rows:
        stratum = row["stratum"]
        if stratum not in STRATA:
            # Low load is a required control part of the 72-scenario grid but
            # does not enter the confirmatory H1 contrasts.
            continue
        pair_key = ("scenario", row["scenario_id"], "seed", row["seed"])
        cells = grouped.setdefault((stratum, pair_key), {})
        policy = row["policy"]
        if policy in cells:
            raise PairingError(
                "duplicate canonical paired cell: "
                f"stratum={stratum} pair={pair_key!r} policy={policy}"
            )
        cells[policy] = row

    paired_records: list[dict[str, Any]] = []
    for stratum in STRATA:
        expected_pairs = {
            (
                "scenario",
                scenario_id,
                "seed",
                seed,
            )
            for scenario_id, scenario_metadata in metadata.items()
            if scenario_metadata["stratum"] == stratum
            for seed in config.seeds
        }
        observed_pairs = {
            pair_key
            for candidate_stratum, pair_key in grouped
            if candidate_stratum == stratum
        }
        if observed_pairs != expected_pairs:
            missing_pairs = sorted(expected_pairs - observed_pairs, key=repr)
            extra_pairs = sorted(observed_pairs - expected_pairs, key=repr)
            raise PairingError(
                "incomplete paired grid: canonical confirmatory paired grid "
                f"stratum={stratum} missing={missing_pairs[:3]!r} extra={extra_pairs[:3]!r}"
            )
        for pair_key in sorted(expected_pairs, key=repr):
            cells = grouped[(stratum, pair_key)]
            if set(cells) != set(expected_policies):
                missing_policies = sorted(set(expected_policies) - set(cells))
                extra_policies = sorted(set(cells) - set(expected_policies))
                raise PairingError(
                    "incomplete paired grid: canonical paired policy grid "
                    f"stratum={stratum} pair={pair_key!r} "
                    f"missing={missing_policies!r} extra={extra_policies!r}"
                )
            treatment = cells[TREATMENT_POLICY]
            for comparator in PRIMARY_COMPARATORS:
                baseline = cells[comparator]
                paired_records.append(
                    {
                        "stratum": stratum,
                        "comparator": comparator,
                        "pair_key": pair_key,
                        "scenario_id": treatment["scenario_id"],
                        "seed": treatment["seed"],
                        "config_hash": checksum,
                        "artifact_comparator": baseline["p95_wait_minutes"],
                        "artifact_treatment": treatment["p95_wait_minutes"],
                        "throughput_comparator": baseline["throughput"],
                        "throughput_treatment": treatment["throughput"],
                        "p95_comparator": baseline["p95_wait_minutes"],
                        "p95_treatment": treatment["p95_wait_minutes"],
                        "total_trucks": treatment["total_trucks"],
                        "hopper_count": treatment["hopper_count"],
                        "scale_count": treatment["scale_count"],
                        "regime": treatment["regime"],
                    }
                )
    paired = pd.DataFrame.from_records(paired_records)
    if paired.empty:
        raise PairingError("incomplete paired grid: canonical grid has no medium/high observations")
    paired = paired.sort_values(
        by=["stratum", "comparator", "pair_key"], key=lambda col: col.map(repr)
    ).reset_index(drop=True)
    return paired, checksum


def _iqr(values: np.ndarray) -> float:
    return float(np.percentile(values, 75) - np.percentile(values, 25))


def _wilcoxon(values: np.ndarray) -> tuple[float, float]:
    nonzero = values[~np.isclose(values, 0.0, rtol=0.0, atol=0.0)]
    if nonzero.size == 0:
        return 0.0, 1.0
    result = wilcoxon(
        values,
        zero_method="wilcox",
        alternative="greater",
        method="auto",
    )
    statistic = float(result.statistic)
    pvalue = float(result.pvalue)
    if not math.isfinite(statistic) or not math.isfinite(pvalue):
        raise RuntimeError("Wilcoxon returned a non-finite result")
    return statistic, pvalue


def _rank_biserial(values: np.ndarray) -> float:
    nonzero = values[~np.isclose(values, 0.0, rtol=0.0, atol=0.0)]
    if nonzero.size == 0:
        return 0.0
    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    denominator = float(ranks.sum())
    return (positive - negative) / denominator if denominator else 0.0


def _hodges_lehmann(values: np.ndarray) -> float:
    """Return the paired Hodges--Lehmann estimator from Walsh averages."""

    count = int(values.size)
    walsh = np.fromiter(
        ((values[i] + values[j]) / 2.0 for i in range(count) for j in range(i, count)),
        dtype=float,
        count=count * (count + 1) // 2,
    )
    estimate = float(np.median(walsh))
    if not math.isfinite(estimate):
        raise RuntimeError("Hodges-Lehmann Walsh estimator is non-finite")
    return estimate


def _decimal_relative_improvements(
    comparator: Sequence[Any], treatment: Sequence[Any]
) -> tuple[Decimal, ...]:
    """Compute decision ratios from canonical decimal spellings of values."""

    values: list[Decimal] = []
    for comparator_value, treatment_value in zip(comparator, treatment, strict=True):
        try:
            comparator_decimal = Decimal(str(comparator_value))
            treatment_decimal = Decimal(str(treatment_value))
            relative = (comparator_decimal - treatment_decimal) / abs(comparator_decimal)
        except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
            raise PairingError(
                "p95_wait_minutes values cannot form a finite decimal improvement"
            ) from exc
        if not comparator_decimal.is_finite() or not treatment_decimal.is_finite():
            raise PairingError(
                "p95_wait_minutes values cannot form a finite decimal improvement"
            )
        if not relative.is_finite():
            raise PairingError(
                "p95_wait_minutes values cannot form a finite decimal improvement"
            )
        values.append(relative)
    if not values:
        raise PairingError("p95_wait_minutes improvement vector must not be empty")
    return tuple(values)


def _stable_seed(stratum: str, comparator: str) -> int:
    digest = hashlib.sha256(f"{BOOTSTRAP_SEED}|{stratum}|{comparator}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def _bootstrap(values: np.ndarray, *, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    sample_indices = rng.integers(0, values.size, size=(BOOTSTRAP_ITERATIONS, values.size))
    estimates = np.median(values[sample_indices], axis=1)
    low, high = np.percentile(estimates, [2.5, 97.5])
    if not (math.isfinite(float(low)) and math.isfinite(float(high))):
        raise RuntimeError("paired bootstrap returned a non-finite interval")
    return float(low), float(high)


@dataclass(frozen=True, slots=True)
class ComparisonStats:
    """Statistics and gates for one stratum/comparator pair."""

    stratum: str
    comparator: str
    n: int
    total_trucks: int
    total_trucks_min: int
    total_trucks_max: int
    artifact_median_comparator: float
    artifact_median_treatment: float
    artifact_iqr_comparator: float
    artifact_iqr_treatment: float
    paired_difference: float
    paired_difference_iqr: float
    relative_improvement: float
    relative_improvement_pct: float
    wilcoxon_statistic: float
    wilcoxon_pvalue: float
    hodges_lehmann: float
    bootstrap_seed: int
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    rank_biserial: float
    throughput_median_comparator: float
    throughput_median_treatment: float
    throughput_difference: float
    throughput_loss: float
    throughput_guard_limit: float
    throughput_guard_statistic: float
    throughput_guard_pvalue: float
    throughput_guard: bool
    effect_pass: bool
    significance_pass: bool
    decision: str

    @property
    def median(self) -> float:
        return self.artifact_median_treatment

    @property
    def iqr(self) -> float:
        return self.artifact_iqr_treatment

    @property
    def p_value(self) -> float:
        return self.wilcoxon_pvalue

    @property
    def bootstrap_ci(self) -> tuple[float, float]:
        return self.bootstrap_ci_low, self.bootstrap_ci_high

    @property
    def relative_improvement_percent(self) -> float:
        return self.relative_improvement_pct

    @property
    def p95_median_comparator(self) -> float:
        return self.artifact_median_comparator

    @property
    def p95_median_treatment(self) -> float:
        return self.artifact_median_treatment

    @property
    def p95_iqr_comparator(self) -> float:
        return self.artifact_iqr_comparator

    @property
    def p95_iqr_treatment(self) -> float:
        return self.artifact_iqr_treatment

    @property
    def p95_difference(self) -> float:
        return self.paired_difference

    @property
    def p95_median(self) -> float:
        return self.artifact_median_treatment

    @property
    def p95_iqr(self) -> float:
        return self.artifact_iqr_treatment

    @property
    def paired_p95_difference(self) -> float:
        return self.paired_difference

    @property
    def throughput_guard_p_value(self) -> float:
        return self.throughput_guard_pvalue

    def to_dict(self) -> dict[str, Any]:
        return {
            "stratum": self.stratum,
            "comparator": self.comparator,
            "n": self.n,
            "total_trucks": self.total_trucks,
            "total_trucks_min": self.total_trucks_min,
            "total_trucks_max": self.total_trucks_max,
            "artifact_median_comparator": self.artifact_median_comparator,
            "artifact_median_treatment": self.artifact_median_treatment,
            "artifact_iqr_comparator": self.artifact_iqr_comparator,
            "artifact_iqr_treatment": self.artifact_iqr_treatment,
            # Explicit protocol-facing names make it auditable that the
            # primary outcome is p95_wait_minutes.  The artifact_* names are
            # retained only as schema aliases for existing consumers.
            "p95_median_comparator": self.p95_median_comparator,
            "p95_median_treatment": self.p95_median_treatment,
            "p95_iqr_comparator": self.p95_iqr_comparator,
            "p95_iqr_treatment": self.p95_iqr_treatment,
            "paired_difference": self.paired_difference,
            "paired_difference_iqr": self.paired_difference_iqr,
            "p95_difference": self.p95_difference,
            "relative_improvement": self.relative_improvement,
            "relative_improvement_pct": self.relative_improvement_pct,
            "wilcoxon_statistic": self.wilcoxon_statistic,
            "wilcoxon_pvalue": self.wilcoxon_pvalue,
            "hodges_lehmann": self.hodges_lehmann,
            "bootstrap_seed": self.bootstrap_seed,
            "bootstrap_ci_low": self.bootstrap_ci_low,
            "bootstrap_ci_high": self.bootstrap_ci_high,
            "rank_biserial": self.rank_biserial,
            "throughput_median_comparator": self.throughput_median_comparator,
            "throughput_median_treatment": self.throughput_median_treatment,
            "throughput_difference": self.throughput_difference,
            "throughput_loss": self.throughput_loss,
            "throughput_guard_limit": self.throughput_guard_limit,
            "throughput_guard_statistic": self.throughput_guard_statistic,
            "throughput_guard_pvalue": self.throughput_guard_pvalue,
            "throughput_guard": self.throughput_guard,
            "effect_pass": self.effect_pass,
            "significance_pass": self.significance_pass,
            "decision": self.decision,
        }


@dataclass(frozen=True, slots=True)
class H1Report:
    """Structured confirmatory result for both congestion strata."""

    h1_overall: str
    stratum_decisions: Mapping[str, str]
    comparisons: Mapping[tuple[str, str], ComparisonStats]
    stratum_pvalues: Mapping[str, float]
    holm_adjusted_pvalues: Mapping[str, float]
    config_hash: str
    alpha: float = ALPHA
    target_relative_improvement: float = TARGET_RELATIVE_IMPROVEMENT
    paired_rows: tuple[Mapping[str, Any], ...] = field(default_factory=tuple, repr=False)
    protocol_config: ExperimentConfig | None = field(default=None, repr=False, compare=False)

    @property
    def overall(self) -> str:
        return self.h1_overall

    @property
    def decision(self) -> str:
        return self.h1_overall

    @property
    def by_stratum(self) -> dict[str, dict[str, ComparisonStats]]:
        return {
            stratum: {
                comparator: stats
                for (candidate_stratum, comparator), stats in self.comparisons.items()
                if candidate_stratum == stratum
            }
            for stratum in STRATA
        }

    @property
    def comparison_stats(self) -> Mapping[tuple[str, str], ComparisonStats]:
        return self.comparisons

    def to_dict(self) -> dict[str, Any]:
        return {
            "h1_overall": self.h1_overall,
            "stratum_decisions": dict(self.stratum_decisions),
            "comparisons": {
                f"{stratum}|{comparator}": stats.to_dict()
                for (stratum, comparator), stats in self.comparisons.items()
            },
            "stratum_pvalues": dict(self.stratum_pvalues),
            "holm_adjusted_pvalues": dict(self.holm_adjusted_pvalues),
            "config_hash": self.config_hash,
            "alpha": self.alpha,
            "target_relative_improvement": self.target_relative_improvement,
        }


def _holm_adjust(pvalues: Mapping[str, float]) -> dict[str, float]:
    if not pvalues:
        raise ValueError("at least one p-value is required for Holm adjustment")
    ordered = sorted(pvalues.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for index, (key, pvalue) in enumerate(ordered):
        candidate = min(1.0, float(pvalue) * (count - index))
        running = max(running, candidate)
        adjusted[key] = running
    return adjusted


def _comparison_stats(
    paired: pd.DataFrame,
    *,
    stratum: str,
    comparator: str,
    config: ExperimentConfig,
) -> ComparisonStats:
    subset = paired.loc[
        (paired["stratum"] == stratum) & (paired["comparator"] == comparator)
    ]
    if subset.empty:
        raise PairingError(
            f"incomplete paired grid: stratum={stratum} comparator={comparator}"
        )
    comparator_artifact = _finite_array(
        "p95_wait_minutes comparator", subset["artifact_comparator"].tolist()
    )
    treatment_artifact = _finite_array(
        "p95_wait_minutes treatment", subset["artifact_treatment"].tolist()
    )
    comparator_throughput = _finite_array(
        "throughput_comparator", subset["throughput_comparator"].tolist()
    )
    treatment_throughput = _finite_array(
        "throughput_treatment", subset["throughput_treatment"].tolist()
    )
    total_truck_values = np.asarray(
        [_total_trucks(value) for value in subset["total_trucks"].tolist()], dtype=int
    )
    difference = comparator_artifact - treatment_artifact
    if np.any(comparator_artifact == 0.0):
        raise PairingError(
            f"p95_wait_minutes comparator values contain zero; relative improvement is undefined: "
            f"stratum={stratum} comparator={comparator}"
        )
    relative_decimal = _decimal_relative_improvements(
        comparator_artifact.tolist(), treatment_artifact.tolist()
    )
    throughput_delta = treatment_throughput - comparator_throughput
    throughput_loss = comparator_throughput - treatment_throughput
    n = int(difference.size)
    guard_limits = np.maximum(
        float(config.minimum_throughput_margin),
        float(config.throughput_margin_rate) * total_truck_values,
    )
    guard_limit = float(np.median(guard_limits))
    loss_summary = float(np.median(throughput_loss))
    throughput_noninferiority = throughput_delta + guard_limits
    guard_statistic, guard_pvalue = _wilcoxon(throughput_noninferiority)
    guard = bool(guard_pvalue <= ALPHA)
    statistic, pvalue = _wilcoxon(difference)
    hl = _hodges_lehmann(difference)
    bootstrap_seed = _stable_seed(stratum, comparator)
    bootstrap_low, bootstrap_high = _bootstrap(difference, seed=bootstrap_seed)
    relative_summary_decimal = decimal_median(relative_decimal)
    relative_summary = float(relative_summary_decimal)
    effect_pass = bool(
        relative_summary_decimal >= Decimal(str(TARGET_RELATIVE_IMPROVEMENT))
    )
    significance_pass = bool(pvalue <= ALPHA)
    decision = "SUPPORTED" if effect_pass and guard and significance_pass else "NOT_SUPPORTED"
    return ComparisonStats(
        stratum=stratum,
        comparator=comparator,
        n=n,
        total_trucks=int(np.median(total_truck_values)),
        total_trucks_min=int(np.min(total_truck_values)),
        total_trucks_max=int(np.max(total_truck_values)),
        artifact_median_comparator=float(np.median(comparator_artifact)),
        artifact_median_treatment=float(np.median(treatment_artifact)),
        artifact_iqr_comparator=_iqr(comparator_artifact),
        artifact_iqr_treatment=_iqr(treatment_artifact),
        paired_difference=float(np.median(difference)),
        paired_difference_iqr=_iqr(difference),
        relative_improvement=relative_summary,
        relative_improvement_pct=relative_summary * 100.0,
        wilcoxon_statistic=statistic,
        wilcoxon_pvalue=pvalue,
        hodges_lehmann=hl,
        bootstrap_seed=bootstrap_seed,
        bootstrap_ci_low=bootstrap_low,
        bootstrap_ci_high=bootstrap_high,
        rank_biserial=_rank_biserial(difference),
        throughput_median_comparator=float(np.median(comparator_throughput)),
        throughput_median_treatment=float(np.median(treatment_throughput)),
        throughput_difference=float(np.median(throughput_delta)),
        throughput_loss=loss_summary,
        throughput_guard_limit=guard_limit,
        throughput_guard_statistic=guard_statistic,
        throughput_guard_pvalue=guard_pvalue,
        throughput_guard=guard,
        effect_pass=effect_pass,
        significance_pass=significance_pass,
        decision=decision,
    )


def _evaluate_h1_core(results: Any, config: ExperimentConfig) -> H1Report:
    """Evaluate H1 after a caller has crossed the persisted-bundle boundary."""

    _require_canonical_confirmatory_config(config)
    frame = _as_frame(results)
    paired, checksum = _extract_pair_frame(frame, config)
    comparisons: dict[tuple[str, str], ComparisonStats] = {}
    for stratum in STRATA:
        for comparator in PRIMARY_COMPARATORS:
            comparisons[(stratum, comparator)] = _comparison_stats(
                paired,
                stratum=stratum,
                comparator=comparator,
                config=config,
            )

    stratum_raw_pvalues: dict[str, float] = {}
    stratum_decisions: dict[str, str] = {}
    for stratum in STRATA:
        stratum_comparisons = [
            comparisons[(stratum, comparator)] for comparator in PRIMARY_COMPARATORS
        ]
        conjunction_pass = all(
            stats.effect_pass and stats.throughput_guard and stats.significance_pass
            for stats in stratum_comparisons
        )
        # A conjunction is no more significant than its least significant
        # constituent.  Holm sees these two values only, never six pairwise
        # tests.
        stratum_raw_pvalues[stratum] = max(
            max(stats.wilcoxon_pvalue, stats.throughput_guard_pvalue)
            for stats in stratum_comparisons
        )
        stratum_decisions[stratum] = "SUPPORTED" if conjunction_pass else "NOT_SUPPORTED"
    adjusted = _holm_adjust(stratum_raw_pvalues)
    for stratum in STRATA:
        if adjusted[stratum] > ALPHA:
            stratum_decisions[stratum] = "NOT_SUPPORTED"
    overall = (
        "SUPPORTED"
        if all(stratum_decisions[stratum] == "SUPPORTED" for stratum in STRATA)
        else "NOT_SUPPORTED"
    )
    # Preserve the canonical pair key as structured data.  Export validation
    # compares freshly extracted pairs with this retained frame, so turning a
    # tuple into a repr string would make an otherwise identical source look
    # different (and would hide a grid mismatch).
    paired_rows = tuple(dict(row) for row in paired.to_dict(orient="records"))
    return H1Report(
        h1_overall=overall,
        stratum_decisions=stratum_decisions,
        comparisons=comparisons,
        stratum_pvalues=stratum_raw_pvalues,
        holm_adjusted_pvalues=adjusted,
        config_hash=checksum,
        paired_rows=paired_rows,
        protocol_config=config,
    )


def _validated_confirmatory_bundle(
    bundle: Any,
    config: ExperimentConfig,
) -> Any:
    """Validate the persisted evidence package before running H1 statistics."""

    _require_canonical_confirmatory_config(config)

    # Keep this import local: experiment.py publishes RunBundle and imports
    # canonical_scenario_metadata from this module.
    from .audit import audit_run
    from .experiment import RunBundle, load_run_bundle

    if not isinstance(bundle, RunBundle):
        raise PairingError(
            "evaluate_h1 accepts only a real RunBundle persisted on disk; "
            "raw rows and duck-typed containers are INVALID_INPUT"
        )

    run_dir = bundle.run_dir
    if not isinstance(run_dir, Path):
        raise PairingError("RunBundle run_dir must be a pathlib.Path")
    try:
        resolved_run_dir = run_dir.resolve(strict=False)
    except OSError as exc:
        raise PairingError(
            f"RunBundle namespace could not be resolved: run_dir={run_dir}"
        ) from exc
    if not resolved_run_dir.is_dir():
        cause = FileNotFoundError(str(resolved_run_dir))
        raise PairingError(
            f"RunBundle namespace does not exist: run_dir={resolved_run_dir}"
        ) from cause

    expected_paths = {
        "manifest_path": resolved_run_dir / "manifest.json",
        "results_path": resolved_run_dir / "results.csv",
        "logs_dir": resolved_run_dir / "logs",
        "audit_path": resolved_run_dir / "audit.json",
    }
    for field_name, expected_path in expected_paths.items():
        actual_path = getattr(bundle, field_name, None)
        if not isinstance(actual_path, Path):
            raise PairingError(
                f"RunBundle {field_name} must be a pathlib.Path within its namespace"
            )
        try:
            resolved_actual = actual_path.resolve(strict=False)
        except OSError as exc:
            raise PairingError(
                f"RunBundle {field_name} could not be resolved: path={actual_path}"
            ) from exc
        if resolved_actual != expected_path.resolve(strict=False):
            raise PairingError(
                "RunBundle path escapes its namespace: "
                f"field={field_name} expected={expected_path} observed={actual_path}"
            )

    for field_name in ("manifest_path", "results_path", "audit_path"):
        path = expected_paths[field_name]
        if not path.is_file():
            cause = FileNotFoundError(str(path))
            raise PairingError(
                f"RunBundle persisted artifact is missing: field={field_name} path={path}"
            ) from cause
    logs_dir = expected_paths["logs_dir"]
    if not logs_dir.is_dir():
        cause = FileNotFoundError(str(logs_dir))
        raise PairingError(
            f"RunBundle decision-log directory is missing: path={logs_dir}"
        ) from cause

    audit_path = expected_paths["audit_path"]
    try:
        persisted_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise PairingError(
            f"persisted audit.json could not be read: path={audit_path}"
        ) from exc
    if not isinstance(persisted_audit, Mapping):
        raise PairingError("persisted audit.json must contain an object")
    claimed_directory = persisted_audit.get("run_directory")
    if not isinstance(claimed_directory, str) or not claimed_directory.strip():
        raise PairingError("persisted audit.json is missing run_directory")
    try:
        resolved_claimed = Path(claimed_directory).resolve(strict=False)
    except OSError as exc:
        raise PairingError(
            "persisted audit.json run_directory could not be resolved: "
            f"observed={claimed_directory!r}"
        ) from exc
    if resolved_claimed != resolved_run_dir:
        raise PairingError(
            "persisted audit.json run_directory escapes the RunBundle namespace: "
            f"expected={resolved_run_dir} observed={resolved_claimed}"
        )
    if persisted_audit.get("overall_pass") is not True:
        raise PairingError(
            "persisted audit.json does not declare automated overall_pass=true"
        )

    try:
        audit_report = audit_run(resolved_run_dir)
    except Exception as exc:
        raise PairingError(
            "confirmatory RunBundle audit failed: "
            f"run_dir={resolved_run_dir} cause={exc}"
        ) from exc
    if getattr(audit_report, "overall_pass", None) is not True:
        diagnostics = getattr(audit_report, "diagnostics", ())
        cause = RuntimeError(f"audit overall_pass={getattr(audit_report, 'overall_pass', None)!r}")
        raise PairingError(
            "confirmatory RunBundle automated audit did not pass: "
            f"run_dir={resolved_run_dir} diagnostics={diagnostics!r}"
        ) from cause
    try:
        refreshed_audit = audit_report.to_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        raise PairingError(
            "confirmatory RunBundle audit returned no canonical persisted report"
        ) from exc
    if not isinstance(refreshed_audit, Mapping):
        raise PairingError("confirmatory RunBundle audit report must be a mapping")
    persisted_for_compare = dict(persisted_audit)
    persisted_for_compare["run_directory"] = str(resolved_run_dir)
    refreshed_for_compare = dict(refreshed_audit)
    refreshed_for_compare["run_directory"] = str(resolved_run_dir)
    if persisted_for_compare != refreshed_for_compare:
        raise PairingError(
            "persisted audit.json does not match the revalidated audit report: "
            f"path={audit_path}"
        )

    try:
        persisted_bundle = load_run_bundle(resolved_run_dir)
    except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PairingError(
            "revalidated RunBundle package could not be loaded: "
            f"run_dir={resolved_run_dir}"
        ) from exc
    manifest = persisted_bundle.manifest
    if manifest.get("phase") != "execute-confirmatory":
        raise PairingError(
            "confirmatory H1 requires phase='execute-confirmatory': "
            f"observed={manifest.get('phase')!r}"
        )
    expected_rows = manifest.get("expected_rows")
    if (
        isinstance(expected_rows, bool)
        or not isinstance(expected_rows, int)
        or expected_rows != 72 * 50 * 5
    ):
        raise PairingError(
            "confirmatory manifest expected_rows must be integer 18000: "
            f"observed={expected_rows!r}"
        )
    if getattr(audit_report, "expected_rows", None) != expected_rows:
        raise PairingError(
            "revalidated audit expected_rows disagrees with manifest: "
            f"audit={getattr(audit_report, 'expected_rows', None)!r} manifest={expected_rows!r}"
        )
    if dict(bundle.manifest) != dict(persisted_bundle.manifest):
        raise PairingError("RunBundle in-memory manifest differs from persisted manifest")
    if tuple(bundle.results) != tuple(persisted_bundle.results):
        raise PairingError("RunBundle in-memory results differ from persisted results")
    return persisted_bundle


def evaluate_h1(bundle: Any, config: ExperimentConfig) -> H1Report:
    """Evaluate H1 from one real, persisted, audited confirmatory RunBundle."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    persisted_bundle = _validated_confirmatory_bundle(bundle, config)
    return _evaluate_h1_core(persisted_bundle.results, config)


def report_summary_dataframe(report: H1Report) -> pd.DataFrame:
    """Materialise the report summary as a fresh DataFrame for export."""

    if not isinstance(report, H1Report):
        raise TypeError("report must be an H1Report")
    rows: list[dict[str, Any]] = []
    for (stratum, comparator), stats in report.comparisons.items():
        row = stats.to_dict()
        row.update(
            {
                "h1_overall": report.h1_overall,
                "stratum_decision": report.stratum_decisions[stratum],
                "stratum_pvalue": report.stratum_pvalues[stratum],
                "holm_adjusted_pvalue": report.holm_adjusted_pvalues[stratum],
                "config_hash": report.config_hash,
            }
        )
        rows.append(row)
    if not rows:
        raise ValueError("H1Report contains no comparison statistics")
    return pd.DataFrame(rows)


def paired_dataframe(report: H1Report) -> pd.DataFrame:
    """Materialise the canonical paired observations retained by the report."""

    if not isinstance(report, H1Report):
        raise TypeError("report must be an H1Report")
    if not report.paired_rows:
        raise ValueError("H1Report has no paired observations")
    frame = pd.DataFrame([dict(row) for row in report.paired_rows])
    if frame.empty:
        raise ValueError("H1Report has no paired observations")
    return frame


__all__ = [
    "ALPHA",
    "BOOTSTRAP_ITERATIONS",
    "BOOTSTRAP_SEED",
    "ComparisonStats",
    "H1Report",
    "INVALID_INPUT",
    "PRIMARY_COMPARATORS",
    "PairingError",
    "STRATA",
    "TREATMENT_POLICY",
    "canonical_scenario_metadata",
    "evaluate_h1",
    "paired_dataframe",
    "report_summary_dataframe",
]
