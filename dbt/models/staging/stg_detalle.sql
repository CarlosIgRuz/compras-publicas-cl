{{ config(materialized="table") }}
-- Una fila por licitación con su detalle (data/raw/detalle), tipado.
-- Se excluyen a propósito los datos personales de funcionarios (nombres, correos, teléfonos).
-- Fuente: Dirección ChileCompra.
with crudo as (
    select
        codigo,
        descargado,
        detalle as d,
        cast(regexp_extract(filename, 'fecha=([0-9-]{10})', 1) as date) as fecha_listado
    from {{ leer_detalle() }}
    where detalle is not null and json_type(detalle) = 'OBJECT'
)

select
    codigo,
    fecha_listado,
    descargado,

    -- estado y tipo
    {{ num_json('d', '$.CodigoEstado', 'integer') }}                    as codigo_estado,
    {{ estado_licitacion(num_json('d', '$.CodigoEstado', 'integer')) }} as estado,
    {{ texto_json('d', '$.Estado') }}                                   as estado_api,
    {{ texto_json('d', '$.Tipo') }}                                     as tipo,
    case {{ num_json('d', '$.CodigoTipo', 'integer') }}
        when 1 then 'publica' when 2 then 'privada' end                 as convocatoria,
    {{ texto_json('d', '$.Nombre') }}                                   as nombre,
    {{ texto_json('d', '$.Descripcion') }}                              as descripcion,

    -- comprador (organismo y unidad de compra)
    {{ texto_json('d', '$.Comprador.CodigoOrganismo') }}                as codigo_organismo,
    {{ texto_json('d', '$.Comprador.NombreOrganismo') }}                as organismo,
    {{ texto_json('d', '$.Comprador.CodigoUnidad') }}                   as codigo_unidad,
    {{ texto_json('d', '$.Comprador.NombreUnidad') }}                   as unidad,
    {{ texto_json('d', '$.Comprador.RutUnidad') }}                      as rut_unidad,
    {{ texto_json('d', '$.Comprador.RegionUnidad') }}                   as region,
    {{ texto_json('d', '$.Comprador.ComunaUnidad') }}                   as comuna,

    -- montos
    {{ texto_json('d', '$.Moneda') }}                                   as moneda,
    {{ num_json('d', '$.MontoEstimado') }}                              as monto_estimado,
    {{ num_json('d', '$.VisibilidadMonto', 'integer') }} = 1            as monto_visible,
    {{ num_json('d', '$.Modalidad', 'integer') }}                       as modalidad_pago,
    {{ texto_json('d', '$.FuenteFinanciamiento') }}                     as fuente_financiamiento,

    -- fechas del proceso
    {{ fecha_json('d', '$.Fechas.FechaCreacion') }}                     as fecha_creacion,
    {{ fecha_json('d', '$.Fechas.FechaPublicacion') }}                  as fecha_publicacion,
    {{ fecha_json('d', '$.Fechas.FechaCierre') }}                       as fecha_cierre,
    {{ fecha_json('d', '$.Fechas.FechaEstimadaAdjudicacion') }}         as fecha_estimada_adjudicacion,
    {{ fecha_json('d', '$.Fechas.FechaAdjudicacion') }}                 as fecha_adjudicacion,

    -- resultado (solo existe en adjudicadas y desiertas)
    {{ num_json('d', '$.Adjudicacion.NumeroOferentes', 'integer') }}    as numero_oferentes,
    {{ num_json('d', '$.Adjudicacion.Tipo', 'integer') }}               as tipo_adjudicacion,

    -- otros
    {{ num_json('d', '$.Items.Cantidad', 'integer') }}                  as n_items,
    {{ num_json('d', '$.CantidadReclamos', 'integer') }}                as cantidad_reclamos,
    {{ num_json('d', '$.Etapas', 'integer') }}                          as etapas,
    {{ num_json('d', '$.Informada', 'integer') }} = 1                   as informada
from crudo
qualify row_number() over (partition by codigo order by descargado desc) = 1
