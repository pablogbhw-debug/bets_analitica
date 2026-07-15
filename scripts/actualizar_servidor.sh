#!/usr/bin/env bash

# Actualiza el proyecto desde GitHub y reinicia Streamlit solo cuando corresponde.
set -Eeuo pipefail

SERVICIO="${SERVICIO:-apuestas}"
PUERTO="${PUERTO:-8501}"
RAMA="${RAMA:-}"

DIRECTORIO_SCRIPT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DIRECTORIO_PROYECTO="$(cd -- "${DIRECTORIO_SCRIPT}/.." && pwd)"
ENTORNO_VIRTUAL="${DIRECTORIO_PROYECTO}/.venv"
LOCK_FILE="/tmp/${SERVICIO}-actualizacion.lock"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fallar() {
    log "ERROR: $*"
    exit 1
}

mostrar_diagnostico() {
    log "Últimos mensajes del servicio ${SERVICIO}:"
    sudo journalctl -u "${SERVICIO}" -n 50 --no-pager || true
}

command -v git >/dev/null 2>&1 || fallar "Git no está instalado."
command -v systemctl >/dev/null 2>&1 || fallar "systemd no está disponible."
command -v curl >/dev/null 2>&1 || fallar "curl no está instalado."
command -v flock >/dev/null 2>&1 || fallar "flock no está instalado."

exec 9>"${LOCK_FILE}"
flock -n 9 || fallar "Ya existe otra actualización en ejecución."

cd "${DIRECTORIO_PROYECTO}"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fallar "La carpeta no es un repositorio Git."

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    git status --short
    fallar "Hay cambios locales rastreados. Confírmalos o descártalos antes de actualizar."
fi

if [[ -z "${RAMA}" ]]; then
    RAMA="$(git branch --show-current)"
fi
[[ -n "${RAMA}" ]] || fallar "No se pudo determinar la rama activa."

COMMIT_ANTERIOR="$(git rev-parse HEAD)"
log "Buscando actualizaciones de origin/${RAMA}..."
git fetch --prune origin "${RAMA}"

COMMIT_REMOTO="$(git rev-parse "origin/${RAMA}")"
if [[ "${COMMIT_ANTERIOR}" == "${COMMIT_REMOTO}" ]]; then
    log "El código ya está actualizado."
    if ! sudo systemctl is-active --quiet "${SERVICIO}"; then
        log "El servicio está detenido; iniciándolo..."
        sudo systemctl start "${SERVICIO}"
    fi
else
    log "Aplicando actualización con avance rápido..."
    git merge --ff-only "origin/${RAMA}"
    COMMIT_NUEVO="$(git rev-parse HEAD)"
    ARCHIVOS_CAMBIADOS="$(git diff --name-only "${COMMIT_ANTERIOR}" "${COMMIT_NUEVO}")"

    log "Archivos actualizados:"
    printf '%s\n' "${ARCHIVOS_CAMBIADOS}"

    if grep -qx 'requirements.txt' <<<"${ARCHIVOS_CAMBIADOS}"; then
        [[ -x "${ENTORNO_VIRTUAL}/bin/python" ]] || fallar "No existe el entorno virtual ${ENTORNO_VIRTUAL}."
        log "Instalando dependencias actualizadas..."
        "${ENTORNO_VIRTUAL}/bin/python" -m pip install -r requirements.txt
    fi

    if grep -Eq '(^app\.py$|^requirements\.txt$|^controllers/|^models/|^views/|\.py$)' <<<"${ARCHIVOS_CAMBIADOS}"; then
        log "Reiniciando ${SERVICIO}..."
        sudo systemctl restart "${SERVICIO}"
    else
        log "Solo cambiaron archivos que no requieren reiniciar ${SERVICIO}."
    fi
fi

if ! sudo systemctl is-active --quiet "${SERVICIO}"; then
    mostrar_diagnostico
    fallar "El servicio ${SERVICIO} no está activo."
fi

log "Esperando la respuesta de Streamlit..."
for intento in {1..15}; do
    if curl --fail --silent --show-error "http://127.0.0.1:${PUERTO}/_stcore/health" >/dev/null; then
        log "Actualización terminada: ${SERVICIO} está activo y Streamlit responde correctamente."
        exit 0
    fi
    sleep 2
done

mostrar_diagnostico
fallar "Streamlit no respondió en el puerto ${PUERTO}."
