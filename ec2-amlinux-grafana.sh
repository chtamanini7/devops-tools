#!/bin/bash
set -euo pipefail

GRAFANA_VERSION="12.1.0"
GRAFANA_TARBALL="grafana-${GRAFANA_VERSION}.linux-amd64.tar.gz"
GRAFANA_URL="https://dl.grafana.com/oss/release/${GRAFANA_TARBALL}"
INSTALL_DIR="/opt/grafana"
SERVICE_FILE="/etc/systemd/system/grafana.service"

echo "==> Updating OS and installing dependencies"
dnf -y update
dnf -y install wget

echo "==> Creating grafana system user (if missing)"
id grafana &>/dev/null || useradd --system --home-dir "${INSTALL_DIR}" --shell /sbin/nologin grafana

echo "==> Removing any previous Grafana install"
systemctl stop grafana 2>/dev/null || true
rm -rf "${INSTALL_DIR}" /opt/grafana-* /opt/"${GRAFANA_TARBALL}" || true

echo "==> Downloading Grafana ${GRAFANA_VERSION}"
cd /opt
wget -q "${GRAFANA_URL}"

echo "==> Extracting Grafana"
tar -zxf "${GRAFANA_TARBALL}"
EXTRACTED_DIR="$(tar -tzf "${GRAFANA_TARBALL}" | head -1 | cut -d/ -f1 || true)"
if [[ -z "${EXTRACTED_DIR}" ]]; then
  echo "ERROR: Could not detect extracted dir from tarball"
  exit 1
fi
mv "${EXTRACTED_DIR}" "${INSTALL_DIR}"

echo "==> Setting ownership and permissions"
chown -R grafana:grafana "${INSTALL_DIR}"
chmod -R 755 "${INSTALL_DIR}"
chmod +x "${INSTALL_DIR}/bin/grafana-server"
touch "${INSTALL_DIR}/conf/custom.ini"
chown grafana:grafana "${INSTALL_DIR}/conf/custom.ini"

echo "==> Creating systemd service"
cat > "${SERVICE_FILE}" <<'SERVICE_UNIT'
[Unit]
Description=Grafana
After=network-online.target
Wants=network-online.target

[Service]
User=grafana
Group=grafana
Type=simple
WorkingDirectory=/opt/grafana
ExecStart=/opt/grafana/bin/grafana-server --homepath=/opt/grafana
Restart=on-failure
RestartSec=5
LimitNOFILE=10000
Environment="GF_PATHS_CONFIG=/opt/grafana/conf/custom.ini"
Environment="GF_PATHS_DATA=/opt/grafana/data"
Environment="GF_PATHS_LOGS=/opt/grafana/logs"
Environment="GF_PATHS_PLUGINS=/opt/grafana/plugins"

[Install]
WantedBy=multi-user.target
SERVICE_UNIT

echo "==> Enabling and starting Grafana"
systemctl daemon-reload
systemctl enable --now grafana

echo "==> Sanity checks"
systemctl status grafana --no-pager || true
wget -qSO- http://127.0.0.1:3000 >/dev/null && echo "Grafana responds" || echo "No response"

echo "==> Done."
