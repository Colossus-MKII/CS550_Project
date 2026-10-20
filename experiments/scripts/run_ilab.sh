#!/usr/bin/env bash
# Run manually AFTER obtaining authorized GPU access. No SSH or Slurm submission.
set -euo pipefail
experiment_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$experiment_dir"
python_bin="${CS550_PYTHON:-$experiment_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
    printf '%s\n' 'Create the Linux environment first, or set CS550_PYTHON.' >&2
    exit 1
fi
exec "$python_bin" -m tracking_lab.run "$@"
