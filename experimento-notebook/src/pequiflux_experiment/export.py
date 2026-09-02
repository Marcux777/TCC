"""Atomic tabular and figure exports for a materialised :class:`H1Report`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import csv
import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import validate_confirmatory_config
from .statistics import (
    H1Report,
    PairingError,
    TARGET_RELATIVE_IMPROVEMENT,
    _evaluate_h1_core,
    _extract_pair_frame,
    _validated_confirmatory_bundle,
    paired_dataframe,
    report_summary_dataframe,
)


@dataclass(frozen=True, slots=True)
class ExportedArtifacts:
    """Published paths produced by :func:`export_analysis`."""

    table_h1: Path
    summary_parquet: Path
    p95_figure: Path
    table_throughput: Path
    paired_improvement_figure: Path
    throughput_waiting_tradeoff_figure: Path
    p95_figure_png: Path | None = None

    @property
    def h1_csv(self) -> Path:
        return self.table_h1

    @property
    def summary_path(self) -> Path:
        return self.summary_parquet

    @property
    def p95_path(self) -> Path:
        return self.p95_figure

    def to_dict(self) -> dict[str, str]:
        values = {
            "table_h1": self.table_h1,
            "summary_parquet": self.summary_parquet,
            "p95_figure": self.p95_figure,
            "table_throughput": self.table_throughput,
            "paired_improvement_figure": self.paired_improvement_figure,
            "throughput_waiting_tradeoff_figure": self.throughput_waiting_tradeoff_figure,
        }
        if self.p95_figure_png is not None:
            values["p95_figure_png"] = self.p95_figure_png
        return {key: str(value) for key, value in values.items()}


def _destination(root: str | Path) -> Path:
    if not isinstance(root, (str, Path)):
        raise TypeError("output_root must be a string or Path")
    destination = Path(root)
    if destination.exists() and not destination.is_dir():
        raise NotADirectoryError(f"output_root is not a directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _temporary(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")


_AUDIT_TABLE_FIELDS = (
    "run_id",
    "expected_rows",
    "observed_rows",
    "a1_pass",
    "a2_structural_pass",
    "a2_human_audit_pending",
    "replay_pass",
    "overall_pass",
)
_AUDIT_BOOLEAN_FIELDS = (
    "a1_pass",
    "a2_structural_pass",
    "a2_human_audit_pending",
    "replay_pass",
    "overall_pass",
)


def export_audit_table(
    audit_json_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Publish one CSV row from a persisted ``audit.json``.

    The JSON file is the sole source of audit values.  The destination is
    created atomically and an existing path is always a collision: this API
    never overwrites a previously published audit table.
    """

    source = Path(audit_json_path)
    if not source.is_file():
        raise FileNotFoundError(f"persisted audit JSON does not exist: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"persisted audit JSON is invalid: {source}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("persisted audit JSON must contain an object")

    required = {
        "run_directory",
        "expected_rows",
        "observed_rows",
        *_AUDIT_BOOLEAN_FIELDS,
    }
    missing = sorted(field for field in required if field not in payload)
    if missing:
        raise ValueError(
            "persisted audit JSON is missing required fields: " + ", ".join(missing)
        )

    run_directory = payload["run_directory"]
    if not isinstance(run_directory, str) or not run_directory.strip():
        raise ValueError("persisted audit run_directory must be a non-empty string")
    claimed_run_dir = Path(run_directory).resolve()
    source_run_dir = source.parent.resolve()
    if claimed_run_dir != source_run_dir:
        raise ValueError(
            "persisted audit run_directory mismatch: "
            f"source={source_run_dir} claimed={claimed_run_dir}"
        )
    run_id = claimed_run_dir.name
    if not run_id:
        raise ValueError("persisted audit run_directory must identify a run namespace")
    expected_rows = payload["expected_rows"]
    observed_rows = payload["observed_rows"]
    if (
        isinstance(expected_rows, bool)
        or not isinstance(expected_rows, int)
        or expected_rows <= 0
    ):
        raise ValueError("persisted audit expected_rows must be a positive integer")
    if (
        isinstance(observed_rows, bool)
        or not isinstance(observed_rows, int)
        or observed_rows < 0
    ):
        raise ValueError("persisted audit observed_rows must be a non-negative integer")
    for field in _AUDIT_BOOLEAN_FIELDS:
        if not isinstance(payload[field], bool):
            raise ValueError(f"persisted audit {field} must be boolean")
    expected_overall = (
        payload["a1_pass"]
        and payload["a2_structural_pass"]
        and payload["replay_pass"]
    )
    if payload["overall_pass"] is not expected_overall:
        raise ValueError(
            "persisted audit overall_pass is inconsistent with automated gates"
        )
    if payload["overall_pass"] and observed_rows != expected_rows:
        raise ValueError(
            "persisted audit overall_pass cannot be true when row counts differ"
        )

    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"audit table already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary(destination)
    row = {
        "run_id": run_id,
        "expected_rows": expected_rows,
        "observed_rows": observed_rows,
        **{field: payload[field] for field in _AUDIT_BOOLEAN_FIELDS},
    }
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=_AUDIT_TABLE_FIELDS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
        # The temporary file lives beside the destination, so rename is an
        # atomic publication on the same filesystem.  Windows also rejects a
        # pre-existing destination rather than replacing it.
        temporary.rename(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _publish_csv(frame: pd.DataFrame, destination: Path) -> None:
    temporary = _temporary(destination)
    try:
        frame.to_csv(temporary, index=False, lineterminator="\n")
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        temporary.replace(destination)
    except Exception:
        # Keep the original exception and operation context; do not publish a
        # partial file or substitute another serialization format.
        temporary.unlink(missing_ok=True)
        raise


def _publish_parquet(frame: pd.DataFrame, destination: Path) -> None:
    temporary = _temporary(destination)
    try:
        try:
            frame.to_parquet(temporary, engine="pyarrow", index=False)
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "summary Parquet export requires the declared pyarrow dependency"
            ) from exc
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _publish_figure(figure: Any, destination: Path, *, format: str) -> None:
    temporary = _temporary(destination)
    try:
        figure.savefig(temporary, format=format, bbox_inches="tight")
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _p95_frame(paired: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame suitable for the p95-by-policy figure."""

    required = {
        "stratum",
        "comparator",
        "p95_comparator",
        "p95_treatment",
    }
    if not required.issubset(paired.columns):
        raise ValueError("paired report is missing canonical p95 columns")
    comparator_rows = paired[
        ["stratum", "comparator", "p95_comparator"]
    ].rename(columns={"p95_comparator": "p95"})
    comparator_rows = comparator_rows.assign(policy=comparator_rows["comparator"])
    treatment_rows = paired[
        ["stratum", "comparator", "p95_treatment"]
    ].rename(columns={"p95_treatment": "p95"})
    treatment_rows = treatment_rows.assign(policy="lexicographic")
    result = pd.concat([comparator_rows, treatment_rows], ignore_index=True)
    result["p95"] = pd.to_numeric(result["p95"], errors="coerce")
    if result["p95"].isna().any() or not np.isfinite(result["p95"].to_numpy(dtype=float)).all():
        raise PairingError("p95_wait_minutes must contain only finite numeric values")
    return result


def _figure_p95(paired: pd.DataFrame) -> Any:
    plot_data = _p95_frame(paired)
    grouped = (
        plot_data.groupby(["stratum", "policy"], as_index=False, sort=True)["p95"]
        .median()
    )
    figure, axis = plt.subplots(figsize=(8, 4.8))
    for stratum in ("medium", "high"):
        subset = grouped.loc[grouped["stratum"] == stratum]
        if not subset.empty:
            axis.plot(subset["policy"], subset["p95"], marker="o", label=stratum)
    axis.set_xlabel("policy")
    axis.set_ylabel("p95 waiting metric")
    axis.set_title("p95 by policy and stratum")
    axis.tick_params(axis="x", rotation=35)
    axis.legend()
    figure.tight_layout()
    return figure


def _figure_improvement(summary: pd.DataFrame) -> Any:
    grouped = summary[["stratum", "comparator", "relative_improvement"]].copy()
    figure, axis = plt.subplots(figsize=(8, 4.8))
    for stratum in ("medium", "high"):
        subset = grouped.loc[grouped["stratum"] == stratum]
        if not subset.empty:
            labels = subset["comparator"].astype(str)
            axis.plot(labels, subset["relative_improvement"], marker="o", label=stratum)
    axis.axhline(
        TARGET_RELATIVE_IMPROVEMENT,
        color="black",
        linestyle="--",
        linewidth=1,
    )
    axis.set_xlabel("primary comparator")
    axis.set_ylabel("relative p95 waiting improvement")
    axis.set_title("Paired p95 waiting improvement")
    axis.tick_params(axis="x", rotation=35)
    axis.legend()
    figure.tight_layout()
    return figure


def _figure_tradeoff(summary: pd.DataFrame) -> Any:
    figure, axis = plt.subplots(figsize=(8, 4.8))
    for stratum in ("medium", "high"):
        subset = summary.loc[summary["stratum"] == stratum]
        if not subset.empty:
            axis.scatter(
                subset["throughput_loss"],
                subset["paired_difference"],
                label=stratum,
            )
    axis.axvline(0.0, color="black", linewidth=1)
    axis.set_xlabel("throughput loss")
    axis.set_ylabel("paired p95 waiting difference")
    axis.set_title("Throughput / p95 waiting trade-off")
    axis.legend()
    figure.tight_layout()
    return figure


def _rows_frame(rows: Any) -> pd.DataFrame:
    """Materialise the caller's source rows at the validation boundary."""

    if hasattr(rows, "results") and not isinstance(rows, (pd.DataFrame, Mapping)):
        rows = rows.results
    if isinstance(rows, pd.DataFrame):
        source = rows.copy(deep=True)
    elif isinstance(rows, Mapping):
        source = pd.DataFrame([dict(rows)])
    else:
        try:
            values = list(rows)
        except TypeError as exc:
            raise TypeError("rows must be an iterable of mappings or a DataFrame") from exc
        if any(not isinstance(value, Mapping) for value in values):
            raise TypeError("rows must contain mappings")
        source = pd.DataFrame([dict(value) for value in values])
    if source.empty:
        raise ValueError("rows must not be empty")
    return source.reset_index(drop=True)


def _validated_report(rows: Any, report: H1Report) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recompute and compare the report before any destination mutation."""

    config = report.protocol_config
    if config is None:
        raise PairingError("report is missing its protocol configuration")
    source = _rows_frame(rows)
    try:
        _, checksum = _extract_pair_frame(source, config)
    except Exception:
        # Preserve PairingError (including its causal diagnostic) and reject
        # malformed or incomplete sources before creating output directories.
        raise
    if checksum != report.config_hash:
        raise PairingError(
            "rows config_hash does not match report config_hash: "
            f"rows={checksum} report={report.config_hash}"
        )
    try:
        fresh_report = _evaluate_h1_core(source, config)
        expected_paired = paired_dataframe(report)
        actual_paired = paired_dataframe(fresh_report)
        pd.testing.assert_frame_equal(
            actual_paired.reset_index(drop=True),
            expected_paired.reset_index(drop=True),
            check_dtype=False,
            check_exact=True,
        )
        expected_summary = report_summary_dataframe(report)
        actual_summary = report_summary_dataframe(fresh_report)
        pd.testing.assert_frame_equal(
            actual_summary.reset_index(drop=True),
            expected_summary.reset_index(drop=True),
            check_dtype=False,
            check_exact=True,
        )
    except PairingError:
        raise
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        raise PairingError("rows do not match the supplied H1Report") from exc
    return actual_paired, actual_summary, fresh_report


def _validate_staging(
    staging: Path,
    *,
    summary: pd.DataFrame,
    throughput_columns: list[str],
    expected_files: tuple[Path, ...],
) -> None:
    """Read every staged output and check its shape before promotion."""

    for path in expected_files:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"staged artifact is missing or empty: {path}")
        if path.suffix.lower() == ".pdf" and path.read_bytes()[:4] != b"%PDF":
            raise RuntimeError(f"staged PDF has an invalid signature: {path}")
        if path.suffix.lower() == ".png" and path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"staged PNG has an invalid signature: {path}")

    table_h1 = staging / "tables" / "table_h1.csv"
    summary_parquet = staging / "processed" / "summary.parquet"
    table_throughput = staging / "tables" / "table_throughput.csv"
    try:
        h1_frame = pd.read_csv(table_h1)
        parquet_frame = pd.read_parquet(summary_parquet, engine="pyarrow")
        throughput_frame = pd.read_csv(table_throughput)
    except Exception as exc:
        raise RuntimeError("staged tabular artifacts could not be read back") from exc

    if h1_frame.empty or parquet_frame.empty or throughput_frame.empty:
        raise RuntimeError("staged tabular artifact is empty")
    if len(h1_frame) != len(summary) or len(parquet_frame) != len(summary):
        raise RuntimeError("staged summary cardinality does not match validated report")
    if list(h1_frame.columns) != list(summary.columns):
        raise RuntimeError("staged H1 CSV columns do not match validated summary")
    if list(parquet_frame.columns) != list(summary.columns):
        raise RuntimeError("staged Parquet columns do not match validated summary")
    if list(throughput_frame.columns) != throughput_columns:
        raise RuntimeError("staged throughput CSV columns do not match contract")
    if len(throughput_frame) != len(summary):
        raise RuntimeError("staged throughput CSV cardinality does not match summary")
    expected_throughput = summary.loc[:, throughput_columns].reset_index(drop=True)
    try:
        # CSV serialisation rounds floating-point values, so use a bounded
        # tolerance there; Parquet is expected to preserve the DataFrame
        # values exactly (apart from dtype representation).
        pd.testing.assert_frame_equal(
            h1_frame.reset_index(drop=True),
            summary.reset_index(drop=True),
            check_dtype=False,
            check_exact=False,
            rtol=1e-6,
            atol=1e-6,
        )
        pd.testing.assert_frame_equal(
            parquet_frame.reset_index(drop=True),
            summary.reset_index(drop=True),
            check_dtype=False,
            check_exact=True,
        )
        pd.testing.assert_frame_equal(
            throughput_frame.reset_index(drop=True),
            expected_throughput,
            check_dtype=False,
            check_exact=False,
            rtol=1e-6,
            atol=1e-6,
        )
    except AssertionError as exc:
        raise RuntimeError("staged tabular values do not match validated DataFrames") from exc


def _remove_path(path: Path) -> None:
    """Remove one explicitly resolved path without traversing symlinks."""

    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _ensure_targets_absent(destination: Path) -> None:
    """Reject collisions before creating a transaction staging directory."""

    for name in ("tables", "processed", "figures"):
        target = destination / name
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"controlled output target already exists: {target}")


def _rollback_promotion(
    *,
    destination: Path,
    promoted: list[str],
    promoted_identities: dict[str, tuple[int, int]],
    cause: BaseException,
) -> None:
    """Remove only directories proven to be ours after a failed promotion."""

    conflicts: list[str] = []
    for name in reversed(promoted):
        target = destination / name
        if not (target.exists() or target.is_symlink()):
            continue
        expected_identity = promoted_identities.get(name)
        if expected_identity is None:
            conflicts.append(
                f"{name}: identity unavailable; preserving target={target}"
            )
            continue
        try:
            observed = target.stat()
            observed_identity = (int(observed.st_dev), int(observed.st_ino))
        except Exception as stat_exc:
            conflicts.append(f"{name}: identity read failed: {stat_exc!r}")
            continue
        if observed_identity != expected_identity:
            conflicts.append(
                f"{name}: target identity conflict expected={expected_identity!r} "
                f"observed={observed_identity!r}; preserving target={target}"
            )
            continue
        try:
            _remove_path(target)
        except Exception as remove_exc:
            conflicts.append(
                f"{name}: removal failed identity={observed_identity!r}: "
                f"{remove_exc!r}"
            )

    if conflicts:
        error = RuntimeError(
            "staged export rollback failed: " + "; ".join(conflicts)
        )
        error.add_note(f"original promotion failure: {cause!r}")
        raise error from cause


def _promote_staging(staging: Path, destination: Path) -> None:
    """Promote the complete staged directory set with rollback on failure."""

    directory_names = ("tables", "processed", "figures")
    promoted: list[str] = []
    promoted_identities: dict[str, tuple[int, int]] = {}
    try:
        for name in directory_names:
            target = destination / name
            if target.exists() or target.is_symlink():
                raise FileExistsError(
                    f"controlled output target already exists: {target}"
                )
        for name in directory_names:
            source = staging / name
            target = destination / name
            if not source.is_dir():
                raise RuntimeError(f"staged directory is missing: {source}")
            if target.exists() or target.is_symlink():
                raise FileExistsError(
                    f"controlled output target appeared during promotion: {target}"
                )
            source.rename(target)
            promoted.append(name)
            identity = target.stat()
            promoted_identities[name] = (int(identity.st_dev), int(identity.st_ino))
        # Emptying the staging root is part of the transaction, before the
        # promotion can be considered successful.  If this fails, rollback
        # still has all old targets available.
        staging.rmdir()
    except Exception as promotion_exc:
        _rollback_promotion(
            destination=destination,
            promoted=promoted,
            promoted_identities=promoted_identities,
            cause=promotion_exc,
        )
        raise


def _export_analysis_core(
    rows: Any,
    report: H1Report,
    output_root: str | Path,
) -> ExportedArtifacts:
    """Publish H1 tables and figures from validated materialisations.

    This private core is also used by deterministic unit tests with synthetic
    rows.  The public boundary below accepts only a persisted, audited
    confirmatory ``RunBundle``.
    """

    if not isinstance(report, H1Report):
        raise TypeError("report must be an H1Report")
    paired, summary, _ = _validated_report(rows, report)
    destination = _destination(output_root)
    _ensure_targets_absent(destination)
    throughput_columns = [
        "stratum",
        "comparator",
        "n",
        "total_trucks",
        "total_trucks_min",
        "total_trucks_max",
        "throughput_median_comparator",
        "throughput_median_treatment",
        "throughput_difference",
        "throughput_loss",
        "throughput_guard_limit",
        "throughput_guard_statistic",
        "throughput_guard_pvalue",
        "throughput_guard",
        "decision",
    ]
    staging: Path | None = None
    failure: BaseException | None = None
    try:
        candidate = destination / f".export-staging-{uuid.uuid4().hex}"
        if candidate.exists() or candidate.is_symlink():
            raise FileExistsError(f"staging path already exists: {candidate}")
        staging = candidate
        staging.mkdir(parents=True)
        tables = staging / "tables"
        processed = staging / "processed"
        figures = staging / "figures"
        for directory in (tables, processed, figures):
            directory.mkdir()

        table_h1 = tables / "table_h1.csv"
        summary_parquet = processed / "summary.parquet"
        table_throughput = tables / "table_throughput.csv"
        p95_figure = figures / "p95_by_policy.pdf"
        paired_improvement_figure = figures / "paired_improvement.pdf"
        throughput_waiting_tradeoff_figure = figures / "throughput_waiting_tradeoff.pdf"
        p95_figure_png = figures / "p95_by_policy.png"
        expected_files = (
            table_h1,
            summary_parquet,
            table_throughput,
            p95_figure,
            p95_figure_png,
            paired_improvement_figure,
            throughput_waiting_tradeoff_figure,
        )
        _publish_csv(summary, table_h1)
        _publish_parquet(summary, summary_parquet)
        _publish_csv(summary.loc[:, throughput_columns], table_throughput)

        p95 = _figure_p95(paired)
        try:
            _publish_figure(p95, p95_figure, format="pdf")
            _publish_figure(p95, p95_figure_png, format="png")
        finally:
            plt.close(p95)
        improvement = _figure_improvement(summary)
        try:
            _publish_figure(improvement, paired_improvement_figure, format="pdf")
        finally:
            plt.close(improvement)
        tradeoff = _figure_tradeoff(summary)
        try:
            _publish_figure(tradeoff, throughput_waiting_tradeoff_figure, format="pdf")
        finally:
            plt.close(tradeoff)

        _validate_staging(
            staging,
            summary=summary,
            throughput_columns=throughput_columns,
            expected_files=expected_files,
        )
        _promote_staging(staging, destination)
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if staging is not None and (staging.exists() or staging.is_symlink()):
            try:
                _remove_path(staging)
            except Exception as cleanup_exc:
                error = RuntimeError(
                    f"staging cleanup failed for {staging}: {cleanup_exc}"
                )
                error.add_note(f"cleanup cause: {cleanup_exc!r}")
                evidence = destination / f".export-cleanup-failed-{uuid.uuid4().hex}"
                try:
                    staging.rename(evidence)
                except Exception as evidence_exc:
                    error.add_note(
                        f"staging evidence preservation failed for {staging}: "
                        f"{evidence_exc!r}"
                    )
                else:
                    error.add_note(f"staging evidence preserved at {evidence}")
                if failure is None:
                    raise error from cleanup_exc
                error.add_note(f"original export failure: {failure!r}")
                raise error from failure

    published_tables = destination / "tables"
    published_processed = destination / "processed"
    published_figures = destination / "figures"

    return ExportedArtifacts(
        table_h1=published_tables / "table_h1.csv",
        summary_parquet=published_processed / "summary.parquet",
        p95_figure=published_figures / "p95_by_policy.pdf",
        table_throughput=published_tables / "table_throughput.csv",
        paired_improvement_figure=published_figures / "paired_improvement.pdf",
        throughput_waiting_tradeoff_figure=published_figures / "throughput_waiting_tradeoff.pdf",
        p95_figure_png=published_figures / "p95_by_policy.png",
    )


def export_analysis(
    bundle: Any,
    report: H1Report,
    output_root: str | Path,
) -> ExportedArtifacts:
    """Publish H1 artifacts from one real, re-audited confirmatory bundle."""

    if not isinstance(report, H1Report):
        raise TypeError("report must be an H1Report")
    config = report.protocol_config
    if config is None:
        raise PairingError("report is missing its protocol configuration")
    try:
        validate_confirmatory_config(config)
    except (TypeError, ValueError) as exc:
        raise PairingError("report protocol configuration is not canonical") from exc
    persisted_bundle = _validated_confirmatory_bundle(bundle, config)
    return _export_analysis_core(persisted_bundle, report, output_root)


__all__ = ["ExportedArtifacts", "export_analysis", "export_audit_table"]
