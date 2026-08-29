"""Fail a release when its tag and project version disagree."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10, which the project still supports.
    tomllib = None  # type: ignore[assignment]


def project_version_from_text(contents: str) -> str:
    if tomllib is not None:
        return str(tomllib.loads(contents)["project"]["version"])
    project_section = re.search(
        r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", contents
    )
    if project_section is None:
        raise ValueError("pyproject.toml has no [project] section")
    version = re.search(
        r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$',
        project_section.group(1),
    )
    if version is None:
        raise ValueError("pyproject.toml has no literal project.version")
    return version.group(1)


def source_versions(root: Path) -> tuple[str, str]:
    """Read versions without importing the package or its dependencies."""

    project_version = project_version_from_text(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    package_tree = ast.parse(
        (root / "spade65" / "__init__.py").read_text(encoding="utf-8")
    )
    package_version = None
    for statement in package_tree.body:
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            package_version = statement.value.value
            break
    if package_version is None:
        raise ValueError("spade65.__version__ is missing or not a string literal")
    return project_version, package_version


def matching_source_version(root: Path) -> str:
    project_version, package_version = source_versions(root)
    if project_version != package_version:
        raise ValueError(
            f"source versions disagree: project={project_version}, "
            f"package={package_version}"
        )
    if not re.fullmatch(r"\d+\.\d+\.\d+", project_version):
        raise ValueError("source version must use MAJOR.MINOR.PATCH form")
    return project_version


def main(arguments: list[str] | None = None) -> int:
    values = sys.argv[1:] if arguments is None else arguments
    root = Path(__file__).resolve().parents[1]
    try:
        project_version, package_version = source_versions(root)
    except (KeyError, OSError, SyntaxError, TypeError, ValueError) as error:
        raise SystemExit(str(error)) from error

    if values == ["--print-version"]:
        try:
            print(matching_source_version(root))
        except ValueError as error:
            raise SystemExit(str(error)) from error
        return 0
    if len(values) != 1 or not re.fullmatch(r"v\d+\.\d+\.\d+", values[0]):
        raise SystemExit(
            "expected a release tag in vMAJOR.MINOR.PATCH form or --print-version"
        )
    tag_version = values[0][1:]
    if project_version != tag_version or package_version != tag_version:
        raise SystemExit(
            f"release versions disagree: tag={tag_version}, "
            f"project={project_version}, package={package_version}"
        )
    print(project_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
