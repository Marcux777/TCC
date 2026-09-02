"""Contract checks for the central experiment notebook.

The structural check intentionally uses only the standard library so it remains
available when the optional notebook execution stack is not installed.  The
execution check is a real top-to-bottom boundary when ``nbformat``, ``nbclient``
and ``nbconvert`` are present; otherwise it fails explicitly as a blocked gate
instead of silently converting the absence into a skipped or passing test.
"""

from __future__ import annotations

from importlib.util import find_spec
import json
from pathlib import Path
import re
import tomllib
from unittest.mock import patch

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "TCC_experimentos.ipynb"

REQUIRED_SECTIONS = (
    "Identificação, manifesto e perfil de execução",
    "Carregamento e validação da configuração congelada",
    "Inventário do ambiente",
    "Domínio e arquitetura",
    "Testes automatizados",
    "Cenários de sanidade",
    "Demonstração emulador -> modelo digital -> recomendação -> comando",
    "Replay e auditoria",
    "Campanha conforme o perfil",
    "Artefatos persistidos",
    "Análise estatística e decisão estruturada de H1",
    "Diagnósticos de consistência do modelo digital",
    "Tabelas e figuras finais",
    "Resumo de artefatos e limites das conclusões",
)


def _read_notebook_with_stdlib() -> dict[str, object]:
    """Load the notebook without requiring the optional notebook stack."""

    with NOTEBOOK_PATH.open("r", encoding="utf-8") as handle:
        notebook = json.load(handle)
    if not isinstance(notebook, dict):
        raise AssertionError("notebook root must be a JSON object")
    return notebook


def _cell_source(notebook: dict[str, object]) -> list[str]:
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise AssertionError("notebook cells must be a list")
    sources: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise AssertionError("notebook cells must be objects")
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if not isinstance(source, str):
            raise AssertionError("notebook cell source must be text")
        sources.append(source)
    return sources


def test_notebook_has_ordered_sections_and_validation_default() -> None:
    notebook = _read_notebook_with_stdlib()
    assert notebook.get("nbformat") == 4
    assert isinstance(notebook.get("nbformat_minor"), int)

    cells = notebook.get("cells")
    assert isinstance(cells, list)
    ids = [cell.get("id") if isinstance(cell, dict) else None for cell in cells]
    assert ids == [f"cell-{index:02d}" for index in range(len(cells))]
    assert len(set(ids)) == len(ids)
    assert all(isinstance(cell_id, str) and re.fullmatch(r"[A-Za-z0-9-_]+", cell_id) for cell_id in ids)

    sources = _cell_source(notebook)
    headings = "\n".join(source for source in sources if source.lstrip().startswith("#"))
    positions = [headings.find(f"## {section}") for section in REQUIRED_SECTIONS]
    assert all(position >= 0 for position in positions), (
        "missing notebook sections: "
        + ", ".join(section for section, position in zip(REQUIRED_SECTIONS, positions) if position < 0)
    )
    assert positions == sorted(positions), "notebook sections must remain in specification order"

    code = "\n".join(
        source
        for cell, source in zip(notebook.get("cells", []), sources)
        if isinstance(cell, dict) and cell.get("cell_type") == "code"
    )
    demonstration_code = next(
        source
        for cell, source in zip(notebook.get("cells", []), sources)
        if isinstance(cell, dict) and cell.get("id") == "cell-14"
    )
    campaign_markdown = next(
        source
        for source in sources
        if "## Campanha conforme o perfil" in source
    )
    assert 'RUN_PROFILE = "validation"' in code
    assert 'ALLOWED_PROFILES = ("validation", "pilot", "load-confirmatory", "execute-confirmatory")' in code
    assert "CONFIRMATORY_RUN_ID = None" in code
    assert "tests/test_a2_structural.py" in code
    assert "dispatch_api.recommend" not in demonstration_code
    assert '"DECISION_RECORDED", "OPERATOR_DECISION", "SERVICE_STARTED"' in demonstration_code
    assert "demo_snapshot_before_recommendation" in demonstration_code
    assert "SANITY_RESULT.physical_snapshot" in demonstration_code
    assert "SANITY_RESULT.digital_snapshot" in demonstration_code
    assert "load-confirmatory" in code
    assert "execute-confirmatory" in code
    assert "sys.executable" in code
    assert "[\"rtk\", \"py\", \"-3\"" not in code
    assert "csv.DictWriter" not in code
    assert "AUDIT_REPORT.to_dict" not in code
    assert "latest" not in code.lower()
    assert "sensitivity" not in campaign_markdown.lower()
    assert "confirmatório e sensitivity" not in campaign_markdown.lower()
    assert all(
        profile in campaign_markdown
        for profile in ("pilot", "load-confirmatory", "execute-confirmatory")
    )
    assert "guard" in campaign_markdown.lower()


def test_notebook_environment_contract_is_locked() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    lock = (PROJECT_ROOT / "requirements.lock").read_text(encoding="utf-8")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "rtk .\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock" in readme
    assert "rtk .\\.venv\\Scripts\\python.exe -m pip install numpy" not in readme
    assert "`ipykernel` fornece o kernel nativo local" in readme
    assert "ipykernel==7.3.0" in lock
    assert "-e ." in lock
    assert ".venv/" in gitignore
    assert "__pycache__/" in gitignore
    assert "*.egg-info/" in gitignore
    assert "build/" in gitignore
    assert "dist/" in gitignore
    assert "runs/*" in gitignore
    assert "results/raw/*" in gitignore
    assert "!runs/.gitkeep" in gitignore
    assert "!results/raw/.gitkeep" in gitignore
    assert "!results/processed/.gitkeep" in gitignore
    assert "!results/tables/.gitkeep" in gitignore
    assert "!results/figures/.gitkeep" in gitignore
    assert "TCC_experimentos_executado.ipynb" in gitignore
    assert "TCC_experimentos.ipynb" not in gitignore
    assert "requirements.lock" not in gitignore


def test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() -> None:
    """The load profile must re-audit, analyse, and export persisted evidence."""

    notebook = _read_notebook_with_stdlib()
    sources = _cell_source(notebook)
    code_cells = [
        source
        for cell, source in zip(notebook["cells"], sources)
        if isinstance(cell, dict) and cell.get("cell_type") == "code"
    ]
    code = "\n".join(code_cells)

    required_notebook_contract = {
        "load branch": 'elif RUN_PROFILE == "load-confirmatory":',
        "load re-audit": "audit_api.audit_run(LOADED_BUNDLE.run_dir)",
        "persisted H1 evaluation": "statistics_api.evaluate_h1(BUNDLE, CONFIG)",
        "dynamic H1 decision": "h1_decision = h1_report.h1_overall",
        "persisted H1 export": (
            "export_api.export_analysis(BUNDLE, h1_report, RESULTS_ROOT)"
        ),
        "validation boundary": 'h1_decision = "NOT_RUN_VALIDATION_PROFILE"',
    }
    missing_notebook_contract = [
        label for label, fragment in required_notebook_contract.items() if fragment not in code
    ]
    assert not missing_notebook_contract, (
        "notebook profile contract is incomplete: "
        + ", ".join(missing_notebook_contract)
    )

    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    assert isinstance(dependencies, list)
    required_packages = {
        "numpy",
        "pandas",
        "scipy",
        "pyarrow",
        "matplotlib",
        "pytest",
        "nbformat",
        "nbclient",
        "nbconvert",
        "ipykernel",
    }

    lock_versions: dict[str, tuple[int, ...]] = {}
    for line in (PROJECT_ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==(\d+(?:\.\d+)*)", line.strip())
        if match:
            name, version = match.groups()
            normalised_name = re.sub(r"[-_.]+", "-", name).lower()
            lock_versions[normalised_name] = tuple(int(part) for part in version.split("."))

    declared_packages: set[str] = set()
    for dependency in dependencies:
        assert isinstance(dependency, str)
        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)>=([0-9]+(?:\.[0-9]+)*),<([0-9]+(?:\.[0-9]+)*)",
            dependency,
        )
        assert match, f"dependency must have bounded version range: {dependency!r}"
        name, lower, upper = match.groups()
        normalised_name = re.sub(r"[-_.]+", "-", name).lower()
        declared_packages.add(normalised_name)
        assert normalised_name in lock_versions, f"missing locked package: {name}"
        lower_tuple = tuple(int(part) for part in lower.split("."))
        upper_tuple = tuple(int(part) for part in upper.split("."))
        locked = lock_versions[normalised_name]
        assert lower_tuple <= locked < upper_tuple, (
            f"lock version for {name} is outside declared range: "
            f"{locked!r} not in [{lower_tuple!r}, {upper_tuple!r})"
        )

    assert declared_packages == required_packages


def test_notebook_validation_profile_executes_cleanly(tmp_path: Path) -> None:
    missing = [
        name
        for name in ("nbformat", "nbclient", "nbconvert")
        if find_spec(name) is None
    ]
    if missing:
        pytest.fail(
            "BLOCKED execution gate: required notebook dependencies are absent: "
            + ", ".join(missing)
        )

    import nbformat
    from nbclient import NotebookClient

    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    with patch.dict(
        "os.environ",
        {
            "PEQUIFLUX_RUNS_ROOT": str(tmp_path / "runs"),
            "PEQUIFLUX_RESULTS_ROOT": str(tmp_path / "results"),
        },
    ):
        executed = NotebookClient(
            notebook,
            timeout=600,
            kernel_name="python3",
            resources={"metadata": {"path": str(PROJECT_ROOT)}},
        ).execute()

    errors = [
        output
        for cell in executed.cells
        if cell.cell_type == "code"
        for output in cell.get("outputs", [])
        if output.output_type == "error"
    ]
    assert errors == []
    assert (tmp_path / "results" / "tables" / "table_audit.csv").exists()
