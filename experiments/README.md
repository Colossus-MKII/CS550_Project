# CS550 实验工作区

这里是实际实验的独立工作区，供本地开发和后续 iLab Linux 运行使用。推理、数据准备、评分和可视化都在本目录，不依赖 `learning/`、教学网站端口或时间戳目录。学习网站只读取已经完成的结果。

本地四组历史保留／重置预实验已经加入，入口是 `tracking_lab/recovery.py`，详见 [恢复实验导读](RECOVERY_GUIDE.md)。它使用现有检测缓存，在各自相同前史上比较 A-H/A-R、B-H/B-R，固定模型权重、目标编号和后续输入；不会启动新网站。

**长窗口批次：**骑手／猫的30步跟随、ByteTrack真实匹配日志，以及SAM跳过一次指定目标刷新，见 [长窗口实验与代码导读](LONG_WINDOW_GUIDE.md)。8／20／30步统计来自同一份预测，不是三个独立样本。主实验和刷新消融分开报告。

**16段独立开发事件：**已按v3审阅清单完成128个主分支（16段×两种框×四组），2967边界案例未运行。64个ByteTrack分支独立CPU重放一致；预先选定的E09/E13另做16个GPU验证分支，逐项复现，不作新样本。实验入口、状态含义及读数规则见 [批次代码导读](RECOVERY_COHORT_GUIDE.txt)。原始数据、逐帧预测、评分与视频保留在本地忽略目录，不随源码提交。正式保留集评估尚未进行。

**基线修订：** `sam_io.py` 的同步保护现已进入正常 `sam_baseline.run_sam()`，不再只用于恢复实验。修正版为 `runs/stage1-20261017-sync-verified/`，另有完整推理复跑检查。旧 B0 周期提示帧的 CPU 卸载竞争导致部分 mask 异常；旧结果保留供追溯，不再用它们证明记忆漂移。网站默认展示修正版评分、视频与分析。恢复导读保留了候选草案及其当时状态；骑手和猫事件的后续运行请看上方最新导读。

## 目录

```text
experiments/
  tracking_lab/          Python 包：数据、A0/B0、评估、报告
    defaults/            实验配置、视频清单、权重指纹
  tests/                 实验自身的单元与迁移测试
  scripts/               本地与 Linux 手动运行入口
  pyproject.toml         可安装包与命令行入口
  requirements-*.txt     依赖版本
  CODE_GUIDE.md          中文代码导读
  data/stage1/           独立原图和 GT 副本，忽略 Git
  checkpoints/           两个已校验模型，忽略 Git
  external/TrackEval/    固定版本评分器，忽略 Git
  runs/                  新实验的输出，忽略 Git
```

目前已复制完整五段、207 帧输入及两份权重到本目录。原网站样本和此前实验存档没有移动或覆盖。26.43 GiB 原始压缩包仍在项目公共数据目录，跑当前五段实验不需要携带整个压缩包。

## Windows 本地运行

使用现有项目环境，在仓库根目录安装一次实验包：

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\experiments
.\experiments\scripts\run_local.ps1 --check
.\experiments\scripts\run_local.ps1 --output runs/stage1-local
```

脚本会切换到 `experiments/`，先选择本目录环境，否则使用已有项目 `.venv`。已有输出目录会被拒绝，不覆盖旧结果。`--check` 只检查 GPU、输入、权重、版本和评分器，不运行模型。

也可激活相应 Python 环境，进入 `experiments/` 后直接运行：

```text
python -m tracking_lab.run --check
python -m tracking_lab.run --output runs/stage1-local
python -m tracking_lab.report --output runs/stage1-local
python -m tracking_lab.verify --output runs/stage1-local --write-record
python -m pytest tests -q
```

命令行别名为 `cs550-run`、`cs550-report`、`cs550-verify`、`cs550-prepare`。普通推理、报告和评分不会启动 Web 服务；展示结果仍使用原来的学习网站。

## VS Code 运行和单步调试

用 VS Code **打开本目录 `experiments/`**，不是只打开一个 Python 文件。
`.vscode/` 已配置 Python、Python Debugger 和 Pylance 扩展推荐、pytest 测试入口，以及两个运行配置。
本机解释器使用上一级项目的 `.venv/Scripts/python.exe`，设置中采用完整路径，避免环境扩展在带 `../` 的路径与实际路径之间重复切换；没有新建或替换环境。

若窗口显示 **Restricted Mode**，需要你本人确认信任此目录后，Python 扩展与调试配置才能启用；本次没有替你修改工作区信任或执行策略。

1. 打开 `tracking_lab/run.py`，左侧“运行和调试”（`Ctrl+Shift+D`）选择 **Stage 1: run / step through A0 + B0**。
2. `F5` 启动调试，自动停在入口；`F10` 单步跳过、`F11` 进入函数、`Shift+F11` 返回、`F5` 继续、`Shift+F5` 停止。点击行号左边或按 `F9` 设置断点；建议先在 `execute()` 内的配置读取处设一个。
3. `Ctrl+F5` 使用同一配置直接运行，不停在入口或断点。输出自动放入新的 `runs/stage1-时间-随机后缀/`，不覆盖旧实验。这里只执行推理和评分，不自动生成报告、更新网站或启动服务。
4. 只检查环境时，选择 **Stage 1: preflight only (no model inference)**；也可按 `Ctrl+Shift+B` 执行预检任务。

运行配置用 `module: tracking_lab.run`，等价于 `python -m tracking_lab.run`，确保包内相对导入正确。**不要使用编辑器右上角的 “Run Python File”** 直接执行 `run.py`。
日志显示在 **Debug Console（调试控制台）**，不需要终端激活脚本。默认 `justMyCode: true`，单步主要进入我们自己的代码；若需深入 PyTorch、Ultralytics 或 SAM 源码，可在 `launch.json` 中改成 `false`。

如果状态栏曾手动选择过其他环境，执行命令面板 **Python: Select Interpreter → Enter interpreter path**，选择项目 `.venv/Scripts/python.exe`。调试配置和任务在 Windows 下显式使用该环境，不受旧选择影响。迁移到 Linux 时，在 VS Code 中重新选择该机器新建的 `.venv/bin/python`；当前 `settings.json` 的默认路径是本机 Windows 设置，不能照搬解释器环境。

调试字段与模块运行方式参考 [VS Code Python 调试文档](https://code.visualstudio.com/docs/python/debugging)。

## 后续迁移到 iLab

迁移单位是本目录，而不是教学网站。由用户在允许的开发协作流程中传输源码、独立输入和权重；不要搬运 Windows `.venv`、`.cache` 或已有大批 `runs`。本次未连接学校服务器、未上传任何文件、未申请或提交 Slurm 任务。

在 Linux 上创建新环境，默认 Python 3.12：

```bash
cd /your/path/experiments
bash scripts/setup_ilab.sh
# 先通过学校当前允许的方式获得 GPU，再执行：
bash scripts/run_ilab.sh --check
bash scripts/run_ilab.sh --output runs/stage1-ilab
.venv/bin/python -m tracking_lab.report --output runs/stage1-ilab
.venv/bin/python -m tracking_lab.verify --output runs/stage1-ilab --write-record
```

安装脚本固定 SAM 与 TrackEval 的源码版本，单独安装 CUDA 版 PyTorch，不自动选择账户、分区或提交作业。Linux 环境尚未在学校机器实测，驱动、CUDA 和机型是否兼容必须先通过预检及短实验确认。`CS550_BOOTSTRAP_PYTHON` 可指定已有 Python 3.12；`CS550_PYTHON` 可指定运行环境。若学校 GPU 需要不同的 PyTorch/CUDA 组合，应显式调整安装步骤并保留版本记录，不能覆盖记录后继续冒充同一环境。

代码不再限制显卡名称必须包含 3080；要求 CUDA 和当前协议的 BF16 支持。使用 `--device cuda:0` 指向作业可见的逻辑 GPU，尊重调度器的 `CUDA_VISIBLE_DEVICES`，不自行选择未分配的物理卡。

## 路径与数据迁移

所有资源都能显式指定，默认位于本目录：

```text
python -m tracking_lab.run --data-root /data/prepared/stage1 --weights-dir /models/checkpoints --trackeval-root /tools/TrackEval --device cuda:0 --output /results/stage1
```

`--config`、`--selection`、`--weight-manifest` 同样可替换。`CS550_EXPERIMENT_HOME` 可以整体改变默认工作区。默认配置与选择清单作为包资源一起安装，不需要项目外部的文件。

新结果同时记录原始数据位置和结果目录相对位置。搬迁结果后可指定数据根目录，不必修改历史 `summary.json`：

```text
python -m tracking_lab.report --output /results/stage1 --data-root /data/prepared/stage1
python -m tracking_lab.verify --output /results/stage1 --data-root /data/prepared/stage1 --trackeval-root /tools/TrackEval
```

评分验证默认只读；指定 `--write-record` 才写入 `verification.json`。当前数据导出、mask 语义、帧单位以及基线定义见 [代码导读](CODE_GUIDE.md)。源码可纳入版本控制，数据、权重、第三方 checkout 和结果继续被忽略；本次没有 Git 提交或推送。
