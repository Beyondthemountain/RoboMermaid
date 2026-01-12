#!/usr/bin/env bash
set -euo pipefail

echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r scripts/requirements.txt

echo "Generating Mermaid diagrams from YAML..."
python scripts/generate_diagrams.py --model models/system.yaml --out diagrams

echo "Rendering Mermaid diagrams to SVG..."
find diagrams -name "*.mmd" -print0 | while IFS= read -r -d '' file; do
  out="${file%.mmd}.svg"
  echo "  Rendering $file -> $out"
  npx -y @mermaid-js/mermaid-cli -i "$file" -o "$out"
done

echo "Diagram build complete."
