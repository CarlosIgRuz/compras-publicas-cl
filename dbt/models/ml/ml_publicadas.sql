-- Licitaciones recién publicadas, con las variables que recibe el modelo al publicar.
-- Es lo que se puntúa cada día (compras.monitor.puntuar) y la población "actual" del monitoreo.
-- Rubro principal: misma regla que fct_licitaciones (rubro con más ítems; empate → alfabético).
-- Fuente: Dirección ChileCompra.
with items as (
    select codigo, count(distinct correlativo) as n_items, count(distinct rubro) as n_rubros
    from {{ ref('stg_publicacion_items') }}
    group by codigo
),

rubro_principal as (
    select codigo, rubro as rubro_principal
    from {{ ref('stg_publicacion_items') }}
    where rubro is not null
    group by codigo, rubro
    qualify row_number() over (partition by codigo order by count(*) desc, rubro) = 1
)

select
    d.codigo,
    d.fecha_publicacion,
    d.fecha_listado,
    d.estado                                              as estado_al_descargar,
    d.tipo,
    d.convocatoria,
    r.rubro_principal,
    coalesce(i.n_items, 0)                                as n_items,
    coalesce(i.n_rubros, 0)                               as n_rubros,
    d.moneda,
    d.region,
    d.codigo_organismo,
    d.etapas,
    case when d.moneda = 'CLP' then d.monto_estimado end  as monto_estimado_clp,
    d.monto_visible
from {{ ref('stg_publicacion') }} d
left join items i using (codigo)
left join rubro_principal r using (codigo)
