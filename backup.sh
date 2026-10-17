#!/usr/bin/env bash
# Respaldo de la base de datos y de los estudios adjuntos (HU-27).
# Uso manual:   ./backup.sh
# Uso automático (diario a las 3am), agregando esta línea con `crontab -e`:
#   0 3 * * * cd /Users/valentinsantamaria/Consultorio3 && ./backup.sh >> backups/backup.log 2>&1

set -euo pipefail
cd "$(dirname "$0")"

DB_NAME="${DB_NAME:-consultorio}"
DB_USER="${DB_USER:-valentinsantamaria}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
export PGPASSWORD="${DB_PASSWORD:-}"

BACKUP_DIR="backups"
RETENTION_DIAS="${BACKUP_RETENTION_DIAS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "[$TIMESTAMP] Respaldando base de datos '$DB_NAME'..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c \
  -f "$BACKUP_DIR/db_${TIMESTAMP}.dump"

if [ -d "uploads/estudios" ] && [ -n "$(ls -A uploads/estudios 2>/dev/null)" ]; then
  echo "[$TIMESTAMP] Respaldando estudios adjuntos..."
  tar -czf "$BACKUP_DIR/estudios_${TIMESTAMP}.tar.gz" -C uploads estudios
else
  echo "[$TIMESTAMP] No hay estudios adjuntos para respaldar todavía."
fi

echo "[$TIMESTAMP] Borrando respaldos de más de $RETENTION_DIAS días..."
find "$BACKUP_DIR" -type f \( -name "db_*.dump" -o -name "estudios_*.tar.gz" \) \
  -mtime "+${RETENTION_DIAS}" -delete

echo "[$TIMESTAMP] Listo. Respaldos guardados en $BACKUP_DIR/"
ls -lh "$BACKUP_DIR" | grep -E "db_${TIMESTAMP}|estudios_${TIMESTAMP}" || true
