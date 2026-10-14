{# Códigos de estado según la documentación de la API. 15 y 16 aparecen en los datos pero no
   están documentados: se marcan explícitamente para no inventarles significado. #}
{% macro estado_licitacion(col) -%}
case {{ col }}
    when 5 then 'publicada'
    when 6 then 'cerrada'
    when 7 then 'desierta'
    when 8 then 'adjudicada'
    when 18 then 'revocada'
    when 19 then 'suspendida'
    else 'no_documentado_' || cast({{ col }} as varchar)
end
{%- endmacro %}
