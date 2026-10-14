-- Listados diarios crudos (data/raw/licitaciones) tipados y sin filas repetidas.
-- Ojo: el listado de un día NO es "publicadas ese día": cada licitación aparece en el día de su
-- último evento según su estado al descargar (publicación, cierre, adjudicación). Ver DECISIONS.md.
-- La API a veces repite una licitación dentro del mismo día con milisegundos distintos en
-- FechaCierre: se deja una fila por (codigo, fecha_listado), la de FechaCierre más reciente.
-- Fuente: Dirección ChileCompra.
with crudo as (
    select *
    from read_json(
        '{{ var("raw_dir") }}/licitaciones/fecha=*.json.gz',
        format = 'array',
        filename = true,
        columns = {CodigoExterno: 'VARCHAR', Nombre: 'VARCHAR', CodigoEstado: 'INTEGER', FechaCierre: 'VARCHAR'}
    )
),

tipado as (
    select
        trim(CodigoExterno)                                              as codigo,
        trim(Nombre)                                                     as nombre,
        CodigoEstado                                                     as codigo_estado,
        {{ estado_licitacion('CodigoEstado') }}                          as estado,
        try_cast(FechaCierre as timestamp)                               as fecha_cierre,
        cast(regexp_extract(filename, 'fecha=([0-9-]{10})', 1) as date)  as fecha_listado,
        regexp_extract(CodigoExterno, '-([A-Z0-9]{2})[0-9]{2}$', 1)      as tipo
    from crudo
)

select *
from tipado
qualify row_number() over (partition by codigo, fecha_listado order by fecha_cierre desc nulls last) = 1
