#!/usr/bin/env bash
# Sobe o servidor de desenvolvimento do SGR com o venv correto (.venv).
# Uso:  ./run.sh            -> roda em 127.0.0.1:8000
#       ./run.sh 0.0.0.0:9000  -> roda no host:porta informado
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/activate" ]; then
  echo "ERRO: venv não encontrado em .venv/ — crie com: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

ADDR="${1:-127.0.0.1:8000}"
echo "==> SGR rodando em http://${ADDR}/estoque/  (login: almox / demo12345)"
exec python manage.py runserver "${ADDR}"
