"""Execute the sole research notebook, retaining outputs even on failure."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / "TCC_experimentos.ipynb"
    notebook = nbformat.read(path, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.execution_count = None
            cell.outputs = []

    def progress(cell, cell_index, **kwargs):
        print(f"cell {cell_index + 1}/{len(notebook.cells)}: {cell.id}", flush=True)

    client = NotebookClient(notebook, timeout=604800, kernel_name="python3",
        resources={"metadata": {"path": str(root)}}, on_cell_execute=progress)
    try:
        client.execute()
    finally:
        nbformat.write(notebook, path)


if __name__ == "__main__":
    main()
