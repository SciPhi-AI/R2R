#!/bin/bash

set -e
echo 'Waiting for PostgreSQL to be ready...'
while ! pg_isready -h hatchet-postgres -p 5432 -U ${HATCHET_POSTGRES_USER:-hatchet_user}; do
  sleep 1
done

echo 'PostgreSQL is ready, checking if database exists...'
if ! PGPASSWORD=${HATCHET_POSTGRES_PASSWORD:-hatchet_password} psql -h hatchet-postgres -p 5432 -U ${HATCHET_POSTGRES_USER:-hatchet_user} -lqt | grep -qw ${HATCHET_POSTGRES_DBNAME:-hatchet}; then
  echo 'Database does not exist, creating it...'
  PGPASSWORD=${HATCHET_POSTGRES_PASSWORD:-hatchet_password} createdb -h hatchet-postgres -p 5432 -U ${HATCHET_POSTGRES_USER:-hatchet_user} -w ${HATCHET_POSTGRES_DBNAME:-hatchet}
else
  echo 'Database already exists, skipping creation.'
fi
