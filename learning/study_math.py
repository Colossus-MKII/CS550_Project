"""Implementation-oriented mathematics; translations share equations and anchors."""
from .study import equation as e, link, pick, section, source


def content(language, home):
    t = lambda zh, en: pick(language, zh, en)
    pages = []

    def add(key, title, body, lesson=None):
        label = t(*title)
        back = link(f"{home}#{lesson}", t("回到对应视频课 / 实验", "Return to the corresponding lesson / experiment")) if lesson else None
        pages.append((key, label, section(key, label, body, back)))

    def refs(*items):
        return '<p class="source-note">' + t("实现与来源：", "Implementation and sources: ") + " · ".join(items) + "</p>"

    add("notation", ("阅读约定与版本", "Notation and versions"), t(
        '<p>先看主线中的模型职责与 A0/B0 实验，再按问题查阅本页。不必先推完所有公式才能开始实验。</p><p>下文区分三类内容：<strong>实现事实</strong>对应已核对的本地代码；<strong>教学算例</strong>用小数字解释运算，不是模型测量；<strong>研究假设</strong>尚待验证，不能写成实验结论。</p>',
        '<p>Read the model roles and A0/B0 experiment first; use this page to answer specific implementation questions. Deriving every equation is not a prerequisite for starting experiments.</p><p><strong>Implementation facts</strong> refer to inspected code. <strong>Worked examples</strong> use small invented numbers, not model measurements. <strong>Research hypotheses</strong> remain untested and must not be reported as findings.</p>') +
        '<div class="table-wrap"><table><thead><tr><th>' + t("对象", "Component") + '</th><th>' + t("核对版本 / 范围", "Checked version / scope") + '</th></tr></thead><tbody>' +
        '<tr><td>YOLO11s-seg / ByteTrack</td><td>ultralytics 8.3.221</td></tr>' +
        '<tr><td>SAM 2.1 Hiera Tiny</td><td><code>2b90b9f5ceec907a1c18123530e92e794ad901a4</code></td></tr>' +
        '<tr><td>TrackEval</td><td><code>12c8791b303e0a0b50f753af204249e622d0281a</code> · ' + t("源码核对，尚未接入正式评估", "source inspected; formal evaluation integration pending") + '</td></tr></tbody></table></div>' + t(
        '<p class="variables">I / X：图像或特征；θ：已学习的网络权重；σ：sigmoid；L：未过 sigmoid 的 logit；B：框；M：视频记忆。符号按小节定义，卡尔曼协方差 P 与 YOLO 原型 P 不是同一变量。</p>',
        '<p class="variables">I / X: images or features; θ: learned weights; σ: sigmoid; L: pre-sigmoid logits; B: boxes; M: video memory. Symbols are local to each section: Kalman covariance P is not the YOLO prototype tensor P.</p>'))

    add("features", ("共同基础：卷积、非线性与残差", "Shared foundations: convolution, nonlinearity and residuals"), t(
        '<p>网络不直接在原始像素中查找“狗模板”。卷积把局部像素组合成特征，逐层扩大感受范围；训练决定哪些组合有用。这里写的是深度学习库常用的互相关形式，通常也称卷积。</p>',
        '<p>The network does not look up a fixed dog template in raw pixels. Convolution combines local inputs into features with progressively larger receptive fields; training determines useful combinations. The expression below is cross-correlation, conventionally called convolution in deep-learning libraries.</p>') +
        e(r'Y_{o,i,j}=b_o+\sum_{c,u,v}W_{o,c,u,v}X_{c,si+u-p,sj+v-p}') + t(
        '<p class="variables">c / o：输入 / 输出通道；u、v：卷积核位置；s：步长；p：填充。三通道图像会变成多通道特征图，而不是每个通道都对应一个物体类别。</p>',
        '<p class="variables">c / o: input / output channels; u, v: kernel positions; s: stride; p: padding. RGB images become multi-channel feature maps; a channel need not represent an object category.</p>') +
        e(r'\operatorname{BN}(x)=\gamma\frac{x-\mu}{\sqrt{\sigma^2+\epsilon}}+\beta,\qquad \operatorname{SiLU}(x)=x\,\operatorname{sigmoid}(x)') +
        e(r'y=x+F_\theta(x),\qquad \frac{\partial y}{\partial x}=I+\frac{\partial F_\theta}{\partial x}') + t(
        '<p>常见 YOLO Conv 模块组合卷积、BatchNorm 和 SiLU；推理时 BN 使用运行统计或折叠进卷积。残差的恒等路径改善深层优化，但不是保证所有梯度问题消失。SAM 的 Hiera / attention 模块另有其具体结构，不能把整个 SAM 说成这一个卷积公式。</p>',
        '<p>A typical YOLO Conv module combines convolution, BatchNorm and SiLU; inference uses running BN statistics or fused convolutions. Residual identity paths aid optimization without guaranteeing that every gradient problem disappears. SAM uses its own Hiera / attention architecture, not merely this convolution block.</p>') +
        refs(source("yolo", "nn/modules/conv.py", "Conv.forward"), link("https://arxiv.org/abs/1512.03385", "ResNet")), "chapter-1")

    add("yolo", ("YOLO：从张量到检测框", "YOLO: from tensors to boxes"), t(
        '<p>预处理先缩放与 letterbox 填充，再把图像转换成网络张量。网络坐标必须去掉填充并除以缩放系数，才能回到原画面。外部缩小视频，与模型内部预处理是两层操作。</p><p>以<strong>实际输入网络的张量为 640 × 640</strong>为例，三个预测层步长为 8、16、32：</p>',
        '<p>Preprocessing resizes and letterboxes the image into a network tensor. Undo padding and divide by the scale factor to map predictions back to the original image. External video resizing and internal model preprocessing are separate operations.</p><p>For an example whose <strong>actual network tensor is 640 × 640</strong>, the three prediction strides are 8, 16 and 32:</p>') +
        e(r'N=80^2+40^2+20^2=8400') + t(
        '<p>矩形输入时 N 会改变。COCO 预训练头有 80 类、每边 16 个回归桶、32 个 mask 系数。因此每个候选逻辑上包含 64 + 80 + 32 = 176 个原始数；回归解码后是 4 + 80 + 32 = 116 个数。它们在实现中来自不同分支，并非都在同一个原始张量里。</p><h3>类别分数：独立 sigmoid</h3>',
        '<p>N changes for rectangular inputs. The COCO pretrained head has 80 classes, 16 regression bins per side and 32 mask coefficients: logically 64 + 80 + 32 = 176 raw values per candidate, or 4 + 80 + 32 = 116 after box decoding. The implementation produces these through separate branches, not one raw tensor.</p><h3>Class scores: independent sigmoids</h3>') +
        e(r'p_c=\sigma(z_c)=\frac{1}{1+e^{-z_c}},\qquad \hat c=\arg\max_c p_c') + t(
        '<p>本地默认单标签后处理取最高分类分数。它不是所有类别之和等于 1 的 softmax；也不要套用旧版 YOLO 的 objectness × class 公式。分数不保证经过概率校准，更不是身份正确率。</p><h3>DFL：从分布求距离</h3>',
        '<p>Default single-label postprocessing selects the highest class score. This is not a softmax summing to one, nor the objectness × class formula from older YOLO variants. Scores are not guaranteed to be calibrated probabilities, and are not identity confidence.</p><h3>DFL: a distance from a distribution</h3>') +
        e(r'q_k=\frac{e^{z_k}}{\sum_{j=0}^{15}e^{z_j}},\qquad d=\sum_{k=0}^{15}kq_k') +
        e(r'(x_1,y_1,x_2,y_2)=s(a_x-l,\ a_y-t,\ a_x+r,\ a_y+b)') + t(
        '<p class="variables">l、t、r、b 是相对候选点的四边距离，单位为该层网格；s 转换为输入像素。这里的候选点是网格位置，不是旧式预设宽高的 anchor box。</p><div class="worked-example"><p>教学算例：候选点 (10.5, 7.5)，四边距离 (2, 1, 3, 4)，步长 8，得到框 [68, 52, 108, 92]。</p></div><h3>NMS 与输出</h3><p>先过滤类别和分数，再按类别进行 NMS：依次保留高分框，抑制重合过大的低分框。YOLO11 的这条推理路径仍使用 NMS。最终的绘图函数只负责把这些数值画在视频上。</p>',
        '<p class="variables">l, t, r, b are distances from a candidate point in grid units; stride s converts them to input pixels. These points are grid locations, not old-style predefined anchor-box widths and heights.</p><div class="worked-example"><p>Worked example: point (10.5, 7.5), distances (2, 1, 3, 4), stride 8 → box [68, 52, 108, 92].</p></div><h3>NMS and output</h3><p>After class and score filtering, class-aware NMS keeps high-score boxes and suppresses strongly overlapping lower-score boxes. This YOLO11 inference path still uses NMS. Rendering subsequently draws these numeric outputs onto the video.</p>') +
        refs(source("yolo", "nn/modules/head.py", "Detect._inference / Segment"), source("yolo", "utils/tal.py", "dist2bbox / make_anchors"), source("yolo", "cfg/models/11/yolo11-seg.yaml", "YOLO11 segmentation config"), source("yolo", "utils/ops.py", "non_max_suppression")), "chapter-1")

    add("masks", ("YOLO：原型如何变成像素 mask", "YOLO: prototypes to pixel masks"), t(
        '<p>当前图像产生共享原型 P，形状为 32 × Hm × Wm。每个实例 i 另外预测 32 个系数 a。对每个像素做线性组合：</p>',
        '<p>The current image produces shared prototypes P of shape 32 × Hm × Wm. Instance i predicts another 32 coefficients a. A linear combination produces each pixel logit:</p>') +
        e(r'L_i(u,v)=\sum_{k=1}^{32}a_{ik}P_k(u,v),\qquad p_i(u,v)=\sigma(L_i(u,v))') + t(
        '<div class="worked-example"><p>只保留三个非零系数 [2, −1, 0.5]，某像素的原型值为 [0.8, 0.2, −0.4]：L = 1.2，sigmoid(L) ≈ 0.769，该像素归入前景。真实实现有 32 项。</p></div><p>本地 <code>retina_masks=True</code> 路径将组合后的 logits 去掉 letterbox、缩放到原图，再按预测框裁剪，最终用 <code>logits &gt; 0</code> 二值化。它与 sigmoid &gt; 0.5 等价；输出 mask 已是二值数组。</p><p>原型随图像变化，不是固定狗轮廓；像素 logit、实例分类分数、跨帧身份是三种不同的量。框偏移还可能通过裁剪影响 mask。</p>',
        '<div class="worked-example"><p>With only three nonzero coefficients [2, −1, 0.5] and prototype values [0.8, 0.2, −0.4] at a pixel: L = 1.2 and sigmoid(L) ≈ 0.769, so the pixel becomes foreground. The real implementation has 32 terms.</p></div><p>The local <code>retina_masks=True</code> path removes letterbox padding from the combined logits, resizes them to the original image, crops to the predicted box and thresholds at <code>logits &gt; 0</code>. This is equivalent to sigmoid &gt; 0.5; the returned mask is already binary.</p><p>Prototypes change with the image; they are not fixed dog outlines. Pixel logits, instance class scores and cross-frame identities are distinct quantities. Box errors can also affect masks through cropping.</p>') +
        refs(source("yolo", "utils/ops.py", "process_mask_native / scale_masks / crop_mask"), source("yolo", "nn/modules/block.py", "Proto")), "chapter-2")

    add("training", ("训练损失：模型原来怎样学会预测", "Training losses: how the model learns to predict"), t(
        '<p class="status-note">保留训练数学作为模型学习背景。当前 proposal 的核心实验冻结所有模型权重，研究推理状态的保留与重置；尚未进行项目微调。</p><p>本地 YOLO11 segmentation 使用名为 <code>v8SegmentationLoss</code> 的损失类。默认增益下：</p>',
        '<p class="status-note">Training mathematics remains as model-learning background. The current proposal fixes all model weights and studies inference-state retention versus resetting; project fine-tuning has not been run.</p><p>Local YOLO11 segmentation uses the class named <code>v8SegmentationLoss</code>. With default gains:</p>') +
        e(r'\mathcal L=7.5\mathcal L_{box}+7.5\mathcal L_{mask}+0.5\mathcal L_{cls}+1.5\mathcal L_{DFL}') + t(
        '<p>各项先有自己的归一化，最后还乘 batch size；这些权重不是各项实际贡献的百分比。</p><h3>正样本分配：先决定谁学哪个目标</h3><p>Task-Aligned Assigner 在候选点位于真实框内部的条件下，按下面的对齐分数选择 top-10，冲突时按重合度处理：</p>',
        '<p>Terms have their own normalization, and the final loss is multiplied by batch size. These gains are not percentages of the realized loss.</p><h3>Positive assignment: who learns which object?</h3><p>The Task-Aligned Assigner restricts candidates to points inside a ground-truth box, ranks by the alignment score below and selects top-10; overlap resolves conflicts:</p>') +
        e(r'T_{ga}=p_{a,c_g}^{0.5}\left[\max(\operatorname{CIoU}(B_a,G_g),0)\right]^6') +
        e(r'q_{a,c_g}=T_{ga}\frac{\max_{a^+}\operatorname{overlap}_{ga^+}}{\max_{a^+}T_{ga^+}+\epsilon}') + t(
        '<p class="variables">g：标注目标；a：候选；c_g：真实类别；a⁺：该目标的正样本。q 是归一化后的软分类目标，其他类别为 0。传入分配器的预测已 detach，不对本次分配决定求导。</p><h3>分类：BCE</h3>',
        '<p class="variables">g: annotated object; a: candidate; c_g: true class; a⁺: positives for that object. q is the normalized soft class target; other classes have zero targets. Predictions passed into assignment are detached; backpropagation does not differentiate through this assignment decision.</p><h3>Classification: BCE</h3>') +
        e(r'\operatorname{BCE}(p,q)=-q\log p-(1-q)\log(1-p),\qquad \frac{\partial\operatorname{BCE}}{\partial z}=\sigma(z)-q') + t(
        '<p>对候选和类别求和，再除以软目标分数之和（最小取 1）。不是简单把每个正候选都当成类别标签 1。</p><h3>定位：CIoU 与 DFL</h3>',
        '<p>Sum over candidates and classes, then divide by the total soft-target score, clamped to at least one. Not every positive candidate simply receives a hard class target of one.</p><h3>Localization: CIoU and DFL</h3>') +
        e(r'\operatorname{CIoU}=\operatorname{IoU}-\frac{\rho^2(c_p,c_g)}{d_{enc}^2}-\alpha v') +
        e(r'v=\frac{4}{\pi^2}\left(\arctan\frac{w_g}{h_g}-\arctan\frac{w_p}{h_p}\right)^2,\qquad \alpha=\frac{v}{1-\operatorname{IoU}+v+\epsilon}') + t(
        '<p>ρ 是中心距离，d_enc 是最小包围框对角线；v 惩罚长宽比差异。实现中 α 不回传梯度。box loss 对正样本的 1 − CIoU 按软目标加权归一化。</p>',
        '<p>ρ is center distance; d_enc is the enclosing-box diagonal; v penalizes aspect-ratio differences. The implementation stops gradients through α. Box loss weights positive 1 − CIoU values by soft-target scores and normalizes them.</p>') +
        e(r'\mathcal L_{DFL}(d=2.4)=-0.6\log q_2-0.4\log q_3') + t(
        '<p>DFL 让距离分布学会落在相邻整数桶之间，再通过期望解码为连续距离。这里用 q_k 表示回归桶概率，与上面的软类别目标是不同量。</p><h3>分割：逐像素 BCE</h3><p>把实例系数与原型相乘得到 logits，计算像素 BCE；按真实框裁剪并进行面积与正样本归一化。本地这条 YOLO 分割损失路径不含 Dice loss。它也没有直接优化跨帧 ID 连续性，因此 ID 断裂本身不能证明应该微调 YOLO。</p>',
        '<p>DFL learns a distribution between adjacent integer bins, decoded to a continuous distance by its expectation. Here q_k denotes regression-bin probabilities, not the soft class target above.</p><h3>Segmentation: pixelwise BCE</h3><p>Multiply coefficients by prototypes to obtain logits, compute pixel BCE, crop to the ground-truth box and normalize by area and positive count. This local YOLO segmentation loss does not include Dice loss. It also does not directly optimize cross-frame ID continuity: an ID break alone does not justify fine-tuning YOLO.</p>') +
        refs(source("yolo", "utils/loss.py", "v8SegmentationLoss / BboxLoss / DFLoss"), source("yolo", "utils/tal.py", "TaskAlignedAssigner"), source("yolo", "utils/metrics.py", "bbox_iou"), source("yolo", "cfg/default.yaml", "default gains")), "chapter-7")

    add("kalman", ("ByteTrack：卡尔曼状态与更新", "ByteTrack: Kalman state and updates"), t(
        '<p>每个轨迹有八维状态；位置是框中心，a 是宽高比，h 是高度，后四项是各自的每帧速度。它跟踪的是框的运动，不是目标外观。</p>',
        '<p>Each track has an eight-dimensional state: box center, aspect ratio a, height h, and four corresponding per-frame velocities. This models box motion, not appearance.</p>') +
        e(r'x=(c_x,c_y,a,h,v_x,v_y,v_a,v_h)^T,\qquad z=(c_x,c_y,a,h)^T') +
        e(r'F=\begin{bmatrix}I_4&I_4\\0&I_4\end{bmatrix},\qquad H=\begin{bmatrix}I_4&0\end{bmatrix}') +
        e(r'x^-=Fx,\qquad P^-=FPF^T+Q') +
        e(r'r=z-Hx^-,\quad S=HP^-H^T+R,\quad K=P^-H^TS^{-1}') +
        e(r'x^+=x^-+Kr,\qquad P^+=P^--KSK^T') + t(
        '<p class="variables">P：状态不确定性；Q：运动噪声；R：观测噪声；r：观测与预测的差；K：预测与观测之间的融合权重。模型假设近似匀速，时间步为一帧。</p><details><summary>本地噪声不是任意常数</summary><p>预测 Q 的对角标准差依次为 [h/20, h/20, 0.01, h/20, h/160, h/160, 0.00001, h/160]；R 的对角标准差为 [h/20, h/20, 0.1, h/20]。平方后成为方差。初始化协方差另有放大系数。</p></details><div class="worked-example"><p>一维教学算例：位置 100、速度 5，P = diag(4, 1)，Q = diag(1, 0.25)，R = 4。预测位置 105，预测协方差为 [[6, 1], [1, 1.25]]。新观测在 110，K = [0.6, 0.1]ᵀ，更新位置 108、速度 5.5。实际实现用上面的八维状态。</p></div>',
        '<p class="variables">P: state uncertainty; Q: motion noise; R: observation noise; r: observation-minus-prediction residual; K: fusion weights. Motion is approximately constant velocity, with one frame per time step.</p><details><summary>The local noise model is not arbitrary constants</summary><p>Prediction Q has diagonal standard deviations [h/20, h/20, 0.01, h/20, h/160, h/160, 0.00001, h/160]; R uses [h/20, h/20, 0.1, h/20]. Squaring gives variances. Initialization uses additional covariance multipliers.</p></details><div class="worked-example"><p>One-dimensional worked example: position 100, velocity 5, P = diag(4, 1), Q = diag(1, 0.25), R = 4. Predicted position is 105 and covariance [[6, 1], [1, 1.25]]. With observation 110, K = [0.6, 0.1]ᵀ; updated position is 108 and velocity 5.5. The real implementation uses the eight-dimensional state above.</p></div>') +
        refs(source("yolo", "trackers/utils/kalman_filter.py", "KalmanFilterXYAH")), "chapter-3")

    add("association", ("ByteTrack：匹配与轨迹生命周期", "ByteTrack: association and track lifetime"), t(
        '<p>卡尔曼预测之后，还需要决定哪个观测属于哪个轨迹。先计算预测框 i 与检测框 j 的匹配代价；默认高分阶段融合检测分数 s_j：</p>',
        '<p>After Kalman prediction, association decides which observation belongs to which track. Compute the cost between predicted box i and detection j; the default high-score stage fuses detection score s_j:</p>') +
        e(r'C^{IoU}_{ij}=1-\operatorname{IoU}(B_i,D_j),\qquad C^{fused}_{ij}=1-\operatorname{IoU}(B_i,D_j)s_j') + t(
        '<p>本地使用带代价门槛的一对一线性分配，默认 LAPJV；允许轨迹 / 检测不匹配。不是逐个贪心选最近框，也不是只要 IoU 大于 0.8 就匹配。<code>match_thresh=0.8</code> 限制的是代价。</p><div class="worked-example"><p>IoU = 0.7、检测分数 = 0.9 时，融合代价为 1 − 0.7 × 0.9 = 0.37。门槛 0.8 只能说明该边有资格，仍需服从全局一对一约束。</p></div>',
        '<p>The local implementation uses cost-limited one-to-one linear assignment, LAPJV by default, with unmatched options. This is neither greedy nearest-box matching nor a requirement that IoU exceed 0.8. <code>match_thresh=0.8</code> limits the cost.</p><div class="worked-example"><p>For IoU = 0.7 and detection score = 0.9, fused cost is 1 − 0.7 × 0.9 = 0.37. Passing the 0.8 cost limit only makes this edge eligible; global one-to-one constraints still apply.</p></div>') +
        '<div class="table-wrap"><table><thead><tr><th>' + t("阶段", "Stage") + '</th><th>' + t("本地默认规则", "Local default rule") + '</th></tr></thead><tbody>' +
        '<tr><td>1</td><td>' + t("活动 + 丢失轨迹与分数 ≥ 0.25 检测匹配；融合代价门槛 0.8。", "Active + lost tracks match detections scoring ≥ 0.25; fused-cost limit 0.8.") + '</td></tr>' +
        '<tr><td>2</td><td>' + t("仍未匹配的活动轨迹，与 0.1 &lt; 分数 &lt; 0.25 的检测匹配；纯 IoU 代价门槛 0.5。", "Still-unmatched active tracks match detections with 0.1 &lt; score &lt; 0.25; pure IoU-cost limit 0.5.") + '</td></tr>' +
        '<tr><td>3</td><td>' + t("未确认轨迹匹配剩余高分检测，代价门槛 0.7；剩余满足新轨迹分数门槛的检测可创建 ID。", "Unconfirmed tracks match remaining high-score detections at cost limit 0.7; remaining detections meeting the new-track score threshold can initialize IDs.") + '</td></tr>' +
        '<tr><td>4</td><td>' + t("超过 max_time_lost 才移除丢失轨迹；当前调用默认保留约 30 帧。", "Lost tracks are removed after max_time_lost; the current invocation retains roughly 30 frames.") + '</td></tr></tbody></table></div>' + t(
        '<p>低分框用于救回已有轨迹，不会在第二阶段直接大量创建新 ID。提前把 YOLO 阈值提得很高，会让 ByteTrack 根本看不到低分候选。</p><p>这个 ByteTrack 路径没有外观 ReID，也不在主要匹配步骤使用马氏距离门控；存在卡尔曼协方差不等于所有匹配都用它。默认教学接口也未显式按类别隔离匹配，proposal 的 A0 需要另加这一封装。</p><details><summary>若研究 ReID，需要增加什么数学量？</summary><p>给每个目标裁剪图提取外观向量 f，用余弦距离 1 − fᵢᵀfⱼ / (‖fᵢ‖‖fⱼ‖) 补充运动 / IoU 代价，再设门控与融合规则。它不是只改 ByteTrack 的保留帧数；特征模型、额外计算和错误匹配都需单独评价。本项目尚未实现该变体。</p></details>',
        '<p>Low-score boxes rescue existing tracks; the second stage does not directly spawn many new IDs. An excessively high YOLO threshold removes those candidates before ByteTrack can use them.</p><p>This ByteTrack path has no appearance ReID and does not use Mahalanobis gating in its main matching stages; maintaining covariance does not mean every association uses it. The default teaching interface also lacks explicit class-separated matching; A0 requires that additional wrapper.</p><details><summary>What would an appearance-ReID study add?</summary><p>Extract an appearance vector f from each object crop and supplement motion / IoU cost with cosine distance 1 − fᵢᵀfⱼ / (‖fᵢ‖‖fⱼ‖), with explicit gating and fusion rules. This is not merely changing the retention buffer; the feature model, extra cost and wrong associations require evaluation. This project variant is not implemented.</p></details>') +
        refs(source("yolo", "trackers/byte_tracker.py", "BYTETracker.update / get_dists"), source("yolo", "trackers/utils/matching.py", "linear_assignment / fuse_score"), source("yolo", "cfg/trackers/bytetrack.yaml", "defaults"), link("https://arxiv.org/abs/1703.07402", "Deep SORT")), "chapter-3")

    add("sam", ("SAM 2.1：提示、注意力与 mask", "SAM 2.1: prompts, attention and masks"), t(
        '<p>Hiera Tiny 配置内部图像尺寸为 1024。主图像特征是 256 × 64 × 64，另有高分辨率分支。记忆注意力有 4 层、模型维度 256，记忆特征通道为 64；这不是说整个 SAM 只有一种分辨率或一个注意力头。</p><h3>框如何成为提示</h3><p>框转换成左上、右下两个角点，映射到内部坐标后加 0.5 像素中心偏移，再归一化。随机 Fourier 位置编码配合两个不同的可学习角点类型向量：</p>',
        '<p>Hiera Tiny uses internal image size 1024. Its main image feature map is 256 × 64 × 64, with additional high-resolution branches. Memory attention has four layers, model dimension 256 and memory features with 64 channels. These are not the only resolution or attention-head configuration in the entire network.</p><h3>Turning a box into a prompt</h3><p>A box becomes top-left and bottom-right corners, transformed to internal coordinates, shifted by 0.5 for pixel centers and normalized. Random Fourier positional encoding is combined with distinct learned corner-type embeddings:</p>') +
        e(r'\phi(u)=[\sin(2\pi(2u-1)G),\ \cos(2\pi(2u-1)G)]') + t(
        '<p class="variables">u 是归一化二维坐标；G 是固定随机高斯矩阵，不是每帧重新生成。空间提示告诉模型“分割这里的这个目标”，并未提供文字类别“dog”。</p><h3>当前画面如何读取历史</h3>',
        '<p class="variables">u is a normalized 2D coordinate; G is a fixed random Gaussian matrix, not resampled every frame. A spatial prompt identifies which object to segment; it does not provide the text class “dog”.</p><h3>Reading history from the current frame</h3>') +
        e(r'Q=XW_Q,\quad K=MW_K,\quad V=MW_V') +
        e(r'\operatorname{Attention}(Q,K,V)=\operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V') + t(
        '<p>这里是单次注意力的核心式：当前特征查询历史目标相关信息。实际代码还使用 RoPE / 位置编码、归一化、残差、前馈层与目标指针，不等于只有一个矩阵相乘。</p><h3>mask 解码</h3><p>双向交互后的 mask token 经 MLP 产生向量 w_k，与上采样像素特征 U 做乘积：</p>',
        '<p>This is the core of one attention operation: current features query historical object-related information. The real code also uses RoPE / positional encodings, normalization, residuals, feed-forward layers and object pointers; it is not just one matrix multiplication.</p><h3>Mask decoding</h3><p>After two-way interactions, an MLP transforms mask token k into vector w_k, multiplied with upsampled pixel features U:</p>') +
        e(r'L_k(u,v)=\sum_d w_{kd}U_d(u,v),\qquad \widehat m_k(u,v)=\mathbf{1}[L_k(u,v)>0]') + t(
        '<p>YOLO 和 SAM 最后都可出现“系数 × 像素特征”形式；区别不是一个会矩阵乘、另一个不会，而是特征、系数与提示 / 历史条件如何产生。SAM 还有 mask 质量与目标存在性预测，不能与 YOLO 分类分数混用。</p>',
        '<p>Both YOLO and SAM can end with coefficients multiplied by pixel features. The distinction is how those features and coefficients are conditioned on the image, prompts and history, not whether matrix multiplication exists. SAM also predicts mask quality and object presence; these are not YOLO class scores.</p>') +
        refs(source("sam", "sam2/modeling/sam/prompt_encoder.py", "PromptEncoder"), source("sam", "sam2/modeling/position_encoding.py", "PositionEmbeddingRandom"), source("sam", "sam2/modeling/memory_attention.py", "MemoryAttention"), source("sam", "sam2/modeling/sam/mask_decoder.py", "MaskDecoder.predict_masks"), source("sam", "sam2/configs/sam2.1/sam2.1_hiera_t.yaml", "Hiera Tiny config")), "chapter-4")

    add("memory", ("SAM 2.1：记忆写入与误差传播", "SAM 2.1: memory writes and error propagation"), t(
        '<p>普通软 mask 写入路径先做 sigmoid，再缩放和平移；不是先把 logits 放大再 sigmoid：</p>',
        '<p>The ordinary soft-mask write path applies sigmoid first, then scaling and shifting. It does not scale logits before sigmoid:</p>') +
        e(r'm_{mem}=20\sigma(L)-10') +
        e(r'M_t=\operatorname{OutProj}\left(\operatorname{Fuser}\left(\operatorname{Conv}_{1\times1}(F_t)+\operatorname{Downsample}(m_{mem})\right)\right)') + t(
        '<div class="worked-example"><p>L = 1 时，写入编码器的 mask 数值约为 4.621，而不是 1 或 0.731。它与图像特征融合后成为 64 通道记忆，不是简单存一张彩色 mask。</p></div><p>代码另有可配置的提示 mask 二值化 / 非重叠处理，及目标缺席时的空间 embedding。主配置 <code>num_maskmem=7</code>：只有一个初始化提示帧时，典型路径包括该条件帧及至多六个近期非条件帧；多次提示帧、记忆选择和目标指针另有规则，不能笼统说“永远只记最近七帧”。</p><h3>为什么错误可能影响后续帧</h3><p>下面是用于理解机制的局部近似，不是项目已经测出的梯度结果。固定输入画面与提示，并只写出 mask 经记忆影响下一帧的这一路径：</p>',
        '<div class="worked-example"><p>For L = 1, the mask value entering memory encoding is approximately 4.621, not 1 or 0.731. Fusion with image features produces 64-channel memory; this is not merely storing a colored mask.</p></div><p>The code also supports configurable prompt-mask binarization / non-overlap handling and spatial embeddings for absent objects. With <code>num_maskmem=7</code> and one initial conditioning frame, a typical path uses that frame plus up to six recent non-conditioning frames. Additional conditioning frames, memory selection and object pointers have separate rules; “it always remembers only the last seven frames” is inaccurate.</p><h3>Why an error may affect later frames</h3><p>This is a local approximation for understanding the mechanism, not a measured project gradient. Hold images and prompts fixed and isolate the path from a mask through memory into the next prediction:</p>') +
        e(r'L_t=f_\theta(I_t,B_t,M_{t-1}),\qquad M_t=g_\theta(I_t,L_t)') +
        e(r'\Delta L_{t+1}\approx\frac{\partial f}{\partial M}\frac{\partial g}{\partial L}\Delta L_t') + t(
        '<p>若错误 mask 被编码进记忆，可能影响下一帧的注意力与分割；也可能被新图像或提示纠正。离散记忆选择等步骤使系统并非处处光滑，不能据此断言误差必然放大。</p><p><strong>这与 RNN 梯度消失不同：</strong>RNN 例子关注训练时反传梯度的长链；这里主要关注冻结权重推理中的状态污染。权重 θ 没有因为看了下一帧就被训练。</p><p>SAM2Long 已研究多路径记忆选择。其完整视频后的最优路径选择与严格在线处理不同；不能把“研究记忆误差”直接称为新发明，也不能忽略延迟差异直接比较。</p>',
        '<p>A wrong mask encoded into memory can affect subsequent attention and segmentation, but new image evidence or prompts may also correct it. Discrete memory selection makes the full system nonsmooth; this approximation does not prove that errors must grow.</p><p><strong>This differs from vanishing gradients in RNNs:</strong> that example concerns long backpropagation chains during training; here the concern is inference-state contamination with frozen weights. Seeing another frame does not train θ.</p><p>SAM2Long already studies multi-path memory selection. Its final whole-video path selection differs from strictly online processing; studying memory errors is not automatically novel, and comparisons must account for latency.</p>') +
        refs(source("sam", "sam2/modeling/sam2_base.py", "_encode_new_memory / _prepare_memory_conditioned_features"), source("sam", "sam2/modeling/memory_encoder.py", "MemoryEncoder.forward"), link("https://arxiv.org/abs/2410.16268", "SAM2Long")), "chapter-4")

    add("wrapper", ("从模型到完整系统：B0 封装", "From model to system: the B0 wrapper"), t(
        '<p class="status-note">以下是 proposal 的待实现流程，不是当前教学视频脚本已具有的功能。当前视频只在第一帧初始化。</p><p>在周期性发现帧，YOLO 给出框和类别；将已有 SAM mask 的外接框与同类别新检测匹配。只有符合存活 / 保留规则的目标才有资格参与：</p>',
        '<p class="status-note">This is the proposed implementation, not functionality already present in the teaching script. The current video initializes objects only on the first frame.</p><p>At periodic discovery frames, YOLO supplies boxes and classes. Match each existing SAM mask bounding box to same-class detections, subject to active / retained-track eligibility:</p>') +
        e(r'C_{ij}=\begin{cases}1-\operatorname{IoU}(\operatorname{bbox}(m_i),D_j),&\text{eligible, same class}\\+\infty,&\text{otherwise}\end{cases}') + t(
        '<p>采用一对一匹配与验证集选定门槛；匹配目标更新框提示，接受的未匹配检测创建新 ID，丢失目标按保留规则处理。空 mask 如何匹配、何时退休、刷新间隔都要显式规定。这里的 box IoU 关联不是最终评分时的 mask IoU。</p><p>类别与新 ID 来自封装，不是 SAM 自动识别身份。自动 B0 不接收 ByteTrack ID 或真实标注提示。独立的受控恢复实验允许当前帧参考框与固定目标路由，其结果与自动系统分开报告。</p>',
        '<p>Use one-to-one assignment with a validation-selected threshold. Matched objects receive updated box prompts; accepted unmatched detections create new IDs; lost objects follow a retention policy. Empty-mask handling, retirement and refresh intervals must be explicit. This association box IoU differs from evaluation mask IoU.</p><p>Classes and new IDs come from the wrapper, not automatic identity recognition by SAM. Automatic B0 receives neither ByteTrack IDs nor ground-truth prompts. Separate controlled recovery experiments permit current-frame reference boxes and fixed target routing, with results reported apart from automatic-system scores.</p>') +
        '<p>' + link(f"{home}#chapter-7", t("查看与最新版 proposal 对齐的实验条件", "See experimental conditions aligned with the current proposal")) + '</p>', "chapter-7")

    add("metrics", ("评价：IoU、IDF1、HOTA 与 AP", "Evaluation: IoU, IDF1, HOTA and AP"), t(
        '<p>先对齐原始坐标与类别，并处理数据集的可见性、忽略区域和有效帧。标注不是模型推理输入。</p><h3>IoU：像素集合</h3>',
        '<p>First align original coordinates and classes, and apply dataset rules for visibility, ignored regions and valid frames. Ground truth is not an inference input.</p><h3>IoU: pixel sets</h3>') +
        e(r'\operatorname{IoU}(P,G)=\frac{|P\cap G|}{|P|+|G|-|P\cap G|}') + t(
        '<p>这里的 P、G 是前景像素集合。双方都空时按评估器的有效目标规则处理，不自行算成满分。只统计成功匹配目标的平均 IoU 会隐藏漏检。</p><h3>IDF1：整段视频的身份分配</h3><p>先统计每对真实身份 g、预测身份 p 在多少有效帧中满足同类别与 IoU ≥ 0.5，得到潜在对应次数 n_gp。整段视频做带虚拟未匹配节点的全局一对一身份分配，最大化正确身份出现次数，而不是复用任意一种逐帧匹配。</p>',
        '<p>P and G are foreground pixel sets. Two empty masks follow evaluator validity rules; do not invent a perfect score. Averaging IoU only over successful matches hides misses.</p><h3>IDF1: whole-video identity assignment</h3><p>For each true ID g and predicted ID p, count eligible same-class frame pairs meeting IoU ≥ 0.5, giving potential correspondence counts n_gp. A global one-to-one identity assignment with dummy unmatched nodes maximizes correct identity occurrences over the sequence. It does not reuse an arbitrary framewise assignment.</p>') +
        e(r'IDFP=N_{pred}-IDTP,\qquad IDFN=N_{gt}-IDTP') +
        e(r'IDF1=\frac{2IDTP}{2IDTP+IDFP+IDFN}') + t(
        '<p class="variables">N_pred / N_gt 是目标在各帧的有效出现总数，不是像素数。预测 ID 叫 7、标注叫 A 并不构成错误；重要的是一对一身份关系。</p><h3>HOTA：关联的交并比</h3><p>在给定重合门槛 α 下，令 n_gp 为实际匹配到该身份对的次数；n_g、n_p 是两个身份的全部有效出现次数（含未匹配出现）：</p>',
        '<p class="variables">N_pred / N_gt count valid object-frame occurrences, not pixels. Predicted ID 7 and ground-truth ID A can be perfectly correct: the one-to-one relationship matters, not the names.</p><h3>HOTA: association as a Jaccard score</h3><p>At overlap threshold α, let n_gp count actual matched occurrences of that identity pair; n_g and n_p count all valid occurrences of each identity, including unmatched ones:</p>') +
        e(r'\operatorname{DetA}_\alpha=\frac{TP}{TP+FP+FN}') +
        e(r'\operatorname{AssA}_\alpha=\frac{1}{TP}\sum_{g,p}\frac{n_{gp}^2}{n_g+n_p-n_{gp}}') +
        e(r'\operatorname{HOTA}_\alpha=\sqrt{\operatorname{DetA}_\alpha\operatorname{AssA}_\alpha},\qquad \operatorname{HOTA}=\frac{1}{19}\sum_{\alpha\in\{0.05,0.10,\ldots,0.95\}}\operatorname{HOTA}_\alpha') + t(
        '<p>TP 为 0 等边界情况由评估器处理。先逐阈值开方再平均，不能先把 DetA、AssA 平均后开方。AssA 的平方项来自“每个 TP 的关联得分”按同一身份对出现次数加权。</p><div class="worked-example"><p>一只狗十帧 mask 完美，前五帧 ID 7，后五帧 ID 8：IDTP = 5，IDFP = IDFN = 5，IDF1 = 0.5。HOTA 中 TP = 10、DetA = 1，两个身份对各 n_gp = 5，AssA = (25/10 + 25/10)/10 = 0.5，HOTA ≈ 0.707。所有 mask IoU 为 1，因此 19 个门槛结果相同。</p></div><details><summary>正式 HOTA 的逐帧匹配还用了全局对齐</summary><p>TrackEval 先从整段序列的相似度构建全局对齐权重 A_gp，再在每帧最大化 A_gp × 相似度的一对一分配，最后按 α 过滤。因此不能只写一个逐帧贪心 IoU 匹配器就称为标准 HOTA。</p>',
        '<p>The evaluator handles boundary cases such as TP = 0. Take the square root per threshold before averaging. The squared count in AssA results from weighting each pair score by its number of true positives.</p><div class="worked-example"><p>One dog has perfect masks for ten frames: ID 7 for five frames, ID 8 for five. IDTP = 5, IDFP = IDFN = 5, so IDF1 = 0.5. For HOTA, TP = 10 and DetA = 1. Both identity pairs have n_gp = 5: AssA = (25/10 + 25/10)/10 = 0.5; HOTA ≈ 0.707. With every mask IoU equal to one, all 19 thresholds agree.</p></div><details><summary>Formal HOTA matching also uses global alignment</summary><p>TrackEval constructs global alignment weights A_gp from similarities across the whole sequence. Framewise one-to-one assignment maximizes A_gp × similarity, then filters matches by α. A framewise greedy-IoU matcher alone is not standard HOTA.</p>') +
        e(r'\widetilde s_{gp,t}=\frac{s_{gp,t}}{\sum_{g^\prime}s_{g^\prime p,t}+\sum_{p^\prime}s_{gp^\prime,t}-s_{gp,t}}') +
        e(r'P_{gp}=\sum_t\widetilde s_{gp,t},\qquad A_{gp}=\frac{P_{gp}}{n_g+n_p-P_{gp}}') + t(
        '<p>零分母使用实现中的数值保护。上式 P_gp 是潜在匹配量，不是前面实际匹配次数 n_gp。</p></details><h3>AP 与速度是另外的维度</h3><p>独立 YOLO 检测 / 分割诊断可报告 AP：按分数排序，以不同分数门槛产生 precision–recall 曲线，积分得到 AP；AP50:95 使用 0.50 到 0.95、间隔 0.05 的十个 IoU 门槛。它不检查跨帧身份，因此不能替代 IDF1 / HOTA。</p>',
        '<p>The implementation protects zero denominators numerically. Here P_gp is a potential-match quantity, not the actual matched count n_gp used above.</p></details><h3>AP and speed measure other dimensions</h3><p>Standalone YOLO detection / segmentation diagnostics can report AP: rank predictions by score, sweep score thresholds to form a precision–recall curve, then integrate. AP50:95 uses ten IoU thresholds from 0.50 to 0.95 at 0.05 increments. It does not test identity continuity and cannot replace IDF1 / HOTA.</p>') +
        e(r'\operatorname{Precision}=\frac{TP}{TP+FP},\quad \operatorname{Recall}=\frac{TP}{N_{gt}},\quad FPS=\frac{N_{frames}}{T_{seconds}}') + t(
        '<p>正式评分按统一适配器和官方聚合规则处理多视频 / 类别，不简单平均各视频的 HOTA。计时需固定硬件、精度、输入与解码边界，预热、GPU 同步，三次取中位数。播放器帧率、冷启动日志和模型置信度都不是准确率或正式吞吐量。</p><p class="status-note">主线交互区是上述单目标特例的闭式演示，不是通用 TrackEval。正式数据适配与合成边界用例验证仍待实现。</p>',
        '<p>Use a common adapter and official multi-sequence / class aggregation rules, not a simple average of per-video HOTA values. Timing fixes hardware, precision, input and decoding boundaries, with warmup, GPU synchronization and the median of three runs. Playback frame rate, cold-start logs and model scores are not benchmark accuracy or throughput.</p><p class="status-note">The handbook interactions are closed-form single-object examples, not a general TrackEval implementation. Formal dataset adaptation and synthetic edge-case checks remain to be implemented.</p>') +
        refs(source("eval", "hota.py", "HOTA.eval_sequence / combine_sequences"), source("eval", "identity.py", "Identity.eval_sequence"), link("https://arxiv.org/abs/2009.07736", "HOTA paper"), link("https://arxiv.org/abs/1609.01775", "ID metrics paper")), "chapter-6")

    add("research", ("保留与重置：把干预写成数学定义", "Retain versus reset: define the interventions"), t(
        '<p>统一问题是“新的观察到来后，旧状态如何影响恢复”。ByteTrack 与 SAM 都有历史，但不是同一种状态。先分别比较 A-H/A-R、B-H/B-R，再分析条件和持续时间。</p><h3>A：运动状态</h3><p>在纠正时刻 τ，把同一框转换为观测 z。H 保留预测均值和协方差，正常更新；R 以当前观测初始化四个位置／尺寸分量，四个速度分量为零，协方差使用实现默认值：</p>',
        '<p>The shared question is how old state affects recovery after new evidence arrives. ByteTrack and SAM both use history, but their states differ. Compare A-H/A-R and B-H/B-R separately before interpreting conditions and duration.</p><h3>A: motion state</h3><p>At correction time τ, convert the same box to observation z. H retains the predicted mean and covariance for a normal update. R initializes four location/size components from z, sets four velocities to zero and uses the implementation’s default initialization covariance:</p>') +
        e(r'm_{\tau}^{H}=m_{\tau}^{-}+K_{\tau}(z_{\tau}-Hm_{\tau}^{-}),\quad P_{\tau}^{H}=(I-K_{\tau}H)P_{\tau}^{-}') +
        e(r'm_{\tau}^{R}=\begin{bmatrix}z_{\tau}\\0_4\end{bmatrix},\quad P_{\tau}^{R}=P_{init}(z_{\tau})') + t(
        '<p>这里的矩阵 H 是卡尔曼观测矩阵；上标 H 表示保留组。外部 ID、生命周期规则和权重不变。<code>re_activate()</code> 调用更新，不等于初始化。</p><h3>B：目标视觉状态</h3><p>用 S 表示该目标的提示、视觉记忆与相关推理状态。相同当前图像 I 和框 b 下，保留组与重置组可概括为：</p>',
        '<p>The matrix H is the Kalman observation matrix; superscript H denotes the retain group. External ID, lifecycle rules and weights stay fixed. <code>re_activate()</code> calls an update, not initialization.</p><h3>B: object visual state</h3><p>Let S represent this target’s prompts, visual memory and related inference state. Given the same image I and box b, the two operations can be summarized as:</p>') +
        e(r'S_{\tau}^{H}=\operatorname{Correct}(S_{\tau}^{-},I_{\tau},b_{\tau}),\quad S_{\tau}^{R}=\operatorname{Init}(I_{\tau},b_{\tau})') + t(
        '<p>这是待实现的策略级定义，不是声称只改变单个注意力矩阵。仅清除提示点不等于清除目标历史；全局清空也不能代替目标级重置。相同框并不保证纠正当帧 mask 相同，主要恢复评分从之后开始。</p><h3>比较差值，而不是预设赢家</h3>',
        '<p>This defines the proposed strategies; it does not claim to change only one attention matrix. Clearing prompt points is not clearing target history, and a global reset is not a target-level operation. Identical boxes may yield different masks in the correction frame, so primary recovery scoring starts afterward.</p><h3>Compare paired differences without assuming a winner</h3>') +
        e(r'\Delta M_A(k)=M_{A-H}(\tau+k)-M_{A-R}(\tau+k),\quad \Delta M_B(k)=M_{B-H}(\tau+k)-M_{B-R}(\tau+k)') + t(
        '<p>M 使用预先定义的质量指标。对“越高越好”的指标，正差支持保留，负差支持重置；错误量或时间指标应明确相反的方向。观察差异持续多久，后续观察能否消除它。各系统专属指标不能直接相减排名。</p><p>同一配对的正常输入安排一致；参考框和目标路由只在诊断中由当前标注辅助。之后不追加标注纠正。固定指定 ID，丢失和空输出计失败；按真实标注时刻与视频内汇总分析。最多一项自动策略验证以证据为前提。</p>',
        '<p>M is a predefined quality measure. For higher-is-better scores, positive differences favor retention and negative ones favor reset; error or time measures require the opposite interpretation. Measure how long differences persist and whether subsequent observations erase them. System-specific scores cannot be directly subtracted into a ranking.</p><p>Keep the native input schedule identical within each pair. Current annotations may assist reference boxes and routing only in the diagnostic experiment; provide no subsequent annotation corrections. Fix the designated ID, count missing and empty outputs, and respect actual annotation times and within-video aggregation. At most one automatic-policy validation follows only if supported by evidence.</p>') +
        refs(source("yolo", "trackers/utils/kalman_filter.py", "Kalman initialization / update"), source("sam", "sam2/sam2_video_predictor.py", "SAM state and correction")) +
        '<p>' + link(f'experiments{".en" if language == "en" else ""}.html#walkthrough', t("逐步走一遍四组实验", "Walk through the four-group experiment")) + ' · ' + link(f'research{".en" if language == "en" else ""}.html#inspiration', t("技术脉络与已有研究", "Technical history and prior research")) + '</p>', "chapter-7")

    return (t("数学与实现", "Mathematics and Implementation"),
            t('<p class="lead">按模型查阅：输入张量 → 数值运算 → 输出 → 可检验的失败机制。</p><p class="small">长公式可在框内左右滑动。</p>', '<p class="lead">Reference by model: input tensors → numeric operations → outputs → testable failure mechanisms.</p><p class="small">Long equations scroll horizontally inside their boxes.</p>'), pages)
