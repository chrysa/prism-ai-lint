"""Generated permissions follow the detected stack: no rule for a tool the project does not use."""

from __future__ import annotations


def _perms(m, tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    pol = m.load_policy(None, [tmp_path])
    return m.generated_permissions(m.detect_stack(tmp_path), pol)


PY = {"pyproject.toml": '[project]\nname = "x"\nversion = "0"\n'}
JS = {"package.json": '{"name": "x", "scripts": {"test": "jest"}}'}
TF = {"main.tf": "terraform {\n}\n"}


def test_python_project_has_no_node_or_cluster_rules(linter_module, tmp_path):
    p = _perms(linter_module, tmp_path, PY)
    joined = "\n".join(p["deny"] + p["ask"])
    assert "node_modules" not in joined and ".next" not in joined and "*.min.js" not in joined
    assert "kubectl" not in joined and "helm" not in joined and "terraform" not in joined
    assert "npm publish" not in joined
    assert any("__pycache__" in r for r in p["deny"])
    assert any("git push" in r for r in p["ask"]) and any("rm -rf" in r for r in p["ask"])


def test_node_project_has_no_python_rules(linter_module, tmp_path):
    p = _perms(linter_module, tmp_path, JS)
    joined = "\n".join(p["deny"] + p["ask"])
    assert "node_modules" in joined and "npm publish" in joined
    assert "__pycache__" not in joined and ".venv" not in joined and "twine" not in joined


def test_terraform_project_keeps_terraform_asks(linter_module, tmp_path):
    p = _perms(linter_module, tmp_path, TF)
    joined = "\n".join(p["ask"])
    assert "terraform apply" in joined and "terraform destroy" in joined
    assert "npm publish" not in joined


def test_compose_up_and_down_ask_instead_of_allow(linter_module, tmp_path):
    p = _perms(linter_module, tmp_path, {"docker-compose.yml": "services: {}\n"})
    assert "Bash(docker compose up *)" in p["ask"] and "Bash(docker compose down *)" in p["ask"]
    assert not any("compose up" in r or "compose down" in r for r in p["allow"])
    assert any("compose logs" in r for r in p["allow"])
