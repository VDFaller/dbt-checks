{% macro check_settings(meta_expression, check_name, allowed_args=none) -%}
    {% set path = '$."checks.' ~ check_name ~ '"' %}
    {% set value = "json_extract(" ~ meta_expression ~ ", '" ~ path ~ "')" %}
    {% set kind = "json_type(" ~ meta_expression ~ ", '" ~ path ~ "')" %}
    struct_pack(
        configured := {{ kind }} is not null,
        enabled := coalesce(
            (
                {{ kind }} = 'BOOLEAN'
                and json_extract_string({{ value }}, '$') = 'true'
            )
            {% if allowed_args is not none %}
                or {{ kind }} = 'OBJECT'
            {% endif %},
            false
        ),
        error := case
            when {{ kind }} is null then null
            {% if allowed_args is none %}
                when {{ kind }} <> 'BOOLEAN'
                    then 'check config must be true or false'
            {% else %}
                when {{ kind }} not in ('BOOLEAN', 'OBJECT')
                    then 'check config must be true, false, or an object'
                when {{ kind }} = 'OBJECT'
                    and exists (
                        select 1
                        from json_each({{ value }}) as option
                        {% if allowed_args | length == 0 %}
                            where true
                        {% else %}
                            where option.key not in (
                                '{{ allowed_args
                                    | map('replace', "'", "''")
                                    | join("', '") }}'
                            )
                        {% endif %}
                    )
                    then 'unknown check option'
            {% endif %}
        end,
        raw := {{ value }}
    )
{%- endmacro %}


{% macro check_arg(settings_expression, arg_name, default_json) -%}
    coalesce(
        json_extract({{ settings_expression }}.raw, '$.{{ arg_name }}'),
        '{{ default_json | replace("'", "''") }}'::json
    )
{%- endmacro %}
