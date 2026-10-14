{# Códigos de estado. 15 y 16 se confirmaron con el detalle (campo Estado): Revocada y Suspendida.
   La documentación pública de la API los lista como 18 y 19; se mantienen ambos por si acaso. #}
{% macro estado_licitacion(col) -%}
case {{ col }}
    when 5 then 'publicada'
    when 6 then 'cerrada'
    when 7 then 'desierta'
    when 8 then 'adjudicada'
    when 15 then 'revocada'
    when 16 then 'suspendida'
    when 18 then 'revocada'
    when 19 then 'suspendida'
    else 'no_documentado_' || cast({{ col }} as varchar)
end
{%- endmacro %}
