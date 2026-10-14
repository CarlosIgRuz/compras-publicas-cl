-- Una fila por línea adjudicada (ítem × proveedor) de licitaciones adjudicadas.
-- Fuente: Dirección ChileCompra.
select
    i.codigo,
    i.posicion,
    i.correlativo,
    i.rut_proveedor,
    i.proveedor,
    i.rubro,
    i.codigo_categoria,
    i.producto,
    l.codigo_organismo,
    l.region,
    l.fecha_adjudicacion,
    l.moneda,
    case when l.moneda = 'CLP' then i.monto_adjudicado end as monto_adjudicado_clp
from {{ ref('stg_detalle_items') }} i
join {{ ref('fct_licitaciones') }} l using (codigo)
where l.estado = 'adjudicada'
  and i.rut_proveedor is not null
