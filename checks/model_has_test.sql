select models.unique_id
from {{ info_schema('models') }} as models
left join (
    select distinct node_unique_id
    from {{ info_schema('data_tests') }}
    where node_unique_id is not null
) as tests
    on tests.node_unique_id = models.unique_id
where models.enabled
  and tests.node_unique_id is null
