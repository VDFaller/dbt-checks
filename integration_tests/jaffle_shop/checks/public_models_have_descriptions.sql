with configured_models as (
    {{ dbt_checks.configured_models('public_models_have_descriptions') }}
)

select models.unique_id
from configured_models
inner join {{ info_schema('models') }} as models
    on models.unique_id = configured_models.unique_id
where configured_models.config_error is not null
    or (
        models.access = 'public'
        and coalesce(trim(models.description), '') = ''
    )
