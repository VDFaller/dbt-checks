select unique_id
from {{ info_schema('sources') }}
where enabled
  and coalesce(trim(description), '') = ''
