{% macro configured_models(check_name, arg_defaults=none) -%}
    {% if arg_defaults is not none %}
        {% for arg_name, default in arg_defaults.items() %}
            {% if default is string %}
                {% if default | trim == '' %}
                    {{ exceptions.raise_compiler_error(
                        'default for check argument ' ~ arg_name ~ ' must be a nonempty string'
                    ) }}
                {% endif %}
            {% elif default is sequence and default is not mapping %}
                {% if default | length == 0 %}
                    {{ exceptions.raise_compiler_error(
                        'default for check argument ' ~ arg_name ~ ' must be a nonempty list of strings'
                    ) }}
                {% endif %}
                {% for item in default %}
                    {% if item is not string or item | trim == '' %}
                        {{ exceptions.raise_compiler_error(
                            'default for check argument ' ~ arg_name ~ ' must be a nonempty list of strings'
                        ) }}
                    {% endif %}
                {% endfor %}
            {% else %}
                {{ exceptions.raise_compiler_error(
                    'unsupported default for check argument ' ~ arg_name
                    ~ ': expected a nonempty string or list of nonempty strings'
                ) }}
            {% endif %}
        {% endfor %}
    {% endif %}
    select
        unique_id,
        settings,
        {% if arg_defaults is not none %}
            {% for arg_name, default in arg_defaults.items() %}
                {% if default is string %}
                    case
                        when json_type({{ arg_name }}_json) = 'VARCHAR'
                            and coalesce(
                                trim(json_extract_string({{ arg_name }}_json, '$')),
                                ''
                            ) <> ''
                            then json_extract_string({{ arg_name }}_json, '$')
                    end as {{ arg_name }},
                {% else %}
                    case
                        when json_type({{ arg_name }}_json) = 'ARRAY'
                            and json_array_length({{ arg_name }}_json) > 0
                            and not exists (
                                select 1
                                from json_each({{ arg_name }}_json) as item
                                where json_type(item.value) <> 'VARCHAR'
                                    or coalesce(
                                        trim(json_extract_string(item.value, '$')),
                                        ''
                                    ) = ''
                            )
                            then try_cast({{ arg_name }}_json as varchar[])
                    end as {{ arg_name }},
                {% endif %}
            {% endfor %}
        {% endif %}
        case
            when settings.error is not null then settings.error
            {% if arg_defaults is not none %}
                {% for arg_name, default in arg_defaults.items() %}
                    {% if default is string %}
                        when json_type({{ arg_name }}_json) <> 'VARCHAR'
                            or coalesce(
                                trim(json_extract_string({{ arg_name }}_json, '$')),
                                ''
                            ) = ''
                            then '{{ arg_name }} must be a nonempty string'
                    {% else %}
                        when json_type({{ arg_name }}_json) <> 'ARRAY'
                            or json_array_length({{ arg_name }}_json) = 0
                            then '{{ arg_name }} must be a nonempty array'
                        when exists (
                            select 1
                            from json_each({{ arg_name }}_json) as item
                            where json_type(item.value) <> 'VARCHAR'
                                or coalesce(
                                    trim(json_extract_string(item.value, '$')),
                                    ''
                                ) = ''
                        )
                            then '{{ arg_name }} must contain nonempty strings'
                    {% endif %}
                {% endfor %}
            {% endif %}
        end as config_error
    from (
        select
            unique_id,
            settings
            {% if arg_defaults is not none %}
                {% for arg_name, default in arg_defaults.items() %}
                    , {{ dbt_checks.check_arg(
                        'settings', arg_name, default | tojson
                    ) }} as {{ arg_name }}_json
                {% endfor %}
            {% endif %}
        from (
            select
                unique_id,
                {{ dbt_checks.check_settings(
                    'meta',
                    check_name,
                    arg_defaults | list if arg_defaults is not none else none
                ) }} as settings
            from {{ info_schema('models') }}
            where enabled
        ) as model_settings
        where settings.configured
          and (settings.enabled or settings.error is not null)
    ) as raw_args
{%- endmacro %}
