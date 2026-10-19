-- Tabla de entrenamiento: una fila por licitación con variables conocidas AL PUBLICAR.
-- Nada de lo que se sabe después del cierre (n° de oferentes, fechas o montos de adjudicación,
-- reclamos acumulados) entra como variable.
-- El historial del organismo y del rubro es point-in-time: solo cuenta licitaciones cuyo
-- resultado (fecha del último evento en el listado) es ANTERIOR a la publicación de esta.
-- Fuente: Dirección ChileCompra.
{% set m = var('suavizado_m') %}
{% set p0 = var('tasa_previa_p0') %}

with base as (
    select
        l.*,
        d.fecha_listado as fecha_resolucion,  -- día del último evento (adjudicación, desierta, etc.)
        d.etapas
    from {{ ref('fct_licitaciones') }} l
    join {{ ref('stg_detalle') }} d using (codigo)
),

limite as (
    select max(fecha_listado) as ultimo_listado from {{ ref('stg_listados') }}
),

resueltas as (
    select codigo, codigo_organismo, rubro_principal, fecha_resolucion, es_desierta
    from base
    where tiene_resultado
),

hist_organismo as (
    select
        b.codigo,
        count(r.codigo)                                as org_n_previas,
        coalesce(sum(r.es_desierta::int), 0)           as org_desiertas_previas
    from base b
    left join resueltas r
        on r.codigo_organismo = b.codigo_organismo
       and r.fecha_resolucion < cast(b.fecha_publicacion as date)
       and r.codigo <> b.codigo
    group by b.codigo
),

hist_rubro as (
    select
        b.codigo,
        count(r.codigo)                                as rubro_n_previas,
        coalesce(sum(r.es_desierta::int), 0)           as rubro_desiertas_previas
    from base b
    left join resueltas r
        on r.rubro_principal = b.rubro_principal
       and r.fecha_resolucion < cast(b.fecha_publicacion as date)
       and r.codigo <> b.codigo
    group by b.codigo
)

select
    b.codigo,
    b.fecha_publicacion,
    b.es_desierta,
    b.tiene_resultado,
    coalesce(
        b.fecha_publicacion >= cast('{{ var("cohorte_desde") }}' as date)
        and cast(b.fecha_publicacion as date)
            <= (select ultimo_listado from limite) - {{ var('horizonte_dias') }},
        false)                                          as en_cohorte,

    -- proceso
    b.tipo,
    b.convocatoria,
    b.etapas,
    b.dias_abierta,
    extract('month' from b.fecha_publicacion)          as mes_publicacion,
    extract('isodow' from b.fecha_publicacion)         as dia_semana_publicacion,
    extract('hour' from b.fecha_publicacion)           as hora_publicacion,

    -- qué se compra
    b.rubro_principal,
    b.n_items,
    b.n_rubros,

    -- cuánto
    b.moneda,
    b.monto_visible,
    b.monto_estimado_clp is null                       as monto_desconocido,
    ln(1 + b.monto_estimado_clp)                       as log_monto_estimado_clp,

    -- quién y dónde
    b.codigo_organismo,
    b.region,

    -- historial point-in-time
    h.org_n_previas,
    (h.org_desiertas_previas + {{ m }} * {{ p0 }}) / (h.org_n_previas + {{ m }})       as org_tasa_desierta_previa,
    r.rubro_n_previas,
    (r.rubro_desiertas_previas + {{ m }} * {{ p0 }}) / (r.rubro_n_previas + {{ m }})   as rubro_tasa_desierta_previa
from base b
join hist_organismo h using (codigo)
join hist_rubro r using (codigo)
