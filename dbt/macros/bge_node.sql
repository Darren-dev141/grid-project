{% macro bge_node() -%}
  {% if not execute %}
    {{ return('NULL') }}
  {% endif %}
  {% set configured = var('bge_pnode_id') %}
  {% if configured | string != (configured | int) | string or configured | int <= 0 %}
    {{ exceptions.raise_compiler_error('bge_pnode_id must be an explicitly verified positive integer node ID') }}
  {% endif %}
  {{ configured | int }}
{%- endmacro %}
