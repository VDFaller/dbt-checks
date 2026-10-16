with configured_models as (
    {{ dbt_checks.configured_models('model_has_contract') }}
)

select
    configured_models.unique_id,
    coalesce(
        configured_models.config_error,
        'model contract is not enforced'
    ) as issue
from configured_models
left join {{ info_schema('models') }} as models
    on models.unique_id = configured_models.unique_id
where configured_models.config_error is not null
    or coalesce(models.contract_enforced, false) = false
