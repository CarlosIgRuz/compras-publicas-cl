{{ config(materialized="table") }}
-- Una fila por línea de Items.Listado de cada licitación, con su adjudicación si existe.
-- Un mismo ítem (correlativo) aparece una vez por proveedor cuando se adjudica a varios;
-- por eso la clave es (codigo, posicion), la posición de la línea en la lista original.
-- Ojo: en algunos ítems la API invierte Cantidad y MontoUnitario de la adjudicación
-- (ej. cantidad 175.000.000 y monto unitario 1); el producto es igual, así que se usa
-- monto_adjudicado = cantidad × monto unitario y no cada campo por separado.
-- Fuente: Dirección ChileCompra.
with licitaciones as (
    select codigo, detalle as d
    from {{ leer_detalle() }}
    where detalle is not null and json_type(detalle) = 'OBJECT'
    qualify row_number() over (partition by codigo order by descargado desc) = 1
),

listas as (
    select codigo, from_json(d -> '$.Items.Listado', '["JSON"]') as lista
    from licitaciones
),

items as (
    select codigo, pos + 1 as posicion, lista[pos + 1] as i
    from listas, unnest(range(len(lista))) as t(pos)
)

select
    codigo,
    posicion,
    {{ num_json('i', '$.Correlativo', 'integer') }}                     as correlativo,
    {{ texto_json('i', '$.CodigoProducto') }}                           as codigo_producto,
    {{ texto_json('i', '$.CodigoCategoria') }}                          as codigo_categoria,
    {{ texto_json('i', '$.Categoria') }}                                as categoria,
    split_part({{ texto_json('i', '$.Categoria') }}, ' / ', 1)          as rubro,
    {{ texto_json('i', '$.NombreProducto') }}                           as producto,
    {{ texto_json('i', '$.UnidadMedida') }}                             as unidad_medida,
    {{ num_json('i', '$.Cantidad') }}                                   as cantidad,
    {{ texto_json('i', '$.Adjudicacion.RutProveedor') }}                as rut_proveedor,
    {{ texto_json('i', '$.Adjudicacion.NombreProveedor') }}             as proveedor,
    {{ num_json('i', '$.Adjudicacion.Cantidad') }}
        * {{ num_json('i', '$.Adjudicacion.MontoUnitario') }}           as monto_adjudicado
from items
