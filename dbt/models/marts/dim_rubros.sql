-- Una fila por rubro (primer nivel de la clasificación de ONU usada por ChileCompra),
-- según el rubro principal de cada licitación.
-- Fuente: Dirección ChileCompra.
select
    rubro_principal                                           as rubro,
    count(*)                                                  as n_licitaciones,
    count(*) filter (where tiene_resultado)                   as n_con_resultado,
    avg(case when es_desierta then 1.0 else 0.0 end)
        filter (where tiene_resultado)                        as tasa_desierta,
    median(numero_oferentes) filter (where estado = 'adjudicada') as oferentes_mediana,
    median(monto_estimado_clp)                                as monto_estimado_mediana_clp,
    count(distinct codigo_organismo)                          as n_organismos
from {{ ref('fct_licitaciones') }}
where rubro_principal is not null
group by rubro_principal
