#!/bin/sh
set -eu

: "${MB_DB_HOST:?Set the private PostgreSQL host}"
: "${MB_DB_DBNAME:?Set the Metabase application database name}"
: "${MB_DB_USER:?Set the Metabase application database user}"
: "${MB_DB_PASS:?Set the Metabase application database password}"

export MB_DB_TYPE=postgres
export MB_JETTY_PORT="${PORT:-3000}"
export MB_SITE_NAME="Practice Planner Analytics"
export MB_LOAD_SAMPLE_CONTENT=false
export MB_ANON_TRACKING_ENABLED=false
export MB_AI_FEATURES_ENABLED=false
export MB_CHECK_FOR_UPDATES=false
export MB_ENABLE_PUBLIC_SHARING=false
unset MB_ENABLE_EMBEDDING
export MB_ENABLE_EMBEDDING_SDK=false
export MB_ENABLE_EMBEDDING_SIMPLE=false
export MB_ENABLE_EMBEDDING_INTERACTIVE=false
export MB_ENABLE_EMBEDDING_STATIC=false
export JAVA_OPTS="${JAVA_OPTS:--Xms256m -Xmx1024m}"

exec /app/run_metabase.sh
