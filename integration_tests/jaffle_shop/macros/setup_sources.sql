{% macro setup_sources() %}
    {% set source_dir = env_var('JAFFLE_SHOP_SOURCE_DIR') %}
    {% set customers_path = source_dir ~ '/seeds/raw_customers.csv.source' %}
    {% set orders_path = source_dir ~ '/seeds/raw_orders.csv.source' %}
    {% set customers_sql = "create table raw_customers as select * from read_csv_auto('"
        ~ customers_path | replace("'", "''") ~ "', header = true)" %}
    {% set orders_sql = "create table raw_orders as select * from read_csv_auto('"
        ~ orders_path | replace("'", "''") ~ "', header = true)" %}
    {% do run_query(customers_sql) %}
    {% do run_query(orders_sql) %}
    {% do log('Loaded raw_customers and raw_orders into DuckDB.', info=true) %}
{% endmacro %}
