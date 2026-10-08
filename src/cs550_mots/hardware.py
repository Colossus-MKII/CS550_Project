"""Hardware inspection without requiring or installing an ML stack."""

import importlib.util
import platform
import shutil
import subprocess
import sys


def hardware_report():
    report = {"python": sys.version.split()[0], "platform": platform.platform(),
              "machine": platform.machine(), "sam3_requires": {
                  "python": ">=3.12", "pytorch": ">=2.7", "cuda": ">=12.6",
                  "backend": "CUDA-compatible GPU (official setup)"}}
    smi = shutil.which("nvidia-smi")
    if smi:
        result = subprocess.run([smi, "--query-gpu=name,memory.total,driver_version",
                                 "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        report["nvidia_smi"] = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    else:
        report["nvidia_smi"] = "not found; no NVIDIA device verified"
    if importlib.util.find_spec("torch") is None:
        report["torch"] = "not installed"
        report["cuda_available"] = None
    else:
        import torch

        report["torch"] = torch.__version__
        report["torch_cuda_build"] = torch.version.cuda
        report["cuda_available"] = torch.cuda.is_available()
        report["cuda_devices"] = [
            {"name": torch.cuda.get_device_name(i),
             "total_vram_gib": torch.cuda.get_device_properties(i).total_memory / 2**30}
            for i in range(torch.cuda.device_count())
        ]
    report["training_feasibility"] = "unknown until a measured pilot; this probe is not a training benchmark"
    return report

