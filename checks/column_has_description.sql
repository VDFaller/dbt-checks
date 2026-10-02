with configured_models as (
    {{ dbt_checks.configured_models('column_has_description') }}
)

select
    configured_models.unique_id,
    null::varchar as column_name,
    configured_models.config_error as issue
from configured_models
where configured_models.config_error is not null

union all

select
    configured_models.unique_id,
    node_columns.column_name,
    'missing column description' as issue
from configured_models
inner join {{ info_schema('node_columns') }} as node_columns
    on node_columns.node_unique_id = configured_models.unique_id
where configured_models.settings.enabled
    and configured_models.config_error is null
    and coalesce(trim(node_columns.description), '') = ''
