{{ config(materialized="table") }}
-- Ver la macro sql_detalle_tipado (compartida con las licitaciones recién publicadas).
{{ sql_detalle_tipado('detalle') }}
