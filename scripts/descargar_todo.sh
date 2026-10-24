#!/usr/bin/env bash
# Lanza todas las descargas y scrapers en paralelo, desacoplados de la terminal.
#
#   setsid nohup scripts/descargar_todo.sh > data/logs/descargar_todo.log 2>&1 &
#
# Cada descargador es reanudable; se ejecuta dos veces para recoger lo que falló en la
# primera pasada (caídas de red puntuales). Los scrapers esperan solos a que vuelva la red.
set -u
cd "$(dirname "$0")/.."
mkdir -p data/logs

dos_pasadas() {
    local nombre=$1; shift
    for pasada in 1 2; do
        echo "$(date -Is) $nombre pasada $pasada"
        uv run tasacion "$@" >> "data/logs/$nombre.log" 2>&1
    done
}

dos_pasadas catastro descargar catastro --workers 4 &
dos_pasadas boe descargar boe &
( dos_pasadas boe_subastas descargar boe-subastas ) &
( uv run tasacion scrapear fotocasa >> data/logs/fotocasa.log 2>&1 ) &
( uv run tasacion scrapear pisoscom listados >> data/logs/pisoscom_listados.log 2>&1
  uv run tasacion scrapear pisoscom fichas >> data/logs/pisoscom_fichas.log 2>&1 ) &

wait
echo "$(date -Is) todo terminado"
