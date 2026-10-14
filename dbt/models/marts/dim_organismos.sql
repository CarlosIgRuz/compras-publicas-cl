-- Una fila por organismo comprador, con su actividad y tasa de licitaciones desiertas.
-- Nombre y región: los de su licitación publicada más recientemente.
-- Fuente: Dirección ChileCompra.
select
    codigo_organismo,
    arg_max(organismo, fecha_publicacion)                     as organismo,
    arg_max(region, fecha_publicacion)                        as region,
    count(*)                                                  as n_licitaciones,
    count(*) filter (where tiene_resultado)                   as n_con_resultado,
    avg(case when es_desierta then 1.0 else 0.0 end)
        filter (where tiene_resultado)                        as tasa_desierta,
    avg(numero_oferentes) filter (where estado = 'adjudicada') as oferentes_promedio,
    sum(monto_adjudicado_clp)                                 as monto_adjudicado_clp,
    min(fecha_publicacion)                                    as primera_publicacion,
    max(fecha_publicacion)                                    as ultima_publicacion
from {{ ref('fct_licitaciones') }}
group by codigo_organismo
