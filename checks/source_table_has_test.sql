with source_tests as (
    select distinct json_extract_string(arguments, '$.model') as model_argument
    from {{ info_schema('data_tests') }}
    where json_extract_string(arguments, '$.model') is not null
)

select sources.unique_id
from {{ info_schema('sources') }} as sources
left join source_tests
    on contains(
        source_tests.model_argument,
        concat('source(''', sources.source_name, ''', ''', sources.name, ''')')
    )
where sources.enabled
  and source_tests.model_argument is null
