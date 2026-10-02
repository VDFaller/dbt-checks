select unique_id
from {{ info_schema('models') }}
where enabled
  and coalesce(trim(description), '') = ''
