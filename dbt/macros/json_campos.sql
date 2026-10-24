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
{% macro leer_detalle(carpeta='detalle') -%}
{#- Si la carpeta aún no tiene archivos (p. ej. detalle_publicacion antes de la primera noche),
    devuelve una relación vacía con las mismas columnas en vez de fallar. -#}
{%- set patron = var("raw_dir") ~ "/" ~ carpeta ~ "/fecha=*.json.gz" -%}
{%- set hay = true -%}
{%- if execute -%}
    {%- set hay = run_query("select count(*) from glob('" ~ patron ~ "')").columns[0].values()[0] > 0 -%}
{%- endif -%}
{%- if hay -%}
read_json(
    '{{ patron }}',
    format = 'array',
    filename = true,
    columns = {codigo: 'VARCHAR', descargado: 'TIMESTAMPTZ', detalle: 'JSON'}
)
{%- else -%}
(select null::varchar as codigo, null::timestamptz as descargado, null::json as detalle,
        null::varchar as filename where false)
{%- endif -%}
{%- endmacro %}
