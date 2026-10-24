{{ config(materialized="table") }}
-- Ítems de las licitaciones recién publicadas (mismo tipado que stg_detalle_items).
-- Fuente: Dirección ChileCompra.
{{ sql_detalle_items('detalle_publicacion') }}
