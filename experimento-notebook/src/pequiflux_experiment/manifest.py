"""Run namespace creation and environment manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tomllib
from typing import Any, Mapping

from .config import ExperimentConfig, config_as_dict, config_hash


_DEPENDENCY_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")
_LOCK_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^=\s]+)$")


def _normalise_distribution_name(name: str) -> str:
    """Return the PEP 503 spelling used to compare project and lock names."""

    return re.sub(r"[-_.]+", "-", name).lower()


def _project_root() -> Path:
    """Resolve this source package's project root without relying on cwd."""

    return Path(__file__).resolve().parents[2]


def _declared_distribution_names() -> tuple[str, ...]:
    """Read direct project requirements and verify their lock pins exist."""

    project_root = _project_root()
    pyproject_path = project_root / "pyproject.toml"
    lock_path = project_root / "requirements.lock"
    try:
        with pyproject_path.open("rb") as handle:
            project_document = tomllib.load(handle)
        lock_lines = lock_path.read_text(encoding="utf-8").splitlines()
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(
            "dependency declaration read failed: "
            f"pyproject={pyproject_path} lock={lock_path}"
        ) from exc

    project = project_document.get("project")
    if not isinstance(project, Mapping):
        raise RuntimeError("dependency declaration is missing [project] in pyproject.toml")
    raw_dependencies = project.get("dependencies")
    if not isinstance(raw_dependencies, list) or not raw_dependencies:
        raise RuntimeError("pyproject.toml project.dependencies must be a non-empty list")

    names: list[str] = []
    for requirement in raw_dependencies:
        if not isinstance(requirement, str):
            raise RuntimeError("project dependency declarations must be strings")
        match = _DEPENDENCY_NAME_RE.match(requirement.strip())
        if match is None:
            raise RuntimeError(f"project dependency has no distribution name: {requirement!r}")
        name = match.group(1)
        if _normalise_distribution_name(name) not in {
            _normalise_distribution_name(pin.group(1))
            for line in lock_lines
            if (pin := _LOCK_PIN_RE.fullmatch(line.strip())) is not None
        }:
            raise RuntimeError(
                "dependency declaration has no lock pin: "
                f"distribution={name} lock={lock_path}"
            )
        if name not in names:
            names.append(name)

    project_name = project.get("name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise RuntimeError("pyproject.toml project.name must be a non-empty string")
    if _normalise_distribution_name(project_name) not in {
        _normalise_distribution_name(pin.group(1))
        for line in lock_lines
        if (pin := _LOCK_PIN_RE.fullmatch(line.strip())) is not None
    }:
        # Editable local projects are represented by ``-e .`` rather than a
        # ``name==version`` line.  The local distribution is still required
        # in the resolved manifest and is resolved through importlib.metadata.
        if not any(line.strip() == "-e ." for line in lock_lines):
            raise RuntimeError(
                "local project has no editable lock entry: "
                f"distribution={project_name} lock={lock_path}"
            )
    if project_name not in names:
        names.append(project_name)
    return tuple(names)


def _resolved_dependency_versions(
    supplied: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Resolve every declared distribution from the active environment.

    ``importlib.metadata`` is deliberately the sole source of versions here:
    lock pins describe the intended environment, while the run receipt must
    record what was actually imported.  A missing or malformed version is a
    hard run-boundary error.
    """

    names = _declared_distribution_names()
    normalised_names = {
        _normalise_distribution_name(name): name
        for name in names
    }
    if supplied is not None:
        if not isinstance(supplied, Mapping):
            raise TypeError("dependencies must be a mapping")
        for name, version in supplied.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("dependency names must be non-empty strings")
            if not isinstance(version, str) or not version.strip():
                raise ValueError("dependency versions must be non-empty strings")
            if _normalise_distribution_name(name) not in normalised_names:
                raise ValueError(f"dependency is not declared by this project: {name}")

    resolved: dict[str, str] = {}
    for name in names:
        try:
            version = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                "dependency version resolution failed: "
                f"distribution={name} operation=manifest"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                "dependency version resolution failed: "
                f"distribution={name} operation=manifest"
            ) from exc
        if not isinstance(version, str) or not version.strip():
            raise RuntimeError(
                "dependency version resolution returned an invalid value: "
                f"distribution={name} observed={version!r}"
            )
        resolved[name] = version

    if supplied is not None:
        for name, expected in supplied.items():
            canonical_name = normalised_names[_normalise_distribution_name(name)]
            observed = resolved[canonical_name]
            if observed != expected:
                raise ValueError(
                    "supplied dependency version disagrees with active environment: "
                    f"distribution={canonical_name} expected={expected!r} observed={observed!r}"
                )
    return resolved


def _safe_component(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value or ":" in value:
        raise ValueError(f"{name} must be a path-safe component")
    return value


def _as_utc(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("now_utc must be an ISO-8601 timestamp") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("now_utc must be datetime, ISO-8601 string, or None")
    if parsed.tzinfo is None:
        raise ValueError("now_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def create_run_directory(
    root: str | Path,
    phase: str,
    commit: str,
    checksum: str,
    now_utc: datetime | str | None = None,
) -> Path:
    """Create one collision-safe run namespace and return its path."""

    phase_component = _safe_component("phase", phase)
    commit_component = _safe_component("commit", commit)
    checksum_component = _safe_component("checksum", checksum)
    timestamp = _as_utc(now_utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = (
        f"{phase_component}__{timestamp}__{commit_component}__"
        f"{checksum_component[:12]}"
    )
    run_dir = Path(root) / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f"run directory already exists: {run_dir}") from exc
    return run_dir


def _memory_total_bytes() -> int | None:
    """Read total physical memory when the platform exposes it directly."""

    if hasattr(os, "sysconf"):
        names = getattr(os, "sysconf_names", {})
        page_size_name = names.get("SC_PAGE_SIZE")
        page_count_name = names.get("SC_PHYS_PAGES")
        if page_size_name is not None and page_count_name is not None:
            return int(os.sysconf(page_size_name)) * int(os.sysconf(page_count_name))
    return None


def _memory_inventory() -> dict[str, Any]:
    try:
        total_bytes = _memory_total_bytes()
    except Exception as exc:
        raise RuntimeError("memory inventory failed") from exc
    if total_bytes is None:
        return {
            "status": "unavailable",
            "reason": "physical memory detection is unsupported on this platform",
            "total_bytes": None,
        }
    if total_bytes <= 0:
        cause = ValueError(f"physical memory detector returned {total_bytes}")
        raise RuntimeError("memory inventory failed") from cause
    return {"status": "detected", "reason": None, "total_bytes": total_bytes}


def _detect_gpu() -> dict[str, Any]:
    """Return an explicit optional GPU inventory without requiring a GPU."""

    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {
            "status": "unavailable",
            "reason": "nvidia-smi is not available",
            "devices": [],
        }
    command = [
        executable,
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "unavailable",
            "reason": f"nvidia-smi detection failed: {exc}",
            "devices": [],
        }

    devices: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 2 or not fields[0] or not fields[1]:
            return {
                "status": "unavailable",
                "reason": "nvidia-smi returned an invalid inventory row",
                "devices": [],
            }
        try:
            memory_mib = int(fields[1])
        except ValueError as exc:
            return {
                "status": "unavailable",
                "reason": f"nvidia-smi returned invalid memory data: {exc}",
                "devices": [],
            }
        devices.append({"name": fields[0], "memory_total_mib": memory_mib})

    if not devices:
        return {
            "status": "unavailable",
            "reason": "nvidia-smi reported no GPU devices",
            "devices": [],
        }
    return {"status": "detected", "reason": None, "devices": devices}


def _normalise_artifacts(
    artifacts: Mapping[str, str | Path] | None,
) -> dict[str, str]:
    if artifacts is None:
        return {}
    if not isinstance(artifacts, Mapping):
        raise TypeError("artifacts must be a mapping")
    result: dict[str, str] = {}
    for name, path in artifacts.items():
        _safe_component("artifact name", name)
        if not isinstance(path, (str, Path)):
            raise TypeError("artifact paths must be strings or Path objects")
        result[name] = str(path)
    return result


def build_manifest(
    config: ExperimentConfig,
    phase: str,
    commit: str,
    checksum: str | None = None,
    *,
    run_dir: str | Path | None = None,
    command: str | None = None,
    profile: str | None = None,
    artifacts: Mapping[str, str | Path] | None = None,
    checkout_clean: bool | None = None,
    dependencies: Mapping[str, str] | None = None,
    now_utc: datetime | str | None = None,
) -> dict[str, Any]:
    """Build a JSON-compatible manifest for one validated run.

    The function only constructs data; callers decide when and where to persist
    ``manifest.json`` so persistence remains an explicit run-boundary action.
    """

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    phase_component = _safe_component("phase", phase)
    commit_component = _safe_component("commit", commit)
    expected_checksum = config_hash(config)
    if checksum is None:
        checksum = expected_checksum
    if not isinstance(checksum, str) or not checksum:
        raise ValueError("checksum must be a non-empty string")
    if checksum != expected_checksum:
        raise ValueError("checksum does not match configuration hash")
    if command is not None and not isinstance(command, str):
        raise TypeError("command must be a string or None")
    if profile is not None:
        _safe_component("profile", profile)
    if checkout_clean is not None and not isinstance(checkout_clean, bool):
        raise TypeError("checkout_clean must be bool or None")
    dependency_versions = _resolved_dependency_versions(dependencies)

    created_at = _as_utc(now_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    processor = platform.processor() or None
    memory = _memory_inventory()
    try:
        gpu = _detect_gpu()
    except Exception as exc:
        gpu = {
            "status": "unavailable",
            "reason": f"GPU detection failed: {exc}",
            "devices": [],
        }

    manifest: dict[str, Any] = {
        "project_name": config.project_name,
        "protocol_version": config.protocol_version,
        "phase": phase_component,
        "hypothesis": config.hypothesis,
        "created_at_utc": created_at,
        "git_commit": commit_component,
        "checkout_clean": checkout_clean,
        "git": {"commit": commit_component, "checkout_clean": checkout_clean},
        "python_version": platform.python_version(),
        "operating_system": platform.platform(),
        "dependencies": dependency_versions,
        "cpu": {"model": processor, "logical_count": os.cpu_count()},
        "memory": memory,
        "gpu": gpu,
        "seeds": list(config.seeds),
        "policies": list(config.policies),
        "configuration": config_as_dict(config),
        "config_hash": checksum,
        "configuration_hash": checksum,
        "command": command,
        "profile": profile,
        "artifacts": _normalise_artifacts(artifacts),
    }
    if run_dir is not None:
        if not isinstance(run_dir, (str, Path)):
            raise TypeError("run_dir must be a string, Path, or None")
        run_path = Path(run_dir)
        manifest["run_directory"] = str(run_path)
        manifest["run_id"] = run_path.name
    return manifest
