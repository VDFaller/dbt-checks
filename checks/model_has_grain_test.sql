with configured_models as (
    {{ dbt_checks.configured_models(
        'model_has_grain_test',
        {
            'accepted_test_names': ['unique', 'combination_of_columns', 'expect_compound_columns_to_be_unique']
        }
    ) }}
),

accepted_test_names as (
    select
        configured_models.unique_id,
        lower(trim(test_name.value)) as test_name
    from configured_models
    cross join unnest(configured_models.accepted_test_names) as test_name(value)
    where configured_models.config_error is null
),

accepted_grain_tests as (
    select
        data_tests.node_unique_id,
        data_tests.unique_id as test_unique_id,
        case
            -- unique
            when json_extract(data_tests.arguments, '$.column_name') is not null
                then [json_extract_string(data_tests.arguments, '$.column_name')]
            -- unique_combination_of_columns
            when json_extract(data_tests.arguments, '$.combination_of_columns') is not null
                then json_extract(
                    data_tests.arguments,
                    '$.combination_of_columns'
                )::varchar[]
            -- expect_compound_columns_to_be_unique
            when json_extract(data_tests.arguments, '$.column_list') is not null
                then json_extract(
                    data_tests.arguments,
                    '$.column_list'
                )::varchar[]
        end as grain_columns
    from {{ info_schema('data_tests') }} as data_tests
    inner join accepted_test_names
        on accepted_test_names.unique_id = data_tests.node_unique_id
        and accepted_test_names.test_name = lower(data_tests.test_name)
),

not_null_tests as (
    select
        node_unique_id,
        json_extract_string(arguments, '$.column_name') as column_name
    from {{ info_schema('data_tests') }}
    where test_name = 'not_null'
),

grain_tests_with_not_nulls as (
    select
        accepted_grain_tests.node_unique_id,
        accepted_grain_tests.test_unique_id,
        accepted_grain_tests.grain_columns,
        count(distinct not_null_tests.column_name) as not_null_column_count
    from accepted_grain_tests
    left join not_null_tests
        on not_null_tests.node_unique_id = accepted_grain_tests.node_unique_id
        and list_contains(
            accepted_grain_tests.grain_columns,
            not_null_tests.column_name
        )
    where list_count(accepted_grain_tests.grain_columns) > 0
    group by
        accepted_grain_tests.node_unique_id,
        accepted_grain_tests.test_unique_id,
        accepted_grain_tests.grain_columns
),

models_with_valid_grain_tests as (
    select node_unique_id
    from grain_tests_with_not_nulls
    where not_null_column_count = list_count(grain_columns)
    group by node_unique_id
)

select
    configured_models.unique_id,
    coalesce(
        configured_models.config_error,
        'missing accepted grain test with not_null on every grain column'
    ) as issue
from configured_models
left join models_with_valid_grain_tests
    on models_with_valid_grain_tests.node_unique_id = configured_models.unique_id
where configured_models.config_error is not null
    or models_with_valid_grain_tests.node_unique_id is null
