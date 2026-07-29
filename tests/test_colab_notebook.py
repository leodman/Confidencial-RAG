import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(__file__).parents[1] / "colab" / "confidencial_rag_launcher.ipynb"


def test_launcher_installs_with_kernel_interpreter_and_verifies_import() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    first_code_cell = next(cell for cell in notebook["cells"] if cell["cell_type"] == "code")
    source = "".join(first_code_cell["source"])
    tree = ast.parse(source)

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "sys" in imported_modules
    assert "confidencial_rag" in imported_modules

    pip_commands = [
        node.args[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
        and node.args
        and isinstance(node.args[0], ast.List)
        and any(
            isinstance(element, ast.Constant) and element.value == "pip"
            for element in node.args[0].elts
        )
    ]
    assert len(pip_commands) == 1
    executable = pip_commands[0].elts[0]
    assert isinstance(executable, ast.Attribute)
    assert isinstance(executable.value, ast.Name)
    assert executable.value.id == "sys"
    assert executable.attr == "executable"
    assert not any(
        isinstance(element, ast.Constant) and element.value == "python"
        for command in pip_commands
        for element in command.elts
    )
    assert "confidencial_rag.__file__" in source


def test_launcher_notebook_has_no_saved_outputs() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
