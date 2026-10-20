# 实验代码导读

本目录是独立实验工作区，包含数据准备、两套基线、GT 评分和错误可视化。已完成五段真实视频的本地 RTX 3080 预实验；同一份源码提供 Linux 运行入口，但学校环境尚未实测。整体目录与迁移步骤见 README.md。

四组对照见 [RECOVERY_GUIDE.md](RECOVERY_GUIDE.md)，从 `recovery.py → execute()` 开始。正常基线现也通过 `sam_io.synchronized_sam_offload()` 确保 CPU 读取前完成 mask 拷贝。网站默认展示 `runs/stage1-20261017-sync-verified/` 的修正版，旧存档保留；旧骑手／马提示帧异常不能继续解释为记忆失败。

## 先看结果，再按顺序读代码

统一入口为原学习网站的 `http://127.0.0.1:8765/cs550-tracking-lab/results.html`，英文为 `results.en.html`；主页首屏和侧栏均有“真实实验结果”。沿用学习网站的主题、导航和中英文切换，不再另起实验 Web 服务。指标、逐帧六格图、诊断表、IoU 曲线和完整视频均在同一站点内。

原始运行存档保留在 `outputs/pilot/stage1-20261017-3080-verified/`，其 `index.html` 也可直接离线打开。最初的 `stage1-20261017-3080` 发现了轨迹到 mask 的索引问题，已标记作废，不能引用其 A0 分数。

这些是重构前的历史存档，其中的源码快照仍保留原 `pilot` 命名。当前实际代码以本目录 `tracking_lab/` 为准，新结果写入本目录 `runs/`，不要从网页快照启动实验。

建议从 `run.py` 开始，按照其中编号追踪下面的文件。每个模块只承担一类职责：

| 文件 | 要回答的问题 | 关键入口 |
| --- | --- | --- |
| `dataset.py` | 原图与 GT 怎么读取，怎样保证不泄漏标注？ | `read_manifest`、`load_ground_truth` |
| `detector.py` | YOLO 每帧预测什么，输出怎么回到原图尺寸？ | `detect_video` |
| `bytetrack.py` | 检测框如何分配 ID，ID 如何对应正确的 mask？ | `DetectionBatch`、`run_bytetrack` |
| `sam_baseline.py` | SAM 如何传播、刷新提示、发现新目标和删除旧目标？ | `PNGFrames`、`propagate_one`、`run_sam` |
| `sam_io.py` | CPU 卸载后的 mask 何时才允许在 CPU 上读取？ | `synchronized_sam_offload` |
| `evaluate.py` | 如何把 mask 交给官方指标，而不是自行近似 HOTA？ | `similarity_data`、`evaluate_all`、`self_checks` |
| `diagnose.py` | 某一帧没跟好，检测、分割和身份各有什么证据？ | `diagnose` |
| `render.py`、`report.py` | 如何只根据已保存结果生成图和网页？ | `comparison`、`build` |
| `common.py` | 实例、坐标、IoU 和预测文件是什么结构？ | `Instance`、`mask_box`、`save_predictions` |
| `config.json` | 本轮具体用了哪些固定参数？ | 运行前读取，随结果保存 |

推理函数只接收 RGB 路径和检测缓存。`run.py` 等两套预测全部保存后才调用 `load_ground_truth`。自动系统不会获得 GT 框、GT 类别列表或 GT 身份通道；两个模型使用的是固定的五类白名单。

## 数据结构与坐标

输入来自已经完整审计的 SlotCurri 数组导出：五段视频为 2686、2744、2689、2718、2692，共 207 个导出帧，覆盖人、狗、猫、马、汽车。选取清单在 `tracking_lab/defaults/stage1_selection.json`，在评分前固定。这些视频用于开发，正式划分时应排除在保留评估集外。

实际输入默认位于独立的 `experiments/data/stage1/`，不再读取教学网站目录。读取无损 PNG：RGB 像素与数组一致，mask alpha 等于原始 `segmentations[t,:,:,channel] > 0`。这不是先前没有 GT 的教学狗视频，也没有将带框演示视频当作模型输入。原始压缩包和数组不修改。

- `Instance.mask`：原始导出尺寸的二维布尔数组。
- `Instance.box`：`[x1,y1,x2,y2]`，右／下边界不包含在框内。单个像素 `(x,y)` 的框是 `[x,y,x+1,y+1]`。
- GT 身份为 `channel+1`；预测身份由各自系统创建。数字不必与 GT 相等，指标会建立对应。
- NumPy 类别值、YOLO COCO 类别编号和实例 ID 不是一回事。适配层按类别名称对应，评分只保留五个研究类别。
- 原始 FPS、时间戳、源帧文件名缺失。`5` 步发现间隔、`15` 步 SAM 保留期、`30` 步 ByteTrack 保留期都是导出步数，不是秒。

## A0 怎样工作

`detector.py` 将 PNG 读取为 OpenCV BGR，交给冻结的 `yolo11s-seg.pt`。检测阈值 0.1，YOLO 输入尺寸 640，使用 `retina_masks=True`，输出 mask 必须与 GT 的原始尺寸一致，否则直接报错。类别、框、置信度和 mask 都来自同一次预测。

`bytetrack.py` 给五个类别各创建一个独立的官方 ByteTrack。每一帧，包括无检测的帧，都调用 `update`，使丢失计数正常推进。内部使用 Kalman 预测、两阶段置信度关联和轨迹管理；不训练、不生成新的像素轮廓。

轨迹输出与该帧 YOLO mask 必须一一对应。固定版本的 `init_track` 在高／低分筛选后重新产生索引，因此不能直接用它索引筛选前的 mask。`DetectionBatch` 在切片时保留原始索引，`IndexedBYTETracker` 只覆盖检测对象构造，将这个索引传入 `STrack`；其余 Kalman 和关联算法完全继承官方实现。高分筛选与低分二阶段各有回归测试。外部 ID 映射保证同一视频不同类别的 ID 不冲突。

ByteTrack 的 `frame_rate=30` 只是使上游 `frame_rate/30 * track_buffer` 不再缩放，从而让保留期等于 30 个导出步数，不是在宣称源视频为 30 fps。最终 mask 仍然是已关联的 YOLO mask；丢失轨迹的运动预测只记入诊断日志，不伪造分割输出。

## B0 怎样工作

SAM 不自动识别类别。B0 每隔 5 步读取同一个 YOLO 缓存中置信度至少 0.25 的框；其他帧由 SAM 2.1 Hiera Tiny 利用过去的状态传播掩码。

每帧按以下顺序处理：

1. 上次接受 YOLO 观测已超过 15 步的目标退出，删除对应 SAM 对象状态。
2. 对剩余目标仅向前传播到当前帧。`max_frame_num_to_track=0` 在固定版本中表示只处理起始这一帧，不是“不执行”。
3. 在发现帧，将同类别 YOLO 框与当前 SAM mask 的外接框做一对一匹配，box IoU 门限 0.3。空 mask 在保留期内使用最后一个框，不读取 GT。
4. 匹配成功则保留 ID、刷新框提示；未匹配的检测经过同类 box IoU 0.7 去重后创建新 ID。达到 32 个活动目标时明确报错，不静默截断。
5. 当前提示通过官方 preflight 编码进记忆，供后续帧使用。已经评分的过去帧不会回头更新。

为了让自动刷新帧稳定地保存为提示帧，显式设置 `add_all_frames_to_correct_as_cond=True`。保留已有历史，不清空记忆；这是记录在配置与结果中的基线选择，不是本轮已经做了记忆干预实验。

两边共享同一批 YOLO 数值结果，便于排查实现差异。A0 使用 207 帧的检测，B0 只使用各视频 0、5、10……处的检测。其余缓存检测仅用于离线诊断，不暗中提供给 B0。因此本轮缓存运行耗时不等于 B0 真正按需调用检测器的端到端耗时。

SAM 官方入口只接收 JPEG 文件夹／MP4。为了避免只有 SAM 输入被有损重编码，`PNGFrames` 复用官方单图缩放函数和相同归一化；仅在初始化期间适配图片加载入口，随后立即恢复。模型状态初始化、1024 内部输入尺寸、权重和传播算法不变，未修改 site-packages。帧按需加载到 CPU，视觉特征只按时间向前计算，并检查没有提前编码未来帧。这个初始化适配是单线程的，不应并发初始化。

SAM 使用 BF16 autocast，视频与状态卸载到 CPU；为跨平台保持相同后处理，两端均禁用可选 CUDA 连通域补洞（`fill_hole_area=0`）。YOLO 使用 FP32。这些设置都会记录，不能说两者内部精度、预处理或推理成本相同。

## 怎样评分和定位错误

`evaluate.py` 将每个视频、每个类别的稳定 GT / 预测 ID 映射成从 0 开始的内部索引，逐帧计算 mask IoU 矩阵，直接交给固定提交版本的官方 TrackEval。

- HOTA、DetA、AssA：平均 mask IoU 阈值 0.05、0.10……0.95 的结果。
- IDF1：mask IoU 门限 0.5，使用整段身份对应，不是每帧重新挑最好的 ID。
- FP、FN、IDSW：官方 CLEAR，mask IoU 门限 0.5。
- 聚合：先由官方方法合并同一类别各视频，再对五类等权平均质量分数；计数求和。保留逐视频、逐类别及全部阈值结果。

固定 TrackEval 版本使用旧的 `np.float` / `np.int` 名称，适配器仅在三个指标模块内映射到原始 Python 类型，不全局修改 NumPy、不修改官方源码和匹配公式。初始化会核验 Git 提交与本地源码未改动。

运行真实数据评分前先执行可解析自检：完美预测、一次漏检、一次 ID 切换、错类预测和空输出。比如同一目标四帧中前两帧 ID 1、后两帧 ID 2，定位完美，但 IDF1 为 0.5、AssA 为 0.5、HOTA 为 `sqrt(0.5)`。

`diagnose.py` 另做本帧的一对一检查：为每个可见 GT 记录最佳同类 mask IoU、匹配预测 ID、YOLO 框／mask IoU，以及 ID 变化标记。可见 GT 没有输出时 IoU 为 0。这些只是解释用的局部诊断，不能替代 HOTA 或 IDF1，局部匹配标记也不保证与官方 CLEAR 的 IDSW 逐项一致。

错误图用蓝色表示漏掉的 GT 前景，红色表示额外或错类前景，绿色表示同类别前景覆盖。它比较类别并集，同类实例之间的身份交换可能仍然是绿色，必须看 ID 与跟踪指标。诊断“有好 YOLO mask 但无匹配跟踪输出”只说明值得检查关联／确认／生命周期，不足以独自证明 Kalman 状态有错。

## 运行和复查

激活对应 Python 环境，进入 `experiments/` 后运行；Windows 与 Linux 使用相同模块入口：

~~~text
python -m tracking_lab.run --check
python -m tracking_lab.run --output runs/stage1-local
python -m tracking_lab.report --output runs/stage1-local
python -m tracking_lab.verify --output runs/stage1-local --write-record
python -m pytest tests -q
~~~

依赖记录在 `requirements-local.txt` 和 `requirements-runtime.txt`；模型默认来自本目录 `checkpoints/`，加载前核验包内 `defaults/checkpoints.json` 的 SHA-256，不自动下载模型。SAM 源码提交固定为 `2b90b9f5ceec907a1c18123530e92e794ad901a4`。

评分器位于被 Git 忽略的 `external/TrackEval`。新环境需先准备：

```powershell
git clone https://github.com/JonathonLuiten/TrackEval.git external/TrackEval
git -C external/TrackEval checkout --detach 12c8791b303e0a0b50f753af204249e622d0281a
```

每次运行保存：配置、版本、权重哈希、输入图和 GT 的逐文件哈希、实际推理源码快照、逐帧预测 JSON、无 pickle 的 mask NPZ、A0 状态日志、B0 发现／刷新／删除事件、原始官方指标和图像。`tracking_lab/report.py` 可独立重建报告，预测 mask 不会被覆盖。推理源码快照与后续工作区排版调整不混淆。

代码与小型选择清单可纳入版本控制；所有原图、GT、权重、第三方源码、运行结果和视频继续留在被忽略目录。本次没有 Git 提交／推送，也不对外发布或提交课程作业。

## 本阶段的边界

第一阶段完成标准是正确运行与可检查的证据链，不是证明 SAM 或 ByteTrack 的记忆更优。两套系统还同时区别于检测频率、关联和生命周期规则；五段开发视频也不足以支持最终排名。本轮没有进行 AP50:95 阈值扫描、三次暖机端到端 FPS 基准、事件恢复标准冻结或 A-H/A-R/B-H/B-R 干预；这些属于后续阶段。

## 主要实现来源

- [Ultralytics 固定版本 ByteTrack](https://github.com/ultralytics/ultralytics/blob/v8.3.221/ultralytics/trackers/byte_tracker.py)
- [SAM 固定版本视频预测器](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/sam2/sam2_video_predictor.py)
- [SAM 固定版本图像加载](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/sam2/utils/misc.py)
- [TrackEval 固定版本指标](https://github.com/JonathonLuiten/TrackEval/tree/12c8791b303e0a0b50f753af204249e622d0281a/trackeval/metrics)
