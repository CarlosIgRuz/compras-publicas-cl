-- Una fila por licitación con su detalle: proceso, comprador, rubro principal, montos y resultado.
-- Es la tabla base del modelo (P1.6–P1.7) y del estudio causal (P2).
-- Montos: solo se dan en CLP; las licitaciones en UF/USD/UTM (~2%) quedan con monto_*_clp NULL
-- hasta incorporar tipos de cambio.
-- Fuente: Dirección ChileCompra.
with items as (
    select
        codigo,
        count(distinct correlativo)                       as n_items,
        count(distinct rubro)                             as n_rubros,
        count(distinct rut_proveedor)                     as n_proveedores_adjudicados,
        sum(monto_adjudicado)                             as monto_adjudicado
    from {{ ref('stg_detalle_items') }}
    group by codigo
),

-- rubro con más ítems; empate → orden alfabético (determinista)
rubro_principal as (
    select codigo, rubro as rubro_principal
    from {{ ref('stg_detalle_items') }}
    where rubro is not null
    group by codigo, rubro
    qualify row_number() over (partition by codigo order by count(*) desc, rubro) = 1
)

select
    d.codigo,
    d.nombre,
    d.tipo,
    d.convocatoria,
    d.estado,

    -- resultado: solo adjudicada y desierta son finales "con decisión" (objetivo del modelo)
    d.estado in ('adjudicada', 'desierta')                 as tiene_resultado,
    case when d.estado in ('adjudicada', 'desierta')
         then d.estado = 'desierta' end                    as es_desierta,
    d.numero_oferentes,

    -- comprador
    d.codigo_organismo,
    d.organismo,
    d.codigo_unidad,
    d.region,

    -- rubro e ítems
    r.rubro_principal,
    coalesce(i.n_items, 0)                                 as n_items,
    coalesce(i.n_rubros, 0)                                as n_rubros,
    coalesce(i.n_proveedores_adjudicados, 0)               as n_proveedores_adjudicados,

    -- montos
    d.moneda,
    d.monto_visible,
    case when d.moneda = 'CLP' then d.monto_estimado end   as monto_estimado_clp,
    case when d.moneda = 'CLP' and d.estado = 'adjudicada'
         then i.monto_adjudicado end                       as monto_adjudicado_clp,

    -- fechas y plazos
    d.fecha_publicacion,
    cast(date_trunc('month', d.fecha_publicacion) as date) as mes_publicacion,
    d.fecha_cierre,
    d.fecha_adjudicacion,
    date_diff('day', d.fecha_publicacion, d.fecha_cierre)  as dias_abierta,
    date_diff('day', d.fecha_cierre, d.fecha_adjudicacion) as dias_hasta_adjudicacion,

    d.cantidad_reclamos,
    d.descargado
from {{ ref('stg_detalle') }} d
left join items i using (codigo)
left join rubro_principal r using (codigo)
