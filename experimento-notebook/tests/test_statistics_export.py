import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from pequiflux_experiment.config import (
    CANONICAL_CONFIRMATORY_FIELDS,
    ExperimentConfig,
    config_as_dict,
    config_hash,
    factorial_scenarios,
    load_config,
    validate_confirmatory_config,
)
import pequiflux_experiment.export as export_module
import pequiflux_experiment.statistics as statistics_module
from pequiflux_experiment.export import export_analysis
from pequiflux_experiment.statistics import (
    PairingError,
    _evaluate_h1_core,
    evaluate_h1 as public_evaluate_h1,
)


PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"

# Synthetic rows exercise the private mathematical core.  The public H1
# boundary below accepts only a persisted, audited RunBundle.
evaluate_h1 = _evaluate_h1_core
# Export transaction tests likewise use the private rendering core; the public
# export boundary is covered explicitly with a raw-input rejection below.
export_analysis = export_module._export_analysis_core


def synthetic_paired_rows(
    *,
    artifact_improvement: float,
    throughput_loss: float,
    pairs_per_stratum: int = 12,
    total_trucks: int = 180,
    p95_improvement: float | None = None,
    p95_differences: list[float] | None = None,
) -> list[dict[str, object]]:
    """Build a complete long-form grid for the frozen confirmatory protocol."""

    del pairs_per_stratum, total_trucks
    config = load_config(CONFIG_PATH)
    checksum = config_hash(config)
    rows: list[dict[str, object]] = []
    offsets = {"low": 0, "medium": 0, "high": 0}
    for scenario in factorial_scenarios(config):
        rho = scenario.truck_count / min(
            36 * scenario.hopper_count, 72 * scenario.scale_count
        )
        stratum = "low" if rho < 0.70 else "medium" if rho < 0.85 else "high"
        for seed in config.seeds:
            offset = offsets[stratum]
            offsets[stratum] += 1
            baseline_artifact = 100.0
            treatment_artifact = baseline_artifact * (1.0 - artifact_improvement)
            baseline_throughput = 100.0
            treatment_throughput = baseline_throughput - throughput_loss
            if p95_differences is not None:
                baseline_p95 = 500.0
                p95_difference = p95_differences[offset % len(p95_differences)]
                treatment_p95 = baseline_p95 - p95_difference
            else:
                p95_gain = artifact_improvement if p95_improvement is None else p95_improvement
                baseline_p95 = 100.0
                treatment_p95 = baseline_p95 * (1.0 - p95_gain)
            common = {
                "stratum": stratum,
                "scenario_id": scenario.scenario_id,
                "seed": seed,
                "config_hash": checksum,
                "total_trucks": scenario.truck_count,
                "hopper_count": scenario.hopper_count,
                "scale_count": scenario.scale_count,
                "regime": scenario.regime,
            }
            for policy in config.policies:
                treatment = policy == "lexicographic"
                rows.append(
                    {
                        **common,
                        "policy": policy,
                        "artifact_count": treatment_artifact if treatment else baseline_artifact,
                        "throughput": treatment_throughput if treatment else baseline_throughput,
                        "p95_wait_minutes": treatment_p95 if treatment else baseline_p95,
                    }
                )
    return rows


def canonical_confirmatory_rows() -> list[dict[str, object]]:
    """Materialise the complete frozen 72 x 50 x 5 confirmatory grid."""

    config = load_config(CONFIG_PATH)
    checksum = config_hash(config)
    rows: list[dict[str, object]] = []
    for scenario in factorial_scenarios(config):
        rho = scenario.truck_count / min(
            36 * scenario.hopper_count, 72 * scenario.scale_count
        )
        stratum = "low" if rho < 0.70 else "medium" if rho < 0.85 else "high"
        for seed in config.seeds:
            common = {
                "scenario_id": scenario.scenario_id,
                "seed": seed,
                "stratum": stratum,
                "total_trucks": scenario.truck_count,
                "hopper_count": scenario.hopper_count,
                "scale_count": scenario.scale_count,
                "regime": scenario.regime,
                "config_hash": checksum,
            }
            for policy in config.policies:
                rows.append(
                    {
                        **common,
                        "policy": policy,
                        "artifact_count": 100.0,
                        "throughput": 100.0,
                        "p95_wait_minutes": 100.0,
                    }
                )
    return rows


def test_h1_rejects_partial_grid_at_invalid_input_boundary():
    rows = canonical_confirmatory_rows()
    rows.pop()

    with pytest.raises(PairingError, match="INVALID_INPUT.*canonical.*72.*50"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


def test_h1_rejects_stratum_that_disagrees_with_canonical_mapping():
    rows = canonical_confirmatory_rows()
    for row in rows:
        if row["stratum"] == "medium":
            row["stratum"] = "high"
        elif row["stratum"] == "high":
            row["stratum"] = "medium"

    with pytest.raises(PairingError, match="INVALID_INPUT.*stratum.*canonical"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


def test_h1_core_accepts_complete_confirmatory_rows_from_bundle(tmp_path):
    from pequiflux_experiment.experiment import RunBundle

    config = load_config(CONFIG_PATH)
    bundle = RunBundle(
        run_dir=tmp_path / "execute-confirmatory__canonical",
        manifest_path=tmp_path / "execute-confirmatory__canonical" / "manifest.json",
        results_path=tmp_path / "execute-confirmatory__canonical" / "results.csv",
        logs_dir=tmp_path / "execute-confirmatory__canonical" / "logs",
        audit_path=tmp_path / "execute-confirmatory__canonical" / "audit.json",
        results=tuple(canonical_confirmatory_rows()),
        manifest={"phase": "execute-confirmatory", "expected_rows": 72 * 50 * 5},
    )

    report = _evaluate_h1_core(bundle.results, config)

    assert report.h1_overall == "NOT_SUPPORTED"
    assert set(report.comparisons) == {
        (stratum, comparator)
        for stratum in ("medium", "high")
        for comparator in statistics_module.PRIMARY_COMPARATORS
    }


def test_h1_derives_scenario_metadata_when_declarations_are_absent():
    rows = canonical_confirmatory_rows()
    for row in rows:
        for field in (
            "stratum",
            "regime",
            "total_trucks",
            "hopper_count",
            "scale_count",
        ):
            row.pop(field)

    report = evaluate_h1(rows, load_config(CONFIG_PATH))

    assert report.h1_overall == "NOT_SUPPORTED"
    assert set(report.stratum_decisions) == {"medium", "high"}


def test_public_h1_rejects_duck_typed_results_container():
    with pytest.raises(PairingError, match="real RunBundle"):
        public_evaluate_h1(
            SimpleNamespace(
                results=(),
                manifest={
                    "phase": "execute-confirmatory",
                    "expected_rows": 72 * 50 * 5,
                },
            ),
            load_config(CONFIG_PATH),
        )


def test_public_h1_rejects_unbacked_run_bundle_before_statistics(tmp_path):
    from pequiflux_experiment.experiment import RunBundle

    run_dir = tmp_path / "execute-confirmatory__unbacked"
    bundle = RunBundle(
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.json",
        results_path=run_dir / "results.csv",
        logs_dir=run_dir / "logs",
        audit_path=run_dir / "audit.json",
        results=(),
        manifest={"phase": "execute-confirmatory", "expected_rows": 72 * 50 * 5},
    )

    with pytest.raises(PairingError, match="audit|namespace|run directory"):
        public_evaluate_h1(bundle, load_config(CONFIG_PATH))


def test_public_h1_rejects_forged_persisted_audit(tmp_path):
    from pequiflux_experiment.experiment import RunBundle

    run_dir = tmp_path / "execute-confirmatory__forged-audit"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "results.csv").write_text("\n", encoding="utf-8")
    (run_dir / "audit.json").write_text(
        json.dumps(
            {
                "run_directory": str(run_dir),
                "overall_pass": True,
                "expected_rows": 72 * 50 * 5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    bundle = RunBundle(
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.json",
        results_path=run_dir / "results.csv",
        logs_dir=logs_dir,
        audit_path=run_dir / "audit.json",
        results=(),
        manifest={"phase": "execute-confirmatory", "expected_rows": 72 * 50 * 5},
    )

    with pytest.raises(PairingError, match="audit"):
        public_evaluate_h1(bundle, load_config(CONFIG_PATH))


def test_public_export_rejects_raw_results(tmp_path):
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    report = evaluate_h1(rows, load_config(CONFIG_PATH))

    with pytest.raises(PairingError, match="RunBundle"):
        export_module.export_analysis(rows, report, tmp_path)


@pytest.mark.parametrize("phase", ["confirmatory", "load-confirmatory"])
def test_matrix_rejects_non_execution_phase_before_materialising_cells(tmp_path, phase):
    from pequiflux_experiment.experiment import run_experiment_matrix

    with pytest.raises(ValueError, match="phase"):
        run_experiment_matrix(
            (),
            (),
            (),
            load_config(CONFIG_PATH),
            tmp_path,
            phase=phase,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("project_name", "PequiFlux altered"),
        ("protocol_version", "9.9.9"),
        ("hypothesis", "H2"),
        ("seeds", tuple(range(101, 150))),
        ("horizon_minutes", 721),
        ("ordinary_window", 7),
        ("priority_thresholds", (60, 30, 11)),
        ("throughput_margin_rate", 0.03),
        ("minimum_throughput_margin", 3),
        ("truck_counts", (60, 120, 181)),
        ("hopper_counts", (1, 2, 4)),
        ("scale_counts", (1, 3)),
        ("regimes", ("altered", "peak", "critical_failure", "priority_shift")),
        (
            "policies",
            (
                "fifo_strict",
                "fifo_flow_faithful",
                "priority_local",
                "fixed_score",
                "altered",
            ),
        ),
    ],
)
def test_confirmatory_validator_rejects_any_material_field_override(field, replacement):
    payload = config_as_dict(load_config(CONFIG_PATH))
    payload[field] = replacement
    if field == "policies":
        # ExperimentConfig protects the canonical panel at construction; the
        # validator must still remain authoritative for an in-memory mutation
        # arriving from a manifest or other untrusted boundary.
        config = load_config(CONFIG_PATH)
        object.__setattr__(config, field, replacement)
    else:
        config = ExperimentConfig(**payload)

    with pytest.raises(ValueError, match=field):
        validate_confirmatory_config(config)


def test_confirmatory_config_file_equals_immutable_canonical_representation():
    config = load_config(CONFIG_PATH)
    expected = {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in CANONICAL_CONFIRMATORY_FIELDS.items()
    }

    assert config_as_dict(config) == expected
    assert validate_confirmatory_config(config) is config


def test_h1_is_conjunctive_and_throughput_guard_can_block_support(tmp_path):
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)

    supported = evaluate_h1(rows, load_config(CONFIG_PATH))

    assert supported.h1_overall == "SUPPORTED"
    assert set(supported.stratum_decisions) == {"medium", "high"}
    assert {
        comparator for _, comparator in supported.comparisons
    } == set(statistics_module.PRIMARY_COMPARATORS)
    assert ("medium", "fifo_strict") not in supported.comparisons
    assert all(
        detail.decision == "SUPPORTED"
        for detail in supported.comparisons.values()
    )

    within_rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    within = evaluate_h1(within_rows, load_config(CONFIG_PATH))
    assert within.h1_overall == "SUPPORTED"
    assert all(detail.throughput_guard for detail in within.comparisons.values())
    assert within.comparisons[("medium", "fifo_flow_faithful")].throughput_guard_limit == pytest.approx(2.0)
    assert within.comparisons[("high", "fifo_flow_faithful")].throughput_guard_limit == pytest.approx(2.4)

    blocked_rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=3)
    blocked = evaluate_h1(blocked_rows, load_config(CONFIG_PATH))
    assert blocked.h1_overall == "NOT_SUPPORTED"
    assert any(not detail.throughput_guard for detail in blocked.comparisons.values())

    artifacts = export_analysis(blocked_rows, blocked, tmp_path)
    assert artifacts.table_h1.exists()
    assert artifacts.summary_parquet.exists()
    assert artifacts.p95_figure.exists()
    assert pd.read_parquet(artifacts.summary_parquet).shape[0] > 0


def test_incomplete_pairing_is_invalid_not_inconclusive():
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    rows.pop()

    with pytest.raises(PairingError, match="incomplete paired grid"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


def test_h1_uses_p95_as_primary_outcome_not_artifact_count():
    config = load_config(CONFIG_PATH)
    artifact_improves_p95_stable = synthetic_paired_rows(
        artifact_improvement=0.20,
        p95_improvement=0.0,
        throughput_loss=0,
    )
    assert evaluate_h1(artifact_improves_p95_stable, config).h1_overall == "NOT_SUPPORTED"

    artifact_stable_p95_improves = synthetic_paired_rows(
        artifact_improvement=0.0,
        p95_improvement=0.20,
        throughput_loss=0,
    )
    assert evaluate_h1(artifact_stable_p95_improves, config).h1_overall == "SUPPORTED"


def test_h1_canonical_threshold_is_fifteen_percent():
    report = evaluate_h1(
        synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0),
        load_config(CONFIG_PATH),
    )
    assert report.target_relative_improvement == pytest.approx(0.15)
    assert report.h1_overall == "SUPPORTED"


def test_fifteen_percent_effect_uses_exact_decimal_values():
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    for row in rows:
        row["p95_wait_minutes"] = 0.255 if row["policy"] == "lexicographic" else 0.3
    exact = evaluate_h1(rows, load_config(CONFIG_PATH))
    assert exact.h1_overall == "SUPPORTED"

    almost_rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    for row in almost_rows:
        row["p95_wait_minutes"] = (
            0.2550000000000001 if row["policy"] == "lexicographic" else 0.3
        )
    almost = evaluate_h1(almost_rows, load_config(CONFIG_PATH))
    assert almost.h1_overall == "NOT_SUPPORTED"


def test_holm_uses_iut_maximum_of_p95_and_throughput_pvalues(monkeypatch):
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    config = load_config(CONFIG_PATH)

    def controlled_stats(*args, **kwargs):
        return SimpleNamespace(
            effect_pass=True,
            throughput_guard=True,
            significance_pass=True,
            wilcoxon_pvalue=0.001,
            throughput_guard_pvalue=0.04,
            decision="SUPPORTED",
        )

    monkeypatch.setattr(statistics_module, "_comparison_stats", controlled_stats)
    report = evaluate_h1(rows, config)

    assert report.stratum_pvalues == {"medium": pytest.approx(0.04), "high": pytest.approx(0.04)}
    assert report.holm_adjusted_pvalues == {"medium": pytest.approx(0.08), "high": pytest.approx(0.08)}
    assert report.stratum_decisions == {"medium": "NOT_SUPPORTED", "high": "NOT_SUPPORTED"}
    assert report.h1_overall == "NOT_SUPPORTED"


@pytest.mark.parametrize("mutation", ["missing", "nan", "infinite"])
def test_missing_or_malformed_p95_is_rejected(mutation):
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    if mutation == "missing":
        for row in rows:
            row.pop("p95_wait_minutes")
    elif mutation == "nan":
        rows[0]["p95_wait_minutes"] = float("nan")
    else:
        rows[0]["p95_wait_minutes"] = float("inf")

    with pytest.raises(PairingError, match="p95_wait_minutes"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


def test_throughput_total_trucks_is_required_and_consistent_within_pair():
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    rows[0]["total_trucks"] = 60
    rows[1]["total_trucks"] = 180
    with pytest.raises(PairingError, match="total_trucks"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


def test_total_trucks_must_belong_to_configured_levels():
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    rows[0]["total_trucks"] = 999
    with pytest.raises(PairingError, match="truck_counts"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


@pytest.mark.parametrize("bad_p95", [float("nan"), float("inf"), True, -1.0, None])
def test_invalid_p95_on_extra_policy_is_rejected_before_pairing(bad_p95):
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    extra = dict(rows[0])
    extra["policy"] = "fixed_score"
    extra["p95_wait_minutes"] = bad_p95
    rows.append(extra)
    with pytest.raises(PairingError, match="p95_wait_minutes"):
        evaluate_h1(rows, load_config(CONFIG_PATH))


def test_throughput_guard_is_paired_noninferiority_not_only_median():
    rows = synthetic_paired_rows(
        artifact_improvement=0.20,
        throughput_loss=0,
        total_trucks=60,
    )
    # The median loss remains zero, but a minority of paired cells lose all
    # throughput.  Wilcoxon must inspect the paired guard, not only its median.
    for stratum in ("medium", "high"):
        changed = 0
        limit = 200 if stratum == "medium" else 1000
        for row in rows:
            if row["stratum"] == stratum and row["policy"] == "lexicographic" and changed < limit:
                row["throughput"] = 0.0
                changed += 1

    report = evaluate_h1(rows, load_config(CONFIG_PATH))
    assert report.h1_overall == "NOT_SUPPORTED"
    assert any(
        detail.throughput_guard_pvalue > 0.05
        for detail in report.comparisons.values()
    )


def test_hodges_lehmann_uses_walsh_averages():
    differences = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100, 101, 102]
    # Preserve a known 12-cell Walsh-average fixture inside the canonical
    # 600-pair medium stratum; the remaining cells sit at the expected HL.
    differences += [7.25] * (600 - len(differences))
    rows = synthetic_paired_rows(
        artifact_improvement=0.0,
        throughput_loss=0,
        p95_differences=differences,
        total_trucks=180,
    )
    report = evaluate_h1(rows, load_config(CONFIG_PATH))
    assert report.comparisons[("medium", "fifo_flow_faithful")].hodges_lehmann == pytest.approx(7.25)


def test_export_revalidates_rows_before_publishing(tmp_path):
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    report = evaluate_h1(rows, load_config(CONFIG_PATH))

    with pytest.raises(PairingError):
        export_analysis([{"foo": "bar"}], report, tmp_path)
    assert not (tmp_path / "tables" / "table_h1.csv").exists()

    next(
        row
        for row in rows
        if row["stratum"] == "medium" and row["policy"] == "fifo_flow_faithful"
    )["p95_wait_minutes"] = 999.0
    with pytest.raises(PairingError):
        export_analysis(rows, report, tmp_path)
    assert not (tmp_path / "tables" / "table_h1.csv").exists()


def test_export_is_all_or_nothing_when_a_late_artifact_fails(tmp_path, monkeypatch):
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    report = evaluate_h1(rows, load_config(CONFIG_PATH))

    def fail_figure(*args, **kwargs):
        raise RuntimeError("synthetic figure failure")

    monkeypatch.setattr(export_module, "_publish_figure", fail_figure)
    with pytest.raises(RuntimeError, match="synthetic figure failure"):
        export_analysis(rows, report, tmp_path)
    assert not (tmp_path / "tables" / "table_h1.csv").exists()
    assert not (tmp_path / "processed" / "summary.parquet").exists()
    assert not (tmp_path / "figures" / "p95_by_policy.pdf").exists()


def test_export_setup_failure_cleans_staging(tmp_path, monkeypatch):
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    report = evaluate_h1(rows, load_config(CONFIG_PATH))
    original_mkdir = Path.mkdir

    def fail_processed_setup(path, *args, **kwargs):
        if path.name == "processed" and path.parent.name.startswith(".export-staging-"):
            raise OSError("injected setup failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_processed_setup)
    with pytest.raises(OSError, match="injected setup failure"):
        export_analysis(rows, report, tmp_path)
    assert not tuple(tmp_path.glob(".export-staging-*"))


def test_export_reports_staging_cleanup_failure_without_swallowing(tmp_path, monkeypatch):
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    report = evaluate_h1(rows, load_config(CONFIG_PATH))
    original_mkdir = Path.mkdir
    original_remove = export_module._remove_path

    def fail_processed_setup(path, *args, **kwargs):
        if path.name == "processed" and path.parent.name.startswith(".export-staging-"):
            raise OSError("injected setup failure")
        return original_mkdir(path, *args, **kwargs)

    def fail_staging_cleanup(path):
        if path.name.startswith(".export-staging-"):
            raise OSError("injected cleanup failure")
        return original_remove(path)

    monkeypatch.setattr(Path, "mkdir", fail_processed_setup)
    monkeypatch.setattr(export_module, "_remove_path", fail_staging_cleanup)
    with pytest.raises(RuntimeError, match="staging cleanup failed.*injected cleanup failure") as exc_info:
        export_analysis(rows, report, tmp_path)
    assert isinstance(exc_info.value.__cause__, OSError)
    assert not tuple(tmp_path.glob(".export-staging-*"))
    assert tuple(tmp_path.glob(".export-cleanup-failed-*"))


def test_rollback_preserves_reappeared_target_and_chains_cause(tmp_path):
    target = tmp_path / "tables"
    target.mkdir()
    (target / "external.txt").write_text("external", encoding="utf-8")
    with pytest.raises(RuntimeError, match="staged export rollback failed") as exc_info:
        export_module._rollback_promotion(
            destination=tmp_path,
            promoted=["tables"],
            promoted_identities={"tables": (0, 0)},
            cause=OSError("injected promotion failure"),
        )
    assert (target / "external.txt").read_text(encoding="utf-8") == "external"
    assert "injected promotion failure" in " ".join(exc_info.value.__notes__)


def test_export_rejects_controlled_target_collision_before_staging(tmp_path):
    rows = synthetic_paired_rows(artifact_improvement=0.15, throughput_loss=0)
    report = evaluate_h1(rows, load_config(CONFIG_PATH))
    (tmp_path / "tables").mkdir()
    with pytest.raises(FileExistsError, match="controlled output target"):
        export_analysis(rows, report, tmp_path)
    assert not tuple(tmp_path.glob(".export-staging-*"))


def test_rollback_accumulates_conflicts_after_removing_own_targets(tmp_path):
    identities = {}
    for name in ("tables", "processed", "figures"):
        target = tmp_path / name
        target.mkdir()
        (target / "marker.txt").write_text(name, encoding="utf-8")
        stat = target.stat()
        identities[name] = (int(stat.st_dev), int(stat.st_ino))
    identities["figures"] = (0, 0)

    with pytest.raises(RuntimeError, match="figures") as exc_info:
        export_module._rollback_promotion(
            destination=tmp_path,
            promoted=["tables", "processed", "figures"],
            promoted_identities=identities,
            cause=OSError("injected promotion failure"),
        )

    assert not (tmp_path / "tables").exists()
    assert not (tmp_path / "processed").exists()
    assert (tmp_path / "figures" / "marker.txt").read_text(encoding="utf-8") == "figures"
    assert isinstance(exc_info.value.__cause__, OSError)
    assert "injected promotion failure" in " ".join(exc_info.value.__notes__)


def test_export_audit_table_uses_persisted_json_and_rejects_collision(tmp_path):
    """The audit table must come from the persisted audit boundary."""

    audit_json = tmp_path / "run" / "audit.json"
    audit_json.parent.mkdir()
    persisted = {
        "run_directory": str(audit_json.parent),
        "expected_rows": 10,
        "observed_rows": 10,
        "a1_pass": True,
        "a2_structural_pass": True,
        "a2_human_audit_pending": True,
        "replay_pass": True,
        "overall_pass": True,
    }
    audit_json.write_text(json.dumps(persisted) + "\n", encoding="utf-8")
    output = tmp_path / "results" / "tables" / "table_audit.csv"

    # Import inside the test so the missing public boundary is the causal RED,
    # without preventing the pre-existing export tests from being collected.
    from pequiflux_experiment.export import export_audit_table

    assert export_audit_table(audit_json, output) == output
    with output.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "run_id": "run",
            "expected_rows": "10",
            "observed_rows": "10",
            "a1_pass": "True",
            "a2_structural_pass": "True",
            "a2_human_audit_pending": "True",
            "replay_pass": "True",
            "overall_pass": "True",
        }
    ]

    # A second call must not overwrite the published table.
    with pytest.raises(FileExistsError, match="already exists"):
        export_audit_table(audit_json, output)


def test_export_audit_table_rejects_claimed_namespace_mismatch(tmp_path):
    actual = tmp_path / "actual-run"
    claimed = tmp_path / "claimed-run"
    actual.mkdir()
    audit_json = actual / "audit.json"
    audit_json.write_text(
        json.dumps(
            {
                "run_directory": str(claimed),
                "expected_rows": 1,
                "observed_rows": 1,
                "a1_pass": True,
                "a2_structural_pass": True,
                "a2_human_audit_pending": True,
                "replay_pass": True,
                "overall_pass": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from pequiflux_experiment.export import export_audit_table

    with pytest.raises(ValueError, match="source=.*claimed="):
        export_audit_table(audit_json, tmp_path / "table_audit.csv")
