import tomllib
from pathlib import Path


def test_package_imports():
    import brotato_coach

    assert brotato_coach.__version__


def test_version_matches_pyproject():
    import brotato_coach

    pyproject = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    assert brotato_coach.__version__ == pyproject["project"]["version"]
