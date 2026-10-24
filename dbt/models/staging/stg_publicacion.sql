{{ config(materialized="table") }}
-- Detalle de las licitaciones tal como estaban AL PUBLICARSE (data/raw/detalle_publicacion),
-- con el mismo tipado que stg_detalle. Insumo de la puntuación diaria y del monitoreo.
-- Fuente: Dirección ChileCompra.
{{ sql_detalle_tipado('detalle_publicacion') }}
