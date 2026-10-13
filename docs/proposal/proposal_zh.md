# 面向多目标分割与跟踪的检测器微调研究

**Jingdi Wu, Yupu Guo, Christina Ross**  

Rutgers University · CS550 Massive Data Mining · 2026 年秋季  
修订版项目提案 · 2026 年 10 月 13 日  
中文审阅版，与英文修订稿逐节对应。

## 摘要

本项目将在固定的 YouTube-VIS 2021 子集上，比较 YOLO11s-seg 搭配 ByteTrack 与检测器辅助的 SAM 2.1。先建立预训练基线，再优先开展一项预算受限的 YOLO 微调研究，检验更好的检测结果能否改善后续分割和身份一致性。两套流程共用同一个微调后的检测器，SAM 始终冻结。我们将评估质量、速度和显存，不预设微调一定有效。

## 1 研究背景与问题

教学视频中观察到的一次类别误识别，是研究动机而非定量结论。我们研究两个问题：（RQ1）检测关联式跟踪与检测器辅助的掩码传播，在准确性和计算成本上有何差异？（RQ2）利用有限的目标领域数据微调 YOLO，能否改善检测和分割，这些改善又能否转化为两套流程的跟踪提升？更准确的观测不一定能解决遮挡后的身份恢复。项目贡献是可复现的实证研究，不是提出新架构，也不是开发语义推理式的身份重识别系统。

## 2 相关工作

YOLO11 输出实例掩码、检测框和类别，支持从预训练权重开始微调（Ultralytics, 2026）。ByteTrack 负责跨帧关联检测结果（Zhang et al., 2021），其关联算法不是本项目要训练的神经网络。SAM 2.1 利用视频记忆传播提示指定的掩码，但自动发现目标和获取类别仍依赖外部检测器（Meta AI, 2026）。HOTA 与 IDF1 从互补角度衡量跟踪质量（Luiten et al., 2020；Ristani et al., 2016）。

## 3 方法与微调实验

流程 A 每帧运行 YOLO11s-seg，使用它的掩码及 ByteTrack 的关联结果。我们将按类别分别运行 ByteTrack，并使用视频内唯一的目标编号，明确记录这一类别隔离版本。流程 B 使用同一个 YOLO 权重定期提供检测框提示和类别，由冻结的 SAM 2.1 Hiera Tiny 传播掩码。流程 B 不接收 ByteTrack 编号，也不使用真实标注作为提示。

| 实验组 | YOLO 权重 | 后续处理流程 |
| --- | --- | --- |
| A0 | 预训练 | ByteTrack + YOLO 掩码 |
| B0 | 预训练 | 冻结的 SAM 2.1 |
| A1 | 微调后 | ByteTrack + YOLO 掩码 |
| B1 | 与 A1 相同 | 冻结的 SAM 2.1 |

对于流程 B，定期检测得到的框与同类别传播掩码的外接框按 box IoU 进行一对一匹配。通过过滤但未匹配的检测建立新轨迹，匹配成功则刷新提示。空掩码不生成输出框，并将轨迹标为暂时丢失；保留轨迹的传播掩码再次出现时可以沿用原编号，否则未匹配的检测得到新编号。丢失轨迹保留时长、重复目标抑制和提示刷新规则在验证集上确定。不额外加入长期身份重识别模块。

完成 A0/B0 后，只微调一个 YOLO11s-seg 模型，使用有监督的实例分割损失，再将同一权重用于 A1/B1。A 同时使用 YOLO 的掩码和框，B 使用框及类别，因此两者获益可能不同。试运行后固定较小的训练预算：初步上限为输入尺寸 640、30 个训练轮次，批量大小根据实测显存确定。按验证集掩码 AP50:95 选择权重。记录抽帧、数据增强、优化器、随机种子以及输出头或类别空间的变化；若类别空间发生变化，就不能将效果解释为仅改变权重的纯消融实验。四组采用相同的目标类别映射。A0/A1 内以及 B0/B1 内保持检测阈值和后续处理规则不变，所有验证调参都在保留评估集测试之前完成。

## 4 数据集与实验控制

计划从 YouTube-VIS 2021 官方训练集选择 200 段带标注视频，覆盖人、狗、猫、马和汽车（Yang et al., 2021）。以随机种子 550 按完整视频划分为 120 段训练、40 段验证和 40 段保留评估视频。先划分视频，再从训练视频按时间间隔抽帧，保留每帧全部目标类别实例；可识别为同源的视频片段放在同一划分。调参前核验并固定文件、类别覆盖、帧清单、映射及任何缩减后的数量。以上是计划中的内部划分，不是官方挑战赛测试集；上游预训练数据是否重叠可能无法确认。

四组处理相同的有标注帧和时间顺序，采用共同的外部缩放策略，并记录模型特定预处理。预测掩码映射回原始标注坐标。训练标签转换后与原掩码核对；评估始终使用原始标注，包含中途进入及暂时消失的目标。保留评估集和教学视频都不参与训练、权重选择或调参。失败分析片段先根据标注选定，再查看模型结果。

## 5 评估与交付成果

主要指标为采用标准多阈值计算的掩码 HOTA，同时报告 DetA、AssA，以及 IoU 阈值 0.5 下的掩码 IDF1。统一且按类别匹配的 TrackEval 适配器还将在 mask IoU 0.5 下报告 CLEAR 误检、漏检和身份切换数（Luiten and Hoffhues, 2020）。各类别先按照指标官方规则合并视频结果，再对类别等权平均，保留逐视频结果用于诊断。先用完美预测、故意漏检和故意切换编号的小样例验证评分流程。

单独测量 YOLO 的框与掩码 AP50:95，并检查类别错误，以区分检测器变化和跟踪变化。对比 A1-A0 与 B1-B0，报告退步、无明确提升等结果，并分析遮挡、目标交叉及离开后返回的案例。结果是本项目的内部测量，不是官方排行榜成绩，也不以一段教学视频作为效果证据。A 与 B 比较的是完整系统，包括不同的检测调用频率，不能将差异全部归因于分割骨干模型。

在相同 GPU 和输入上报告峰值显存、检测器调用次数，以及预热后三次 GPU 同步运行的 FPS 中位数。计时包含从解码到最终掩码和编号的处理，不含模型加载、可视化和评分；训练 GPU 小时数单独报告。交付配置、数据划分清单、完整逐帧预测、训练日志、可行时的四组结果、同步对比视频及报告。

## 6 可行性与阶段安排

RTX 3080（10 GB）上的短视频推理已经验证，完整自动 SAM 跟踪与 YOLO 训练仍需试运行。学校实验遵守 Rutgers iLab 的访问和调度规则，不预设 GPU 必然可用。阶段依次为数据与评分检查、A0/B0、短时训练及验证试验、A1/B1、结果分析。数据和环境就绪后，估计基线与数据、评分准备需要 3-5 个工作日，微调试验及实验额外需要 2-4 日，报告整理需要 1-2 日，按试运行实测修正。两组预训练流程在整个保留评估集上的比较是最低交付；微调是优先扩展，若资源原因导致未完成，将如实记录。SAM/DeAOT 训练和额外流程不在本次范围内。项目成功不以指标一定提升为前提。

## 参考文献

Jonathon Luiten, Aljosa Osep, Patrick Dendorfer, Philip Torr, Andreas Geiger, Laura Leal-Taixe, and Bastian Leibe. 2020. [HOTA: A higher order metric for evaluating multi-object tracking](https://arxiv.org/abs/2009.07736). International Journal of Computer Vision.

Jonathon Luiten and Arne Hoffhues. 2020. [TrackEval](https://github.com/JonathonLuiten/TrackEval). Evaluation software.

Meta AI. 2026. [SAM 2: Inference, SAM 2.1 checkpoints, and training documentation](https://github.com/facebookresearch/sam2). Online documentation, accessed October 13, 2026.

Ergys Ristani, Francesco Solera, Roger Zou, Rita Cucchiara, and Carlo Tomasi. 2016. [Performance measures and a data set for multi-target, multi-camera tracking](https://arxiv.org/abs/1609.01775). ECCV Workshops.

Ultralytics. 2026. [YOLO11 instance segmentation and fine-tuning documentation, version 8.3.221](https://github.com/ultralytics/ultralytics/blob/v8.3.221/docs/en/tasks/segment.md). Online documentation, accessed October 13, 2026.

Linjie Yang, Yuchen Fan, Yang Fu, and Ning Xu. 2021. [The 3rd Large-scale Video Object Segmentation Challenge - video instance segmentation track](https://youtube-vos.org/dataset/vis/).

Yifu Zhang, Peize Sun, Yi Jiang, Dongdong Yu, Fucheng Weng, Zehuan Yuan, Ping Luo, Wenyu Liu, and Xinggang Wang. 2021. [ByteTrack: Multi-object tracking by associating every detection box](https://arxiv.org/abs/2110.06864). arXiv:2110.06864.
