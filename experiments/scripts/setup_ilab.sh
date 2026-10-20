#!/usr/bin/env bash
# Environment setup only; run manually on Linux. Does not request a GPU or run jobs.
set -euo pipefail
experiment_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$experiment_dir"
python_bin="${CS550_BOOTSTRAP_PYTHON:-python3.12}"
if [[ ! -d .venv ]]; then
    "$python_bin" -m venv .venv
fi
.venv/bin/python -m pip install 'torch==2.7.1' 'torchvision==0.22.1' --index-url "${CS550_TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"
.venv/bin/python -m pip install -r requirements-runtime.txt
SAM2_BUILD_CUDA=0 .venv/bin/python -m pip install 'https://github.com/facebookresearch/sam2/archive/2b90b9f5ceec907a1c18123530e92e794ad901a4.zip'
.venv/bin/python -m pip install --no-deps -e .
if [[ ! -d external/TrackEval ]]; then
    git clone https://github.com/JonathonLuiten/TrackEval.git external/TrackEval
fi
git -C external/TrackEval checkout --detach 12c8791b303e0a0b50f753af204249e622d0281a
printf '%s\n' 'Setup finished. Run scripts/run_ilab.sh --check inside an authorized GPU allocation.'
