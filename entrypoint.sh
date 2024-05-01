#!/bin/bash
set -e

# Shellcheck source=runtime/functions
source "${GAME_HOME}/functions"

[[ ${DEBUG} == true ]] && set -x

########################################
# POSTGRES & MINIO: prepare
########################################
create_datadir
create_certdir
create_logdir
create_rundir

########################################
# POSTGRES: launch
########################################
set_resolvconf_perms

configure_postgresql

echo "Starting PostgreSQL ${PG_VERSION}..."
exec start-stop-daemon --start --chuid "${PG_USER}:${PG_USER}" --exec "${PG_BINDIR}/postgres" -- -D "${PG_DATADIR}" &

########################################
# MINIO: launch
########################################
echo "Starting MINIO ${MINIO_RELEASE}..."
if [ ! -z ${MINIO_CERTDIR} ]; then
  MINIO_CERT_COMAND="--certs-dir ${MINIO_CERTDIR}"
fi
exec start-stop-daemon --start --chuid "${MINIO_USER}:${MINIO_USER}" --exec "${MINIO_BINARY}" -- server ${MINIO_DATADIR} --console-address ":9001" ${MINIO_CERT_COMAND} &

if [ "${START_SERVICES}" = "true" ]; then
  # ########################################
  # # Game Master: launch
  # ########################################
  echo "Starting Bots..."
  exec start-stop-daemon --start --chuid "${BOT_MASTER_USER}:${BOT_MASTER_USER}"   --exec "${GAME_HOME}/box-bot" -- master_bot  1 &
  exec start-stop-daemon --start --chuid "${BOT_COLOR_USER}:${BOT_COLOR_USER}"     --exec "${GAME_HOME}/box-bot" -- color_bot   1 &
  exec start-stop-daemon --start --chuid "${BOT_DOORS_USER}:${BOT_DOORS_USER}"     --exec "${GAME_HOME}/box-bot" -- doors_bot   1 &
  exec start-stop-daemon --start --chuid "${BOT_GOSSIP_USER}:${BOT_GOSSIP_USER}"   --exec "${GAME_HOME}/box-bot" -- gossip_bot  1 &
  exec start-stop-daemon --start --chuid "${BOT_HERO_USER}:${BOT_HERO_USER}"       --exec "${GAME_HOME}/box-bot" -- hero_bot    1 &
  exec start-stop-daemon --start --chuid "${BOT_STAFF_USER}:${BOT_STAFF_USER}"     --exec "${GAME_HOME}/box-bot" -- staff_bot   1 &
  exec start-stop-daemon --start --chuid "${BOT_STATION_USER}:${BOT_STATION_USER}" --exec "${GAME_HOME}/box-bot" -- station_bot 1 &
fi

while :; do
  sleep 100
  echo 'Main process is still alive!'
done