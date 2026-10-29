with configured_models as (
    {{ dbt_checks.configured_models(
        'column_is_documented',
        {'require_data_type': true}
    ) }}
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
    case
        when coalesce(trim(node_columns.description), '') = ''
            then 'missing column description'
        when configured_models.require_data_type
            and coalesce(trim(node_columns.data_type_declared), '') = ''
            then 'missing declared data type'
    end as issue
from configured_models
inner join {{ info_schema('node_columns') }} as node_columns
    on node_columns.node_unique_id = configured_models.unique_id
where configured_models.settings.enabled
    and configured_models.config_error is null
    and (
        coalesce(trim(node_columns.description), '') = ''
        or (
            configured_models.require_data_type
            and coalesce(trim(node_columns.data_type_declared), '') = ''
        )
    )
