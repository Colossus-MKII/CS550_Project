"""A selective history organized by bottlenecks, not a model leaderboard."""
from .study import link, pick, section, source


def content(language, home):
    t = lambda zh, en: pick(language, zh, en)
    pages = []

    def add(key, title, body):
        label = t(*title)
        pages.append((key, label, section(key, label, body)))

    def item(year, name, zh, en, *sources):
        return f'<h3>{year} · {name}</h3><p>{t(zh, en)}</p><p class="source-note">' + " · ".join(link(url, label) for url, label in sources) + '</p>'

    add("map", ("先看任务分支，而不是版本排名", "Start with task branches, not version rankings"), t(
        '<p>这些进展不是一条“传统方法 → YOLO → SAM，后者替代前者”的直线。分类、检测、分割、跨帧身份和开放概念识别解决不同问题，很多技术同时存在并相互组合。年份以下面标注的论文 / 发布版本为准，预印本与会议年份可能不同。</p>',
        '<p>This is not a linear replacement chain from classical methods to YOLO to SAM. Classification, detection, segmentation, identity association and open-concept recognition solve different tasks; techniques coexist and combine. Dates refer to the indicated paper or release; preprint and conference years can differ.</p>') +
        '<div class="table-wrap"><table><thead><tr><th>' + t("问题", "Question") + '</th><th>' + t("代表路线", "Representative path") + '</th><th>' + t("与本项目的联系", "Project connection") + '</th></tr></thead><tbody>' +
        '<tr><td>' + t("如何表示图像？", "How to represent images?") + '</td><td>SIFT / HOG → CNN → ResNet / ViT</td><td>' + t("特征如何获得不变性、语义与上下文。", "Invariance, semantics and context in features.") + '</td></tr>' +
        '<tr><td>' + t("哪些目标在哪里？", "Which objects, where?") + '</td><td>R-CNN / Faster R-CNN · YOLO · DETR</td><td>' + t("发现目标、类别、框与计算成本。", "Object discovery, classes, boxes and cost.") + '</td></tr>' +
        '<tr><td>' + t("哪些像素属于它？", "Which pixels belong to it?") + '</td><td>U-Net / Mask R-CNN · SAM</td><td>' + t("轮廓、提示条件与实例分离。", "Boundaries, prompt conditioning and instances.") + '</td></tr>' +
        '<tr><td>' + t("是不是刚才那个？", "Is it the same object?") + '</td><td>SORT / Deep SORT / ByteTrack · DeAOT / SAM 2</td><td>' + t("框关联与视觉记忆是不同的时间建模。", "Box association and visual memory model time differently.") + '</td></tr></tbody></table></div>' +
        '<p>' + link(f'math{".en" if language == "en" else ""}.html', t("已看懂任务？进入数学与实现", "Already understand the tasks? Continue to mathematics and implementation")) + '</p>')

    add("features", ("规则与手工特征 → 学习特征", "Rules and hand-crafted features → learned representations"),
        item(t("基础", "Foundations"), t("阈值、边缘与模板", "Thresholds, edges and templates"),
             '阈值把像素按强度分组，边缘刻画局部变化，模板匹配寻找相似结构。规则容易解释，但光照、尺度、背景和姿态变化会破坏固定假设；它们本身通常没有“狗”这样的语义。受控场景中仍有价值。',
             'Thresholds group pixels by intensity, edges capture local changes and templates search for similar structures. Rules are interpretable but fixed assumptions can fail under lighting, scale, background or pose changes. These operations generally lack semantics such as “dog”; they remain useful in controlled settings.',
             ("https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html", "OpenCV: thresholding")) +
        item("2004 / 2005", "SIFT / HOG",
             'SIFT 用局部关键点与描述子提高尺度、旋转变化下的匹配能力；HOG 汇总局部梯度方向，并可结合 SVM 做行人检测。关键变化是先设计稳健表示，再训练判别器，但特征设计仍依赖人工判断。',
             'SIFT uses local keypoints and descriptors for matching across scale and rotation changes. HOG summarizes local gradient orientations and can feed an SVM pedestrian detector. Robust representation design precedes classification, but features are still hand-engineered.',
             ("https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf", "Lowe: SIFT"),
             ("https://lear.inrialpes.fr/people/triggs/pubs/Dalal-cvpr05.pdf", "Dalal & Triggs: HOG")) +
        item("2012", "AlexNet",
             '大规模标注、GPU 与深层卷积推动端到端特征学习：从数据中学习有用表示，而不是完全手写描述子。CNN 并不是 2012 年才出现；AlexNet 是重要规模化节点，也不意味着每个小项目都要从零训练。',
             'Large labeled data, GPUs and deep convolutions advanced end-to-end feature learning instead of relying entirely on designed descriptors. CNNs predate 2012; AlexNet is a scaling milestone, not a reason for every small project to train from scratch.',
             ("https://proceedings.neurips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html", "AlexNet paper")) +
        item("2015 preprint / 2016 CVPR", "ResNet",
             '残差连接 y = x + F(x) 提供恒等路径，使很深网络更容易优化。这里可以看到“具体瓶颈 → 结构改动 → 实验验证”的研究方式，但不能把所有视觉模型失败都归因于梯度消失。',
             'Residual connections y = x + F(x) provide an identity path and make very deep networks easier to optimize. This exemplifies a concrete bottleneck → architectural intervention → experimental test; not every vision failure is a vanishing-gradient problem.',
             ("https://arxiv.org/abs/1512.03385", "Deep Residual Learning")))

    add("detection", ("检测：候选框、单阶段与多尺度", "Detection: proposals, one-stage prediction and scale"),
        item("2014 → 2015", "R-CNN → Faster R-CNN",
             '两阶段路线先生成区域候选，再判别与修正框。Faster R-CNN 用共享卷积特征上的区域建议网络 RPN 减少候选生成瓶颈。研究重点之一是把昂贵或割裂的步骤变成共享、可学习模块。',
             'Two-stage detection proposes regions, then classifies and refines boxes. Faster R-CNN uses a region proposal network on shared convolutional features to reduce proposal-generation bottlenecks. One research pattern is replacing costly disconnected steps with shared learnable components.',
             ("https://arxiv.org/abs/1311.2524", "R-CNN"), ("https://arxiv.org/abs/1506.01497", "Faster R-CNN")) +
        item("2015 preprint / 2016 CVPR", "YOLO",
             '把目标位置与类别预测整合为一次网络前向，强调实时检测。此后 YOLO 系列有许多不同实现；不能把第一代的网格 / objectness 公式直接当成我们使用的 YOLO11。快速独立逐帧检测也不自动解决跨帧身份。',
             'YOLO unifies localization and classification in one network forward pass, emphasizing real-time detection. Later YOLO families vary substantially; first-generation grid / objectness formulas are not automatically the formulas of our YOLO11. Fast framewise detection does not itself solve identity continuity.',
             ("https://arxiv.org/abs/1506.02640", "Original YOLO"), ("https://docs.ultralytics.com/models/yolo11/", "YOLO11 documentation")) +
        item("2016 preprint / 2017 CVPR", "FPN",
             '通过自顶向下与横向连接组合不同尺度特征，让高层语义与细粒度空间信息结合。小目标不只是“大模型不够大”，也可能受下采样、分辨率与特征融合限制。',
             'Top-down and lateral connections combine feature scales, linking semantic features with finer spatial detail. Small-object failures can involve downsampling, resolution and feature fusion rather than simply insufficient model size.',
             ("https://arxiv.org/abs/1612.03144", "Feature Pyramid Networks")) +
        item("2020", "DETR",
             '使用目标查询和集合预测，以二分图匹配训练一组目标输出。原始 DETR 不依赖传统 anchor 和 NMS，提供另一种去重与分配思路；不是所有 Transformer 检测器都必须以相同方式实现。',
             'Object queries and set prediction train a collection of outputs using bipartite matching. Original DETR avoids traditional anchors and NMS, offering another approach to assignment and duplicate suppression. Not every transformer detector uses the same design.',
             ("https://arxiv.org/abs/2005.12872", "End-to-End Object Detection with Transformers")))

    add("segmentation", ("分割：恢复细节与区分实例", "Segmentation: recover detail and separate instances"),
        item("2015", "U-Net",
             '编码器提取上下文，解码器恢复空间分辨率，跳跃连接补充局部细节。语义分割为像素分配类别，但要把两只同类的狗分开，还需要实例表示。',
             'An encoder extracts context, a decoder restores spatial resolution and skip connections recover local detail. Semantic segmentation labels pixel classes; separating two dogs also requires an instance representation.',
             ("https://arxiv.org/abs/1505.04597", "U-Net")) +
        item("2017", "Mask R-CNN",
             '在两阶段检测上增加实例 mask 分支，并用 RoIAlign 改善区域特征的空间对齐。检测框与像素分割关联，但不是同一个任务，也不能用框准确直接推断 mask 准确。',
             'Mask R-CNN adds an instance-mask branch to two-stage detection and uses RoIAlign for spatially aligned region features. Boxes and pixel segmentation are related but distinct; accurate boxes do not guarantee accurate boundaries.',
             ("https://arxiv.org/abs/1703.06870", "Mask R-CNN")) +
        item(t("本项目", "This project"), "YOLO11s-seg",
             '共享当前图像的 mask 原型，每个实例预测组合系数，形成像素 logits，再缩放、裁剪、二值化。这是逐帧实例分割；下一个帧相同数组下标不代表同一只狗。具体公式和源码放在数学页。',
             'Shared image-dependent mask prototypes combine with per-instance coefficients to form pixel logits, followed by resizing, cropping and thresholding. This is framewise instance segmentation: the same array index in the next frame need not be the same dog. Equations and code links are on the mathematics page.',
             ("https://github.com/ultralytics/ultralytics/blob/v8.3.221/ultralytics/nn/modules/head.py", "Pinned Segment head")) +
        '<p>' + link(f'math{".en" if language == "en" else ""}.html#masks', t("展开 YOLO mask 的数学实现", "Open the YOLO mask implementation")) + '</p>')

    add("foundation", ("Attention、预训练与可提示分割", "Attention, pretraining and promptable segmentation"),
        item("2020", "ViT",
             '把图像拆成 patch token，以自注意力学习 token 间关系。更广的交互方式带来不同的数据、计算与归纳偏置需求；不是一旦用 attention 就天然理解视频事件。',
             'ViT turns image patches into tokens and uses self-attention to model token relationships. This changes data, compute and inductive-bias requirements; attention alone does not imply video-event understanding.',
             ("https://arxiv.org/abs/2010.11929", "An Image is Worth 16x16 Words")) +
        item("2021 / 2023", "CLIP / DINOv2",
             'CLIP 从图像–文本对学习对齐表征；DINOv2 用自监督学习构建通用视觉特征。这两种监督信号不同。强预训练表示让下游任务可以复用知识，但不会免除领域差异与评估。',
             'CLIP learns aligned representations from image–text pairs; DINOv2 learns general visual features through self-supervision. Their learning signals differ. Strong pretrained features transfer knowledge to downstream tasks without eliminating domain shift or the need for evaluation.',
             ("https://arxiv.org/abs/2103.00020", "CLIP"), ("https://arxiv.org/abs/2304.07193", "DINOv2")) +
        item("2023", "SAM",
             '将分割组织为提示式任务：图像与空间提示共同决定输出区域，并通过大规模数据增强泛化。它解决“指定哪个目标并分出轮廓”，不等于自动判断所有语义类别或维持视频身份。',
             'SAM formulates segmentation as a promptable task: image and spatial prompts jointly determine the output region, supported by large-scale data. Segmenting a specified object is not the same as automatically recognizing all semantic categories or maintaining video identities.',
             ("https://arxiv.org/abs/2304.02643", "Segment Anything")) +
        item("2024", "SAM 2 / SAM 2.1",
             '加入流式视觉记忆，使当前图像可以读取目标相关历史。我们使用 SAM 2.1 Hiera Tiny 的冻结权重。目标发现与类别仍由项目封装解决；记忆能帮助遮挡后的恢复，也可能携带错误。',
             'Streaming visual memory lets current images read object-related history. We use frozen SAM 2.1 Hiera Tiny weights. The project wrapper still handles discovery and classes; memory may assist recovery after occlusion but can also carry errors.',
             ("https://arxiv.org/abs/2408.00714", "SAM 2 paper"), ("https://github.com/facebookresearch/sam2", "Official SAM 2 code / 2.1 release")))

    add("tracking", ("时间维度：框关联与视觉记忆", "Time: box association versus visual memory"),
        item("2016 / 2017", "SORT / Deep SORT",
             'SORT 将卡尔曼预测与一对一分配组合为轻量跟踪；Deep SORT 增加学习到的外观度量。由此可以区分位置外推、数据关联和外观重识别，而不是把整个跟踪器叫成一个卡尔曼滤波器。',
             'SORT combines Kalman prediction with one-to-one assignment for lightweight tracking. Deep SORT adds a learned appearance metric. Motion extrapolation, data association and appearance re-identification are distinct components, not one Kalman filter.',
             ("https://arxiv.org/abs/1602.00763", "SORT"), ("https://arxiv.org/abs/1703.07402", "Deep SORT")) +
        item("2021 preprint / 2022 ECCV", "ByteTrack",
             '利用低置信度检测接续未匹配的活动轨迹，避免把遮挡目标的弱检测一概丢掉。过去的观察融合成运动状态与不确定性，因此它也有历史记忆。当前实现没有外观 ReID，离开视野很久的狗可能回来变成新 ID。',
             'Low-score detections can reconnect unmatched active tracks instead of discarding every weak observation of an occluded object. Past observations are summarized in motion state and uncertainty, so it also has historical memory. The current implementation lacks appearance ReID; a dog returning after a long absence may receive a new ID.',
             ("https://arxiv.org/abs/2110.06864", "ByteTrack")) +
        item("2022 preprint / 2023 CVPR", "OC-SORT",
             '分析遮挡及非线性运动下卡尔曼状态误差的积累，并利用恢复后的观察修正运动估计。它为“历史运动状态什么时候需要纠正”提供相关依据；本项目不因此新增第三套必测跟踪器。',
             'Studies accumulated Kalman-state errors under occlusion and nonlinear motion, using recovered observations to correct motion estimates. It motivates asking when old motion state needs correction; it does not add a third required tracker to our project.',
             ("https://arxiv.org/abs/2203.14360", "OC-SORT paper"), ("https://github.com/noahcao/OC_SORT", "Official code")) +
        item("2022", "DeAOT",
             '在视频目标分割中解耦传播目标无关视觉信息与目标特定身份信息。它是预训练神经网络，不是 ByteTrack 式框匹配器。SAM-Track 将第一代 SAM 与这类传播模块连接；当前 proposal 未采用，网站仅保留背景介绍。',
             'DeAOT decouples propagation of object-agnostic visual information and object-specific identity information for video object segmentation. It is a pretrained neural network, not a ByteTrack-style box matcher. SAM-Track combines original SAM with this kind of propagation; it remains background, outside the current proposal.',
             ("https://arxiv.org/abs/2210.09782", "Decoupling Features in Hierarchical Propagation"), ("https://github.com/z-x-yang/Segment-and-Track-Anything", "SAM-Track code")) +
        item("2024 preprint / 2025 ICCV", "SAM2Long",
             '针对错误 mask 写入记忆后的累积影响，维持有限条候选分割路径，按累积质量分数保留分支，最后选择整段视频的最佳路径。它说明该问题已有直接研究；整段结束后的路径选择不等于零额外延迟的在线推理。本项目尚未实现。',
             'To address errors carried through mask memory, SAM2Long retains a bounded set of candidate segmentation paths, prunes by cumulative quality scores and selects the best path after the sequence. This is direct prior work on the issue; whole-video selection is not zero-extra-latency online inference. It is not implemented in our project.',
             ("https://arxiv.org/html/2410.16268v3", "SAM2Long paper"), ("https://github.com/Mark12Ding/SAM2Long", "Official code")) +
        item("2024", "SAMURAI",
             '用卡尔曼预测框与候选掩码框的重合度补充预测掩码质量，辅助选择候选结果，并利用质量、存在及运动一致性筛选记忆。它连接运动证据与视觉历史，但不等于给 SAM 加了 ByteTrack 的身份关联。官方实现还保留上一帧等回退条件，不能理解成完全排除所有低质量历史。',
             'Combines overlap with a Kalman-predicted box and predicted mask quality to select candidates, then uses quality, presence and motion consistency to select memory. It connects motion evidence with visual history, rather than adding ByteTrack identity association to SAM. Official code includes fallbacks such as retaining the previous frame, so it does not exclude every low-quality history item.',
             ("https://arxiv.org/html/2411.11922v2", "SAMURAI paper"), ("https://github.com/yangchris11/samurai", "Official code")))

    add("recent", ("较新进展：了解，不自动扩展项目", "Newer developments: context, not automatic scope expansion"),
        item("2025-11", "SAM 3",
             '官方论文把短名词短语或图像示例作为概念提示，输出所有符合概念的实例 mask 与身份，将发现、分割和跟踪进一步连接。这与 SAM 2.1 的空间提示能力不同。我们未运行 SAM 3，也不因有新模型就替换已确定的受控实验。',
             'The official paper uses short noun phrases or image exemplars as concept prompts to return matching instance masks and identities, further connecting discovery, segmentation and tracking. This differs from SAM 2.1 spatial prompting. We have not run SAM 3 and do not automatically replace the controlled study because a newer model exists.',
             ("https://arxiv.org/abs/2511.16719", "SAM 3: Segment Anything with Concepts"), ("https://github.com/facebookresearch/sam3", "Official SAM 3 code")) +
        item("2026-01", "YOLO26",
             'Ultralytics 官方资料介绍原生端到端推理、较轻的检测头及训练方案更新，表明 YOLO11 不应被称为“最新 YOLO”。本网站的数学页明确针对 8.3.221 下的 YOLO11，不把新版本不同的推理头混进去。',
             'Ultralytics documents native end-to-end inference, a lighter detection head and an updated training recipe. YOLO11 should therefore not be labeled the latest YOLO. Our mathematical reference explicitly targets YOLO11 under 8.3.221, rather than mixing in another version’s head.',
             ("https://docs.ultralytics.com/models/yolo26/", "Official YOLO26 documentation")) + t(
             '<p class="small">本节核对日期：2026-10-14。这里只列与讨论有关的进展，不是完整排行榜，也不声称性能已在我们的数据上复现。</p>',
             '<p class="small">Checked 2026-10-14. These are developments relevant to our discussion, not an exhaustive leaderboard or reproduced results on our data.</p>'))

    add("inspiration", ("如何从进展中提炼项目问题", "Deriving project questions from these developments"), t(
        '<p>当前研究主线已经从完整 A0/B0 比较，递进到两套系统内部的历史保留／重置实验。ByteTrack 不是无记忆对照，SAM 也不天然保证长期身份正确。</p><dl><dt>两类状态，同一个干预问题</dt><dd>ByteTrack 的运动估计与 SAM 的视觉历史分别怎样响应新观察？比较 A-H/A-R 与 B-H/B-R，先解释各自差异，再对照条件规律。</dd><dt>历史影响会持续多久</dt><dd>观察纠正后的时间曲线：可靠的新观察是否很快消除旧状态影响？遮挡、突变运动、相似目标是否使差异持续？这些都是待验证假设。</dd><dt>局部恢复为什么不等于全系统改善</dt><dd>正确检测可能没有送达正确轨迹；轨迹可能已经删除。机制实验固定路由，自动系统仍自行关联，因此需要单独报告不适用事件和完整系统成绩。</dd></dl><p>与“RNN 梯度消失 → 长程训练改进”的研究方式相似之处，是从机制提出可证伪假设；不能说 SAM 推理漂移就是同一个梯度问题。核心实验冻结权重，最多一项自动策略验证取决于证据。</p>',
        '<p>The research now progresses from complete A0/B0 comparison to within-system history-retention/reset experiments. ByteTrack is not a no-memory control, and SAM does not inherently guarantee long-term identity correctness.</p><dl><dt>Two state types, one intervention question</dt><dd>How do ByteTrack motion estimates and SAM visual history respond to new observations? Compare A-H/A-R and B-H/B-R, explaining each pair before comparing conditional patterns.</dd><dt>How long does history matter?</dt><dd>Inspect post-correction curves: do reliable new observations quickly erase old-state effects? Do occlusion, motion changes or distractors prolong them? These remain hypotheses.</dd><dt>Why local recovery may not improve the whole system</dt><dd>A correct detection may be routed to the wrong track, or the old track may have been deleted. Mechanism experiments fix routing; automatic systems still associate independently. Report ineligible cases and complete-system outcomes separately.</dd></dl><p>The analogy with vanishing gradients in RNN training is a research process: derive falsifiable hypotheses from mechanisms. SAM inference drift is not the same gradient problem. Core experiments fix weights; at most one automatic-policy validation depends on evidence.</p>') +
        '<p>' + link(f'experiments{".en" if language == "en" else ""}.html', t("查看四组对照流程", "Open the four-group experiment walkthrough")) + ' · ' + link(f'math{".en" if language == "en" else ""}.html#research', t("查看数学定义", "Open mathematical definitions")) + '</p>')

    add("sources", ("源码与评分资料索引", "Implementation and evaluation source index"), t(
        '<p>上方每个进展都附原论文或官方文档；下面是复核本项目实现时最直接的入口。库版本号、模型代数与 checkpoint 是不同层次。固定源码链接能避免后续升级改变公式含义。</p>',
        '<p>Each milestone above links its original paper or official documentation. The entries below are direct implementation checks. Package version, model generation and checkpoint are separate identifiers; pinned source links prevent later updates from changing the meaning of an explanation.</p>') +
        '<ul class="source-list"><li>' + source("yolo", "nn/modules/head.py", "Ultralytics 8.3.221: Detect / Segment") + ' · ' + source("yolo", "utils/loss.py", "Losses") + ' · ' + source("yolo", "utils/tal.py", "Assignment") + '<p>' + t("框解码、mask 分支、训练损失与正样本分配。", "Box decoding, mask branches, training losses and positive assignment.") + '</p></li>' +
        '<li>' + source("yolo", "trackers/byte_tracker.py", "BYTETracker") + ' · ' + source("yolo", "trackers/utils/kalman_filter.py", "Kalman") + ' · ' + source("yolo", "trackers/utils/matching.py", "Matching") + '<p>' + t("两阶段匹配、轨迹状态与代价限制。", "Two-stage association, track states and cost limits.") + '</p></li>' +
        '<li>' + source("sam", "sam2/modeling/sam2_base.py", "SAM 2.1: memory and tracking") + ' · ' + source("sam", "sam2/modeling/sam/mask_decoder.py", "Mask decoder") + '<p>' + t("记忆选择 / 写入、提示与像素预测；固定到本地安装 commit。", "Memory selection / writes, prompts and pixel prediction; pinned to the locally installed commit.") + '</p></li>' +
        '<li>' + source("eval", "hota.py", "TrackEval HOTA") + ' · ' + source("eval", "identity.py", "TrackEval Identity") + '<p>' + t("已核对公开源码，不表示正式数据适配与评测已经完成。", "Public source inspected; formal dataset integration and benchmarking are not complete.") + '</p></li>' +
        '<li>' + link("https://arxiv.org/abs/2009.07736", "HOTA paper") + ' · ' + link("https://arxiv.org/abs/1609.01775", "ID metrics paper") + ' · ' + link("https://youtube-vos.org/dataset/vis/", "YouTube-VIS dataset") + '<p>' + t("评价定义与数据任务；正式实验记录具体版本、划分和类别映射。", "Metric definitions and dataset task; record exact versions, splits and category mappings for experiments.") + '</p></li></ul>' + t(
        '<p class="small">网页内容、公式和已有视频可离线阅读；点击论文或官方源码需要联网。未复制第三方完整仓库、训练数据或任何私人登录资料。</p>',
        '<p class="small">Page content, equations and saved videos work offline; paper and official-code links require internet access. No complete third-party repositories, training data or private login information are copied here.</p>'))

    return (t("技术脉络与来源", "Technical History and Sources"),
            t('<p class="lead">按“原来的瓶颈 → 关键思路 → 仍未解决的问题”查阅，不增加必修课程负担。</p>', '<p class="lead">Read by bottleneck → key idea → remaining limitation. This is a reference, not extra required lessons.</p>'), pages)
