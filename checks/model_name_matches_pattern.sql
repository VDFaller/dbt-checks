with configured_models as (
    {{ dbt_checks.configured_models(
        'model_name_matches_pattern',
        {
            'pattern': '^[a-z][a-z0-9_]*$'
        }
    ) }}
),

validated_models as (
    select
        configured_models.unique_id,
        case
            when configured_models.config_error is not null
                then configured_models.config_error
            when not regexp_full_match(
                models.name,
                configured_models.pattern
            )
                then 'model name does not match pattern: '
                    || configured_models.pattern
        end as issue
    from configured_models
    inner join {{ info_schema('models') }} as models
        on models.unique_id = configured_models.unique_id
)

select unique_id, issue
from validated_models
where issue is not null
