# dbt-checks

Reusable `dbt check` checks for dbt projects.

The package currently enforces documentation and test coverage for enabled
models and sources:

- every enabled model has a properties YAML file;
- every enabled model has a description;
- every enabled model has at least one data test;
- every enabled source table has a description;
- every enabled source table has at least one data test;
- every enabled model opting into the grain check has an accepted grain test
  with matching not-null tests;
- columns have descriptions on models that opt in with
  `"checks.column_has_description": true` under `meta`; and
- opted-in model names fully match a configurable regex pattern.

Put each check directly under `+meta` as a separate, quoted `checks.*` key.
This lets dbt inherit or override one check without replacing the settings
for another check. For example, enable the grain check for every model, and
require column descriptions and a name pattern in marts:

```yaml
models:
  your_project:
    +meta:
      "checks.model_has_grain_test":
        accepted_test_names:
          - unique
          - unique_combination_of_columns
          - expect_compound_columns_to_be_unique
    marts:
      +meta:
        "checks.column_has_description": true
        "checks.model_name_matches_pattern":
          pattern: "(dim_|fct_).*"
```

The grain check accepts `unique`, `combination_of_columns`, and
`expect_compound_columns_to_be_unique` by default. Set its value to `true` to
use that default, `false` to disable it on a path or model, or an
object to specify `accepted_test_names`. A more specific value replaces the
whole value for that check. The second name above is dbt-utils' compound
uniqueness test; the third is the equivalent dbt-expectations test. These are
bare generic test names, not package-qualified YAML keys. A model passes when
an accepted uniqueness test has matching built-in `not_null` tests for all of
its grain columns. `checks.column_has_description` takes `true` or `false`.
Absent keys are off; invalid values cause the corresponding check to fail.
To use different accepted tests in a subfolder, set
`"checks.model_has_grain_test"` in that subfolder's `+meta`; it replaces the
inherited value for that check. To exempt one model while keeping its path's
policy, put this in its properties YAML:

```yaml
models:
  - name: exceptional_model
    config:
      meta:
        "checks.model_has_grain_test": false
```

Install it from a dbt package source in `packages.yml`, or use a local path
while developing:

```yaml
packages:
  - local: /path/to/dbt-checks
```

The repository can also be installed from Git with
`git: https://github.com/VDFaller/dbt-checks.git` (with access to the private
repository).

## Check names

Check names describe one failing entity, even when a check scans the whole
project. For example, `model_has_test` reports an individual model without a
test, and `source_table_has_test` reports an individual source table.

These names replace the earlier plural names. Update any `checks.dbt_checks`
overrides that use them; for the column check, also update its `checks.*` meta
key:

| Previous name | Current name |
| --- | --- |
| `models_have_properties_files` | `model_has_properties_file` |
| `models_have_descriptions` | `model_has_description` |
| `models_have_tests` | `model_has_test` |
| `source_tables_have_descriptions` | `source_table_has_description` |
| `sources_have_tests` | `source_table_has_test` |
| `columns_have_descriptions` | `column_has_description` |

## Overriding checks

The consuming project's `dbt_project.yml` can disable individual checks without
editing this package. Use the package name `dbt_checks` and the check name:

```yaml
checks:
  dbt_checks:
    model_has_test:
      +enabled: false
```

The same pattern applies to `column_has_description`,
`model_has_grain_test`, `model_name_matches_pattern`,
`model_has_description`, `model_has_properties_file`,
`source_table_has_description`, and `source_table_has_test`. To disable every
check from this package:

```yaml
checks:
  dbt_checks:
    +enabled: false
```

## Writing configurable checks

For a model-level check, `configured_models(check_name, arg_defaults=none)`
produces the enabled models with that `meta` key, plus models with invalid
configuration so the check can report an error. It omits absent and explicitly
disabled checks. A boolean-only check needs only its name:

```sql
with configured_models as (
    {{ dbt_checks.configured_models('column_has_description') }}
)
```

For a check with arguments, pass a map of argument names to their defaults:

```sql
with configured_models as (
    {{ dbt_checks.configured_models(
        'model_has_grain_test',
        {
            'accepted_test_names': ['unique']
        }
    ) }}
)
```

The result has `unique_id`, `settings`, `config_error`, and a typed SQL column
for each argument. A nonempty string default yields a string; a nonempty list
of nonempty strings yields a string array. Defaults are used only when an
argument is absent. Unsupported or empty defaults fail at compile time.
Invalid configured argument types, empty values, and unknown option names set
`config_error`; checks should report that error before evaluating their own
rule. Invalid arguments have null typed columns; valid arguments can be used
directly, for example
`regexp_full_match(models.name, configured_models.pattern)`. An object enables
checks that accept arguments. The lower-level `check_settings` and `check_arg`
macros are available if a check needs a different query shape. These macros
generate SQL against dbt's parse-time Information Schema, so they do not query
the consuming project's warehouse models.

## Model name contract

`model_name_matches_pattern` adapts dbt-checkpoint's
[`check-model-name-contract`](https://github.com/dbt-checkpoint/dbt-checkpoint/blob/main/HOOKS.md#check-model-name-contract)
to the per-model `meta` convention. Its `pattern` argument is a regular
expression that must match the entire model name. `true` uses the default
lowercase snake_case pattern; `false` disables the check for that model.
For example, configure staging and marts differently:

```yaml
models:
  your_project:
    staging:
      +meta:
        "checks.model_name_matches_pattern":
          pattern: "(base_|stg_).*"
    marts:
      +meta:
        "checks.model_name_matches_pattern":
          pattern: "(dim_|fct_).*"
```

The check reports non-string or empty patterns as configuration errors. An
invalid regex causes `dbt check` to fail with the database's regex error.

## Integration project

`integration_tests/jaffle_shop` is a complete DuckDB project that exercises all
eight checks against Jaffle Shop models, sources, descriptions, and tests. Its
`dbt check` output intentionally includes violations; the suite runner verifies
the exact expected resources and runs focused passing and failing checks for
each behavior. The fixtures cover project and folder inheritance, YAML and SQL
overrides, and invalid settings in isolated temporary projects.
The fixture keeps source checks focused by check name: dbt 2.0.6 currently
skips source-only check results when `--select` is supplied, so the runner
asserts both source outcomes from each isolated source-check report.

Install dbt v2 with its DuckDB adapter, then run the suite from the repository
root:

```sh
uv run integration_tests/jaffle_shop/run_suite.py
```

The runner installs the local `dbt_checks` package, recreates the fixture
database from the two `.csv.source` files, runs `dbt seed`, and builds the
models and tests with `dbt build --skip-checks` before checking the declared
outcomes. To inspect the deliberate failures directly:

```sh
dbt deps --project-dir integration_tests/jaffle_shop --profiles-dir integration_tests/jaffle_shop
uv run integration_tests/jaffle_shop/setup_database.py
dbt seed --project-dir integration_tests/jaffle_shop --profiles-dir integration_tests/jaffle_shop
dbt build --skip-checks --project-dir integration_tests/jaffle_shop --profiles-dir integration_tests/jaffle_shop
dbt check --project-dir integration_tests/jaffle_shop --profiles-dir integration_tests/jaffle_shop
```

Set `JAFFLE_SHOP_DB_PATH` to use a different DuckDB file. The setup script
recreates that file, so point it only at the integration database.
