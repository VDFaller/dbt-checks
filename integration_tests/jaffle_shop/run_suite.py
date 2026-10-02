"""Run the Jaffle Shop dbt-checks integration suite and assert exact outcomes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


PROJECT_DIR = Path(__file__).resolve().parent
REPO_DIR = PROJECT_DIR.parents[1]
DB_PATH = Path(os.environ.get("JAFFLE_SHOP_DB_PATH", PROJECT_DIR / "target" / "jaffle_shop.duckdb")).resolve()
PROFILES_DIR = Path(os.environ.get("JAFFLE_SHOP_PROFILES_DIR", PROJECT_DIR)).resolve()


@dataclass(frozen=True)
class CheckCase:
    check: str
    resource: str
    passes: bool


FOCUSED_CASES = [
    CheckCase("model_has_properties_file", "customers", True),
    CheckCase("model_has_properties_file", "mart_without_docs", False),
    CheckCase("model_has_description", "customers", True),
    CheckCase("model_has_description", "mart_without_docs", False),
    CheckCase("model_has_test", "customers", True),
    CheckCase("model_has_test", "mart_without_docs", False),
    CheckCase("column_has_description", "customers", True),
    CheckCase("column_has_description", "fct_missing_column_docs", False),
    CheckCase("column_has_description", "stg_customers", True),
    CheckCase("column_has_description", "stg_orders", True),
    CheckCase("column_has_description", "stg_sql_column_override", False),
    CheckCase("column_has_description", "stg_yaml_column_exemption", True),
    CheckCase("column_has_description", "fct_yaml_column_exemption", True),
    CheckCase("model_has_grain_test", "customers", True),
    CheckCase("model_has_grain_test", "fct_composite_grain", True),
    CheckCase("model_has_grain_test", "dim_missing_grain_not_null", False),
    CheckCase("model_has_grain_test", "orders", True),
    CheckCase("model_has_grain_test", "dim_sql_grain_exemption", True),
    CheckCase("model_has_grain_test", "stg_orders", True),
    CheckCase("model_name_matches_pattern", "fct_composite_grain", True),
    CheckCase("model_name_matches_pattern", "customers", True),
    CheckCase("model_name_matches_pattern", "orders", True),
    CheckCase("model_name_matches_pattern", "yaml_pattern_model", True),
    CheckCase("model_name_matches_pattern", "inline_sql_pattern_case", True),
    CheckCase("model_name_matches_pattern", "mart_without_docs", False),
    CheckCase("public_models_have_descriptions", "customers", True),
    CheckCase("public_models_have_descriptions", "mart_without_docs", False),
]

EXPECTED_ALL_FAILURES = {
    "model_has_properties_file": {"mart_without_docs"},
    "model_has_description": {"mart_without_docs"},
    "model_has_test": {"mart_without_docs"},
    "source_table_has_description": {"raw_orders"},
    "source_table_has_test": {"raw_orders"},
    "column_has_description": {"fct_missing_column_docs", "stg_sql_column_override"},
    "model_has_grain_test": {"dim_missing_grain_not_null"},
    "model_name_matches_pattern": {"mart_without_docs"},
    "public_models_have_descriptions": {"mart_without_docs"},
}


def command(args: Sequence[str], *, cwd: Path = PROJECT_DIR, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args), cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    return result


def dbt(*args: str, project: Path = PROJECT_DIR, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    effective_env = os.environ.copy()
    effective_env.setdefault("JAFFLE_SHOP_DB_PATH", str(DB_PATH))
    if env is not None:
        effective_env.update(env)
    return command(
        ["dbt", *args, "--project-dir", str(project), "--profiles-dir", str(PROFILES_DIR)],
        cwd=project,
        env=effective_env,
    )


def assert_case(case: CheckCase) -> None:
    selector = case.resource
    result = dbt("check", case.check, "--select", selector)
    if "NoNodesForSelectionCriteria" in result.stdout or "Skipped [" in result.stdout:
        raise AssertionError(f"Focused selector {selector!r} selected no check resources:\n{result.stdout}")
    if (result.returncode == 0) != case.passes:
        raise AssertionError(
            f"{case.check} --select {selector}: expected "
            f"{'pass' if case.passes else 'failure'}, got exit {result.returncode}\n{result.stdout}"
        )
    if not case.passes and case.resource not in result.stdout:
        raise AssertionError(f"Expected {case.resource} in focused result:\n{result.stdout}")


def assert_source_cases(check_name: str) -> None:
    """Source selection is not supported by dbt check 2.0.6; run each check alone."""
    result = dbt("check", check_name)
    if result.returncode != 1 or "raw_orders" not in result.stdout:
        raise AssertionError(f"{check_name} should report raw_orders:\n{result.stdout}")
    if "raw_customers" in result.stdout:
        raise AssertionError(f"{check_name} unexpectedly reported passing raw_customers:\n{result.stdout}")


def assert_full_suite() -> None:
    result = dbt("check")
    if result.returncode != 1:
        raise AssertionError(f"Plain dbt check should fail intentionally, got {result.returncode}:\n{result.stdout}")
    reported_counts = {
        name: int(count)
        for name, count in re.findall(
            r"check '([^']+)' failed with (\d+) violation\(s\)", result.stdout
        )
    }
    expected_counts = {
        check_name: len(resources)
        for check_name, resources in EXPECTED_ALL_FAILURES.items()
    }
    if reported_counts != expected_counts:
        raise AssertionError(
            f"Expected exactly these check violation counts: {expected_counts}; "
            f"got {reported_counts}:\n{result.stdout}"
        )
    for check_name, resources in EXPECTED_ALL_FAILURES.items():
        if check_name not in result.stdout:
            raise AssertionError(f"Full check output omitted {check_name}:\n{result.stdout}")
        for resource in resources:
            if resource not in result.stdout:
                raise AssertionError(f"Full check output omitted {check_name} resource {resource}:\n{result.stdout}")
    for resource in {"raw_orders", "dim_missing_grain_not_null", "mart_without_docs"}:
        if resource not in result.stdout:
            raise AssertionError(f"Full check output omitted expected failing resource {resource}:\n{result.stdout}")


def invalid_settings_cases() -> None:
    """Exercise invalid argument handling in tiny throwaway dbt projects."""
    invalid_cases = [
        ("wrong_type", '"checks.model_has_grain_test": "true"', "check config must be true, false, or an object"),
        ("unknown_option", '"checks.model_has_grain_test": {"unknown": true}', "unknown check option"),
        ("empty_argument", '"checks.model_has_grain_test": {"accepted_test_names": []}', "accepted_test_names must be a nonempty array"),
        ("wrong_argument_type", '"checks.model_has_grain_test": {"accepted_test_names": "unique"}', "accepted_test_names must be a nonempty array"),
    ]
    with tempfile.TemporaryDirectory(prefix="dbt-checks-invalid-") as temporary:
        root = Path(temporary)
        absent = root / "absent_setting"
        (absent / "models").mkdir(parents=True)
        (absent / "models" / "no_setting.sql").write_text("select 1 as id\n", encoding="utf-8")
        (absent / "dbt_project.yml").write_text(
            "name: absent_setting\nversion: '1.0'\nconfig-version: 2\n"
            "profile: jaffle_shop\nmodel-paths: ['models']\ncheck-paths: ['checks']\n"
            "info_schema:\n  version: 1\n", encoding="utf-8"
        )
        (absent / "packages.yml").write_text(
            f"packages:\n  - local: {REPO_DIR.as_posix()}\n", encoding="utf-8"
        )
        absent_env = os.environ.copy()
        absent_env["JAFFLE_SHOP_DB_PATH"] = str(root / "absent_setting.duckdb")
        deps = dbt("deps", project=absent, env=absent_env)
        if deps.returncode != 0:
            raise AssertionError(f"dbt deps failed for absent setting fixture:\n{deps.stdout}")
        absent_check = dbt("check", "model_has_grain_test", "--select", "no_setting", project=absent, env=absent_env)
        if absent_check.returncode != 0:
            raise AssertionError(f"Absent setting should leave the check unconfigured:\n{absent_check.stdout}")
        for case_name, setting, expected in invalid_cases:
            project = root / case_name
            (project / "models").mkdir(parents=True)
            (project / "models" / "invalid_case.sql").write_text(
                '{{ config(meta={' + setting + '}) }}\nselect 1 as id\n', encoding="utf-8"
            )
            (project / "dbt_project.yml").write_text(
                "name: invalid_settings\nversion: '1.0'\nconfig-version: 2\n"
                "profile: jaffle_shop\nmodel-paths: ['models']\ncheck-paths: ['checks']\n"
                "info_schema:\n  version: 1\n", encoding="utf-8"
            )
            (project / "packages.yml").write_text(
                f"packages:\n  - local: {REPO_DIR.as_posix()}\n", encoding="utf-8"
            )
            local_env = os.environ.copy()
            local_env["JAFFLE_SHOP_DB_PATH"] = str(root / f"{case_name}.duckdb")
            # Each project has no source dependencies. dbt can create its empty DuckDB file.
            deps = dbt("deps", project=project, env=local_env)
            if deps.returncode != 0:
                raise AssertionError(f"dbt deps failed for {case_name}:\n{deps.stdout}")
            check = dbt("check", "model_has_grain_test", "--select", "invalid_case", project=project, env=local_env)
            if check.returncode != 1 or expected not in check.stdout:
                raise AssertionError(f"{case_name}: expected {expected!r}, got {check.returncode}:\n{check.stdout}")

        empty_pattern = root / "empty_pattern"
        (empty_pattern / "models").mkdir(parents=True)
        (empty_pattern / "models" / "bad_pattern.sql").write_text(
            '{{ config(meta={"checks.model_name_matches_pattern": {"pattern": ""}}) }}\nselect 1 as id\n',
            encoding="utf-8",
        )
        (empty_pattern / "dbt_project.yml").write_text(
            "name: empty_pattern\nversion: '1.0'\nconfig-version: 2\n"
            "profile: jaffle_shop\nmodel-paths: ['models']\ncheck-paths: ['checks']\n"
            "info_schema:\n  version: 1\n", encoding="utf-8"
        )
        (empty_pattern / "packages.yml").write_text(
            f"packages:\n  - local: {REPO_DIR.as_posix()}\n", encoding="utf-8"
        )
        pattern_env = os.environ.copy()
        pattern_env["JAFFLE_SHOP_DB_PATH"] = str(root / "empty_pattern.duckdb")
        deps = dbt("deps", project=empty_pattern, env=pattern_env)
        if deps.returncode != 0:
            raise AssertionError(f"dbt deps failed for empty pattern fixture:\n{deps.stdout}")
        check = dbt("check", "model_name_matches_pattern", "--select", "bad_pattern", project=empty_pattern, env=pattern_env)
        if check.returncode != 1 or "pattern must be a nonempty string" not in check.stdout:
            raise AssertionError(f"Empty regex pattern was not rejected as a configuration error:\n{check.stdout}")

        malformed = root / "malformed_regex"
        (malformed / "models").mkdir(parents=True)
        (malformed / "models" / "bad_pattern.sql").write_text(
            '{{ config(meta={"checks.model_name_matches_pattern": {"pattern": "("}}) }}\nselect 1 as id\n',
            encoding="utf-8",
        )
        (malformed / "dbt_project.yml").write_text(
            "name: malformed_regex\nversion: '1.0'\nconfig-version: 2\n"
            "profile: jaffle_shop\nmodel-paths: ['models']\ncheck-paths: ['checks']\n"
            "info_schema:\n  version: 1\n", encoding="utf-8"
        )
        (malformed / "packages.yml").write_text(
            f"packages:\n  - local: {REPO_DIR.as_posix()}\n", encoding="utf-8"
        )
        env = os.environ.copy()
        env["JAFFLE_SHOP_DB_PATH"] = str(root / "malformed_regex.duckdb")
        deps = dbt("deps", project=malformed, env=env)
        if deps.returncode != 0:
            raise AssertionError(f"dbt deps failed for malformed regex fixture:\n{deps.stdout}")
        check = dbt("check", "model_name_matches_pattern", "--select", "bad_pattern", project=malformed, env=env)
        if check.returncode == 0 or not re.search(r"regex|regular expression|pattern", check.stdout, re.I):
            raise AssertionError(f"Malformed regex did not fail with a regex diagnostic:\n{check.stdout}")


def assert_override_removals() -> None:
    """Remove each exemption/override in isolation and prove inherited policy applies."""
    cases = [
        (
            "customers_sql_pattern",
            "model_name_matches_pattern",
            "customers",
            "models/marts/customers.sql",
            '    meta={"checks.model_name_matches_pattern": {"pattern": "customers"}}\n',
            '    meta={}\n',
            "model name does not match pattern",
        ),
        (
            "inline_sql_pattern",
            "model_name_matches_pattern",
            "inline_sql_pattern_case",
            "models/staging/inline_sql_pattern_case.sql",
            '{{ config(meta={"checks.model_name_matches_pattern": {"pattern": "inline_.*"}}) }}\n',
            "",
            "model name does not match pattern",
        ),
        (
            "orders_yaml_pattern_exemption",
            "model_name_matches_pattern",
            "orders",
            "models/marts/schema.yml",
            '        "checks.model_name_matches_pattern": false\n',
            "",
            "model name does not match pattern",
        ),
        (
            "yaml_custom_pattern",
            "model_name_matches_pattern",
            "yaml_pattern_model",
            "models/marts/schema.yml",
            '        "checks.model_name_matches_pattern":\n          pattern: "yaml_.*"\n',
            "",
            "model name does not match pattern",
        ),
        (
            "yaml_column_exemption",
            "column_has_description",
            "fct_yaml_column_exemption",
            "models/marts/schema.yml",
            '  - name: fct_yaml_column_exemption\n    description: "Fixture for an individual YAML column-check exemption."\n    config:\n      meta:\n        "checks.column_has_description": false\n        "checks.model_has_grain_test": false\n',
            '  - name: fct_yaml_column_exemption\n    description: "Fixture for an individual YAML column-check exemption."\n    config:\n      meta:\n        "checks.model_has_grain_test": false\n',
            "missing column description",
        ),
        (
            "sql_column_exemption",
            "column_has_description",
            "dim_sql_grain_exemption",
            "models/marts/dim_sql_grain_exemption.sql",
            ', "checks.column_has_description": false',
            "",
            "missing column description",
        ),
        (
            "sql_grain_exemption",
            "model_has_grain_test",
            "dim_sql_grain_exemption",
            "models/marts/dim_sql_grain_exemption.sql",
            '{{ config(meta={"checks.model_has_grain_test": false, "checks.column_has_description": false}) }}\n',
            '{{ config(meta={"checks.column_has_description": false}) }}\n',
            "missing accepted grain test",
        ),
        (
            "yaml_grain_exemption",
            "model_has_grain_test",
            "orders",
            "models/marts/schema.yml",
            '        "checks.model_has_grain_test": false\n',
            "",
            "missing accepted grain test",
        ),
    ]
    with tempfile.TemporaryDirectory(prefix="dbt-checks-overrides-") as temporary:
        root = Path(temporary)
        for name, check_name, resource, relative_path, old, new, expected in cases:
            project = root / name
            shutil.copytree(
                PROJECT_DIR,
                project,
                ignore=shutil.ignore_patterns("target", "dbt_packages", "logs", "*.duckdb"),
            )
            packages_path = project / "packages.yml"
            packages_path.write_text(f"packages:\n  - local: {REPO_DIR.as_posix()}\n", encoding="utf-8")
            target_file = project / relative_path
            original = target_file.read_text(encoding="utf-8")
            if old not in original:
                raise AssertionError(f"Could not find override to remove for {name} in {relative_path}")
            target_file.write_text(original.replace(old, new, 1), encoding="utf-8")
            env = os.environ.copy()
            env["JAFFLE_SHOP_DB_PATH"] = str(root / f"{name}.duckdb")
            deps = dbt("deps", project=project, env=env)
            if deps.returncode != 0:
                raise AssertionError(f"dbt deps failed for override case {name}:\n{deps.stdout}")
            result = dbt("check", check_name, "--select", resource, project=project, env=env)
            if result.returncode == 0 or resource not in result.stdout or expected not in result.stdout:
                raise AssertionError(
                    f"Removing {name} should expose inherited failure {expected!r}:\n{result.stdout}"
                )


def main() -> int:
    for args in (("deps",),):
        result = dbt(*args)
        if result.returncode != 0:
            raise AssertionError(f"dbt {' '.join(args)} failed:\n{result.stdout}")
        print(f"PASS dbt {' '.join(args)}")

    subprocess.run([sys.executable, str(PROJECT_DIR / "setup_database.py")], check=True)
    if not DB_PATH.exists():
        raise AssertionError(f"Setup did not create DuckDB database {DB_PATH}")

    for args in (("seed",), ("build", "--skip-checks")):
        result = dbt(*args)
        if result.returncode != 0:
            raise AssertionError(f"dbt {' '.join(args)} failed:\n{result.stdout}")
        print(f"PASS dbt {' '.join(args)}")

    assert_full_suite()
    print("PASS plain dbt check returned exactly the declared failures")

    for source_check in ("source_table_has_description", "source_table_has_test"):
        assert_source_cases(source_check)
        print(f"PASS {source_check}: raw_customers passes and raw_orders fails")

    for case in FOCUSED_CASES:
        assert_case(case)
        print(f"PASS {case.check} --select {case.resource} ({'pass' if case.passes else 'expected failure'})")

    assert_override_removals()
    print("PASS removing YAML and SQL overrides restores inherited check failures")

    invalid_settings_cases()
    print("PASS invalid types, unknown options, empty arguments, absent settings, and malformed regex")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
