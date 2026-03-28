#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="${REPO_ROOT}/tools"
BIN_DIR="${TOOLS_DIR}/bin"
PLANTUML_DIR="${TOOLS_DIR}/plantuml"
DRAWIO_DIR="${TOOLS_DIR}/drawio"
PYTHON_DIAGRAM_TOOLS_DIR="${TOOLS_DIR}/python-diagram-tools"

PLANTUML_VERSION="${PLANTUML_VERSION:-1.2026.2}"
DRAWIO_VERSION="${DRAWIO_VERSION:-24.7.17}"
PYDEPS_SPEC="${PYDEPS_SPEC:-pydeps}"
PYLINT_SPEC="${PYLINT_SPEC:-pylint}"

SKIP_SYSTEM_PACKAGES=0
SKIP_DRAWIO=0

usage() {
  cat <<EOF
Usage: ./setup.sh [options]

Options:
  --skip-system-packages   Skip apt/dnf package installation
  --skip-drawio            Skip draw.io AppImage download
  -h, --help               Show this help text

Environment overrides:
  PLANTUML_VERSION         PlantUML jar version  (default: ${PLANTUML_VERSION})
  DRAWIO_VERSION           draw.io version       (default: ${DRAWIO_VERSION})
  PYDEPS_SPEC              pydeps pip spec       (default: ${PYDEPS_SPEC})
  PYLINT_SPEC              pylint pip spec       (default: ${PYLINT_SPEC})
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-system-packages)
      SKIP_SYSTEM_PACKAGES=1
      ;;
    --skip-drawio)
      SKIP_DRAWIO=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi
  echo "Need root privileges for: $*" >&2
  exit 1
}

find_system_dot() {
  local entry
  local candidate
  local real_entry

  IFS=':' read -r -a path_entries <<< "${PATH}"
  for entry in "${path_entries[@]}"; do
    [[ -n "${entry}" ]] || continue
    real_entry="$(cd "${entry}" 2>/dev/null && pwd -P)" || continue
    [[ "${real_entry}" == "${BIN_DIR}" ]] && continue
    candidate="${real_entry}/dot"
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

install_system_packages() {
  if [[ "${SKIP_SYSTEM_PACKAGES}" -eq 1 ]]; then
    echo "[setup] Skipping system package installation (--skip-system-packages)."
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    echo "[setup] Installing shared architecture tooling via dnf..."
    run_root dnf install -y \
      curl \
      git \
      graphviz \
      python3 \
      python3-pip \
      java-21-openjdk-headless \
      inkscape
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "[setup] Installing shared architecture tooling via apt-get..."
    run_root apt-get update
    run_root apt-get install -y \
      curl \
      git \
      graphviz \
      python3 \
      python3-pip \
      python3-venv \
      default-jre-headless \
      inkscape
    return
  fi

  echo "[setup] No supported package manager (dnf/apt-get) detected." >&2
  echo "[setup] Install curl, git, graphviz, python3, pip, java, and inkscape manually." >&2
}

install_plantuml() {
  command -v java >/dev/null 2>&1 || {
    echo "[setup] java is required for PlantUML. Install a JRE first." >&2
    exit 1
  }
  mkdir -p "${PLANTUML_DIR}" "${BIN_DIR}"
  local jar_path="${PLANTUML_DIR}/plantuml.jar"
  local jar_url="https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar"

  if [[ -f "${jar_path}" ]]; then
    echo "[setup] PlantUML jar already present: ${jar_path}"
  else
    echo "[setup] Downloading PlantUML ${PLANTUML_VERSION}..."
    curl -fL --retry 3 --retry-delay 2 -o "${jar_path}" "${jar_url}"
  fi

  cat > "${BIN_DIR}/plantuml" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR:$PATH"
exec java -jar "$DIR/../plantuml/plantuml.jar" "$@"
WRAPPER
  chmod +x "${BIN_DIR}/plantuml"
  echo "[setup] PlantUML wrapper: ${BIN_DIR}/plantuml"
}

install_graphviz_wrapper() {
  mkdir -p "${BIN_DIR}"
  local dot_path=""
  if dot_path="$(find_system_dot 2>/dev/null)"; then
    cat > "${BIN_DIR}/dot" <<WRAPPER
#!/usr/bin/env bash
set -euo pipefail
exec "${dot_path}" "\$@"
WRAPPER
    chmod +x "${BIN_DIR}/dot"
    echo "[setup] Graphviz dot wrapper: ${BIN_DIR}/dot -> ${dot_path}"
    return
  fi

  echo "[setup] Graphviz dot was not found on PATH."
  echo "[setup] Starter PlantUML diagrams still render via Smetana, but richer PlantUML diagrams may need Graphviz."
}

install_python_diagram_tools() {
  command -v python3 >/dev/null 2>&1 || {
    echo "[setup] python3 is required for pydeps and pyreverse." >&2
    exit 1
  }

  mkdir -p "${BIN_DIR}"
  if [[ ! -x "${PYTHON_DIAGRAM_TOOLS_DIR}/bin/python" ]]; then
    echo "[setup] Creating Python diagram-tool virtual environment..."
    python3 -m venv "${PYTHON_DIAGRAM_TOOLS_DIR}"
  fi

  echo "[setup] Installing Python diagram tools (${PYDEPS_SPEC}, ${PYLINT_SPEC})..."
  "${PYTHON_DIAGRAM_TOOLS_DIR}/bin/python" -m pip install --upgrade pip
  "${PYTHON_DIAGRAM_TOOLS_DIR}/bin/python" -m pip install "${PYDEPS_SPEC}" "${PYLINT_SPEC}"

  cat > "${BIN_DIR}/pydeps" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR:$PATH"
if [[ -x "$DIR/../python-diagram-tools/bin/pydeps" ]]; then
  exec "$DIR/../python-diagram-tools/bin/pydeps" "$@"
fi
exec pydeps "$@"
WRAPPER
  chmod +x "${BIN_DIR}/pydeps"

  cat > "${BIN_DIR}/pyreverse" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR:$PATH"
if [[ -x "$DIR/../python-diagram-tools/bin/pyreverse" ]]; then
  exec "$DIR/../python-diagram-tools/bin/pyreverse" "$@"
fi
exec pyreverse "$@"
WRAPPER
  chmod +x "${BIN_DIR}/pyreverse"

  echo "[setup] pydeps wrapper: ${BIN_DIR}/pydeps"
  echo "[setup] pyreverse wrapper: ${BIN_DIR}/pyreverse"
}

install_drawio() {
  if [[ "${SKIP_DRAWIO}" -eq 1 ]]; then
    echo "[setup] Skipping draw.io download (--skip-drawio)."
    return
  fi

  local arch
  arch="$(uname -m)"
  if [[ "${arch}" != "x86_64" ]]; then
    echo "[setup] draw.io AppImage auto-install currently supports x86_64 only." >&2
    echo "[setup] Skipping draw.io download for architecture: ${arch}" >&2
    return
  fi

  mkdir -p "${DRAWIO_DIR}" "${BIN_DIR}"
  local appimage_path="${DRAWIO_DIR}/drawio.AppImage"
  local drawio_url="https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-x86_64-${DRAWIO_VERSION}.AppImage"

  if [[ -f "${appimage_path}" ]]; then
    echo "[setup] draw.io AppImage already present: ${appimage_path}"
  else
    echo "[setup] Downloading draw.io desktop ${DRAWIO_VERSION}..."
    curl -fL --retry 3 --retry-delay 2 -o "${appimage_path}" "${drawio_url}"
    chmod +x "${appimage_path}"
  fi

  local extracted="${DRAWIO_DIR}/squashfs-root"
  if [[ ! -d "${extracted}" ]]; then
    echo "[setup] Extracting draw.io AppImage (avoids FUSE requirement)..."
    (
      cd "${DRAWIO_DIR}"
      "${appimage_path}" --appimage-extract >/dev/null
    )
  else
    echo "[setup] draw.io already extracted: ${extracted}"
  fi

  cat > "${BIN_DIR}/drawio" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/../drawio/squashfs-root/drawio" --no-sandbox "$@"
WRAPPER
  chmod +x "${BIN_DIR}/drawio"
  echo "[setup] draw.io wrapper: ${BIN_DIR}/drawio"
}

print_summary() {
  cat <<EOF
[setup] Complete.
[setup] Add local tools to PATH for this shell:
  export PATH="${BIN_DIR}:\$PATH"
[setup] Install the editable Python package if needed:
  python3 -m pip install -e .

[setup] Architecture authoring paths:
  - deterministic starter generation: archility generate /path/to/repository
  - deterministic Python sidecar diagrams for package/module repos: archility render /path/to/repository
  - agent-authored repo architecture: write repo-specific diagrams/docs, then render them here
[setup] Graphviz-backed PlantUML diagrams are supported when dot is available.
[setup] Starter repo-architecture diagrams still render without Graphviz via Smetana.
[setup] pydeps and pyreverse are installed into a local tool venv and exposed through tools/bin/.

[setup] Render diagrams through archility:
  archility render /path/to/repository
  PYTHONPATH=src python3 -m archility render /path/to/repository
EOF
}

install_system_packages
install_plantuml
install_graphviz_wrapper
install_python_diagram_tools
install_drawio
print_summary
