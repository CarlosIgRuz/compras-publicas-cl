{# Helpers para leer el JSON crudo del detalle. #}

{# Fecha de la API: la API usa 1900-01-0x como "sin fecha"; se vuelve NULL. #}
{% macro fecha_json(json_col, ruta) -%}
case when try_cast({{ json_col }} ->> '{{ ruta }}' as timestamp) >= timestamp '1990-01-01'
     then try_cast({{ json_col }} ->> '{{ ruta }}' as timestamp) end
{%- endmacro %}

{% macro texto_json(json_col, ruta) -%}
nullif(trim({{ json_col }} ->> '{{ ruta }}'), '')
{%- endmacro %}

{% macro num_json(json_col, ruta, tipo='double') -%}
try_cast({{ json_col }} ->> '{{ ruta }}' as {{ tipo }})
{%- endmacro %}

{# Lee los archivos de detalle (lista de {codigo, descargado, detalle}) con el detalle como JSON
   sin inferir esquema, para que un campo nuevo o con tipo cambiante no rompa la lectura. #}
{% macro leer_detalle() -%}
read_json(
    '{{ var("raw_dir") }}/detalle/fecha=*.json.gz',
    format = 'array',
    filename = true,
    columns = {codigo: 'VARCHAR', descargado: 'TIMESTAMPTZ', detalle: 'JSON'}
)
{%- endmacro %}
