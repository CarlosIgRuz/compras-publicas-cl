{{ config(materialized="table") }}
-- Ver la macro sql_detalle_items (compartida con las licitaciones recién publicadas).
{{ sql_detalle_items('detalle') }}
