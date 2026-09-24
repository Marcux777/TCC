"""Structural checks only: the notebook itself always requests the full campaign."""

import json
from pathlib import Path
import tomllib

import nbformat

ROOT = Path(__file__).parents[1]
NOTEBOOK = ROOT / "TCC_experimentos.ipynb"


def test_notebook_is_complete_scientific_workflow_without_embedded_tests():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    code = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "code")
    for cell in notebook.cells:
        if cell.cell_type == "code":
            compile(cell.source, f"{NOTEBOOK}:{cell.id}", "exec")
    for forbidden in ("pytest", "validation_fixtures", "tiny_scenario", "run_validation_matrix",
                      "smoke_test", "SANITY", 'RUN_PROFILE = "validation"'):
        assert forbidden not in code
    ids = [cell.id for cell in notebook.cells]
    stages = ["capacity", "prepare-scientific-inputs", "pilot", "principal",
              "h1", "sensitivity", "exploratory", "closure"]
    assert [ids.index(stage) for stage in stages] == sorted(ids.index(stage) for stage in stages)
    assert 'DATASET_ACTION = "generate"' in code
    assert "run_sensitivity" in code
    assert "analyse_pilot" in code
    assert "exploratory_summary" in code
    assert '"research_complete": False' in code
    assert '"human_evaluation": "NOT_EVALUATED"' in code
    assert "evaluate_h1(PRINCIPAL, CONFIG)" in code
    assert "face_receipt" not in code


def test_notebook_environment_contract_is_locked():
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert set(project["tool"]["uv"]["constraint-dependencies"]) == {
        line for line in lock.splitlines() if "==" in line}
    assert (ROOT / "uv.lock").is_file()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "uv sync --locked" in readme
    assert "uv run --locked python tools/execute_notebook.py" in readme
    assert "rtk " not in readme
