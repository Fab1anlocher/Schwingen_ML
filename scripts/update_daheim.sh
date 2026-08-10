#!/usr/bin/env bash
# Echtes ESV-Update vom Heimrechner (Wohn-IP umgeht die WAF-Sperre von esv.ch).
#
# Scrapt die ESV-Ranglisten mit echtem Browser, trainiert die Modelle neu und
# pusht die Artefakte -> Vercel deployt automatisch. Als geplanter Task
# einrichtbar (Linux/macOS: cron; Windows: Aufgabenplanung / WSL).
#
# Einmalig vorbereiten:
#   pip install -r requirements-pipeline.txt playwright
#   playwright install chromium
#
# Aufruf:
#   bash scripts/update_daheim.sh
set -euo pipefail
cd "$(dirname "$0")/.."

export SCHWINGEN_USE_BROWSER=1   # echten Browser für esv.ch nutzen (WAF/JS)

echo "==> ESV scrapen + Modelle trainieren ..."
python -m pipeline.run_pipeline --source esv

echo "==> Artefakte committen & pushen ..."
git add artifacts/ web/public/data/
if git diff --staged --quiet; then
  echo "Keine Änderungen — nichts zu tun."
else
  git commit -m "chore: ESV-Daten & Modelle aktualisiert ($(date -u +%Y-%m-%d))"
  git push
  echo "==> Fertig. Vercel deployt automatisch."
fi
