"""Bilingual experiment walkthrough: protocol diagrams, never measured results."""
from .study import link, pick, section, source


def content(language, home):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    pages = []

    def add(key, title, body):
        label = t(*title)
        pages.append((key, label, section(key, label, body)))

    def card(tag, title, text, classes=""):
        return f'<div class="protocol-card {classes}"><span class="protocol-tag">{tag}</span><h3>{title}</h3><p>{text}</p></div>'

    def table(headers, rows, key):
        return f'<div class="table-wrap"><table id="{key}"><thead><tr>' + ''.join(f'<th>{x}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'

    add("logic", ("一条研究主线，三个层次", "One research question, three levels"),
        '<p>' + t('新的目标观察到来时，过去的状态是在帮助恢复，还是延续错误？先测完整系统，再在系统内部控制历史处理，最后分析局部发现能否改善自动流程。', 'When a new object observation arrives, does past state help recovery or carry errors forward? Measure complete systems, control history handling within each system, then test whether a supported finding can improve the automatic pipeline.') + '</p><p>' + link('program'+suffix+'.html', t('先看实验步骤对应的文件、函数与真实结果 →', 'See experiment steps, files/functions and real evidence first →')) + '</p>' +
        '<ol class="protocol-flow" aria-label="' + t('研究流程', 'Research flow') + '">' +
        '<li>' + card('01', t('A0 / B0 自动基线', 'A0 / B0 automatic baselines'), t('比较完整质量与成本；定位观察、关联及状态更新问题。', 'Compare complete-system quality and cost; locate observation, association and state-update failures.')) + '</li>' +
        '<li>' + card('02', t('四组受控恢复', 'Four controlled recovery groups'), t('同一事件、同一纠正框；分别比较 A-H / A-R 与 B-H / B-R。', 'One event and correction box; compare A-H / A-R and B-H / B-R separately.')) + '</li>' +
        '<li>' + card('03', t('解释规律与验证', 'Explain patterns and validate'), t('观察差异出现与消失的过程。有证据时，最多验证一项自动策略。', 'Study when differences arise and disappear. If evidence supports it, validate at most one automatic policy.')) + '</li></ol>' +
        '<p class="status-note">' + t('本页保留已批准的实验设计，不展示虚构结果。四组开发冒烟检查已跑通；修正后的真实案例与下一批事件筛选见程序地图。按钮仅切换说明步骤。', 'This page preserves the approved design without invented outcomes. Four-group development smoke tests ran; see the program map for corrected real cases and the next candidate set. Controls only navigate the explanation.') + '</p><p>' + link('program'+suffix+'.html#recovery', t('修正后案例 → 下一批实验怎么选', 'Corrected cases → selecting the next experiment')) + '</p>')

    add("baselines", ("A / B 保留各自的自动流程", "A / B retain their automatic pipelines"),
        '<div class="protocol-grid">' +
        card('A0', 'YOLO11s-seg + ByteTrack', t('每帧检测 → 按类别隔离的 ByteTrack → 带视频内唯一 ID 的 YOLO 掩码。历史主要包含运动估计、不确定性与轨迹状态。', 'Per-frame detections → class-separated ByteTrack → YOLO masks with video-wide unique IDs. History includes motion estimates, uncertainty and track state.'), 'system-a') +
        card('B0', 'YOLO + SAM 2.1 Hiera Tiny', t('定期检测 → 同类别 box IoU 匹配与提示刷新 → SAM 掩码传播。历史包含目标相关的视觉推理状态。', 'Periodic detections → same-category box-IoU matching and prompt refresh → SAM mask propagation. History includes object-specific visual inference state.'), 'system-b') + '</div>' +
        '<p>' + t('两套系统都使用历史。A0/B0 的不同还包括检测频率、掩码来源和关联方式，因此完整系统分数不能单独证明哪类记忆更优。两套系统都冻结 YOLO 和 SAM 权重。', 'Both systems use history. A0/B0 also differ in detector frequency, mask source and association, so their scores cannot isolate which type of memory is better. YOLO and SAM weights stay fixed throughout the core experiments.') + '</p>' +
        table([t('先检查', 'Check first'), t('例子', 'Example'), t('对恢复实验意味着什么', 'Implication for recovery')], [
            [t('观察', 'Observation'), t('目标没有合格检测', 'No eligible object detection'), t('缺少新信息，不能仅归咎于旧记忆。', 'Missing new information is not solely a history problem.')],
            [t('关联 / 生命周期', 'Association / lifecycle'), t('正确检测创建了新 ID，旧轨迹已删除', 'A correct detection creates a new ID; the old track was deleted'), t('未送达正确目标，或已经没有状态可以保留。', 'The observation is misrouted, or no old state remains to retain.')],
            [t('状态更新与传播', 'State update and propagation'), t('目标收到纠正，之后仍然偏离', 'The correct target receives a correction but subsequently drifts'), t('比较历史保留与重置的核心场景。', 'A central case for retaining versus resetting history.')],
        ], 'failure-stages'))

    steps = [
        (t('共享前史', 'Shared prefix'),
         '<p>' + t('选定同一视频、目标和纠正时刻 τ。先分别运行 A0 与 B0 到 τ 之前，再复制各自的状态。A 的两条分支来自同一个 A 状态；B 的两条分支来自同一个 B 状态，A 与 B 不共享内部状态。', 'Fix the video, target and correction time τ. Run A0 and B0 independently to just before τ, then copy each state. Both A branches start from the same A state, and both B branches from the same B state; A and B do not share internal state.') + '</p>' +
         '<div class="state-fork"><div class="fork-source system-a">A0 · τ−</div><div class="fork-targets"><span>A-H</span><span>A-R</span></div><div class="fork-source system-b">B0 · τ−</div><div class="fork-targets"><span>B-H</span><span>B-R</span></div></div>' +
         '<p>' + t('主要四组比较要求双方仍有可操作的目标状态。若轨迹已删除，不虚构“保留”分支；另报无法进入实验的事件数量及比例。', 'The primary four-group comparison requires retained, operable target state in both systems. Do not fabricate a retained branch for deleted tracks; report the count and proportion of ineligible events separately.') + '</p>'),
        (t('同一纠正', 'Same correction'),
         '<div class="correction-box"><span class="protocol-tag">τ</span><strong>' + t('一个框 · 指定同一目标 · 每组只消费一次', 'One box · same designated target · consumed once per group') + '</strong></div>' +
         '<p>' + t('分别使用实际 YOLO 框和当前帧标注生成的参考框。每一次成对比较固定坐标、来源、时刻及目标对应关系。参考框不是完美 mask，也不保证正确分割。', 'Study actual YOLO boxes and reference boxes derived from current-frame annotations separately. Each paired comparison fixes coordinates, source, time and target routing. A reference box is not a perfect mask and does not guarantee correct segmentation.') + '</p>' +
         '<p>' + t('<strong>H 组也收到纠正。</strong>不能把“保留但不纠正”与“重置并纠正”当作历史处理的公平比较。未额外纠正的 A0/B0 轨迹另作参考。纠正帧不能再被同帧正常检测重复更新。', '<strong>H receives the correction too.</strong> Comparing uncorrected retention against corrected reset confounds the intervention. Uncorrected A0/B0 trajectories are separate references. Do not update again with the same normal detection in the correction frame.') + '</p>' +
         '<p class="status-note">' + t('人为固定目标对应关系只存在于机制诊断，回答“收到纠正后能否恢复”。它不表示自动系统已解决重识别。', 'Manually fixed target routing belongs only to mechanism diagnosis: can the system recover once a correction arrives? It does not establish automatic re-identification.') + '</p>'),
        (t('四组更新', 'Four updates'),
         '<div class="protocol-grid four-branches">' +
         card('A-H', t('保留运动状态', 'Retain motion state'), t('继承位置、速度和协方差，用纠正框执行一次正常卡尔曼更新。', 'Retain position, velocity and covariance; perform one normal Kalman update with the correction box.'), 'system-a') +
         card('A-R', t('重建运动状态', 'Reinitialize motion state'), t('纠正框初始化位置与尺寸；速度为零；协方差使用默认初始化规则。', 'Initialize location and size from the box, set velocity to zero and use the default initialization covariance.'), 'system-a') +
         card('B-H', t('保留视觉历史', 'Retain visual history'), t('对已有目标追加相同的纠正框提示，并延续它的历史推理状态。', 'Add the same corrective box to the existing target and retain its historical inference state.'), 'system-b') +
         card('B-R', t('重建视觉状态', 'Reinitialize visual state'), t('清除该目标旧提示、视觉记忆及相关状态，再用相同框初始化。', 'Clear this target’s old prompts, visual memory and related state, then initialize from the same box.'), 'system-b') + '</div>' +
         '<p>' + t('四组保留外部目标 ID；在各自 H/R 配对内，纠正后的存活状态与生命周期处理相同。A/B 保留各自原生规则，不主动重置其他目标。重置不会更新神经网络权重，也不是替目标重新判定身份。', 'All groups preserve the external target ID. Within each H/R pair, post-correction live/lifecycle handling is identical; A and B retain their own native rules. Other targets are not intentionally reset. Resetting neither updates neural weights nor determines the target’s identity again.') + '</p>'),
        (t('继续正常输入', 'Resume native inputs'),
         '<div class="protocol-grid">' +
         card('A-H / A-R', t('后续逐帧检测相同', 'Same subsequent framewise detections'), t('继续向 ByteTrack 提供预定的检测结果。两组自行预测与关联；关联分歧是观察结果，不强行修成一致。', 'Continue the scheduled detection stream. Both branches predict and associate on their own; association divergence is an outcome, not something to correct away.'), 'system-a') +
         card('B-H / B-R', t('后续自动刷新安排相同', 'Same subsequent automatic refresh schedule'), t('继续预先锁定的自动提示安排与掩码传播。观察窗口不追加人工或标注纠正。', 'Continue the locked automatic prompt schedule and mask propagation. Add no further human or annotation-based corrections in the observation window.'), 'system-b') + '</div>' +
         '<p>' + t('配对一致指同一系统内 H/R 的输入安排相同。A 与 B 保留各自的正常检测频率；跨系统比较必须考虑这种差异。只向前处理，不用未来提示改写过去预测。', 'Paired consistency means identical input schedules within each H/R pair. A and B keep their native detector frequencies, which must be considered in cross-system interpretation. Process forward only; future prompts must not rewrite scored past outputs.') + '</p>'),
        (t('分析恢复过程', 'Analyze recovery'),
         '<div class="paired-comparisons"><div><strong>A-H ↔ A-R</strong><span>' + t('运动预测、正确关联、持续跟随', 'Motion prediction, correct association, sustained following') + '</span></div><div><strong>B-H ↔ B-R</strong><span>' + t('mask 质量、漂移、持续跟随', 'Mask quality, drift, sustained following') + '</span></div></div>' +
         '<p>' + t('先看各自的保留−重置差值与逐时曲线，再比较收益出现的条件和持续时间。共同跟随指标中，正差表示保留更好；负差表示重置更好。不同系统专属指标不能直接相减排名。', 'First inspect within-system retain-minus-reset differences and time curves, then compare their conditions and duration. For shared following-quality measures, positive differences favor retention and negative ones favor reset. System-specific measures cannot be directly subtracted into a ranking.') + '</p>' +
         '<p>' + t('固定指定目标的外部 ID；不逐帧改挑最像标注的输出。排除被直接纠正的 τ 帧；目标可见时，丢失或空输出计失败。按真实时间与标注时刻报告，不把稀疏标注点叫作连续视频帧。', 'Keep the designated external target ID fixed; never choose whichever output best matches ground truth anew each frame. Exclude the directly corrected frame τ. Visible-target misses or empty outputs count as failures. Report real time and annotated instants, not sparse labels as consecutive video frames.') + '</p>' +
         '<p class="status-note">' + t('恢复曲线需要真实实验生成；这里不给预设胜者或虚构曲线。一次实验无明显收益，也可以排除不成立的解释。', 'Recovery curves require actual experiments; no winner or curve is fabricated here. A lack of benefit can still rule out an unsupported explanation.') + '</p>'),
    ]
    controls = '<div id="event-controls" hidden><div class="protocol-step-buttons" role="group" aria-label="' + t('选择说明步骤', 'Choose a protocol step') + '">' + ''.join(f'<button type="button" data-event-step="{i}" aria-controls="event-panel-{i}">{i + 1}. {label}</button>' for i, (label, _) in enumerate(steps)) + '</div><div class="controls"><button type="button" id="event-prev">' + t('上一步', 'Previous') + '</button><output id="event-progress" aria-live="polite"></output><button type="button" id="event-next">' + t('下一步', 'Next') + '</button></div></div>'
    panels = ''.join(f'<article id="event-panel-{i}" class="event-panel" data-event-panel="{i}" aria-labelledby="event-heading-{i}"><h3 id="event-heading-{i}">{i + 1}. {label}</h3>{body}</article>' for i, (label, body) in enumerate(steps))
    add("walkthrough", ("走一遍受控事件", "Walk through one controlled event"), '<p>' + t('这是一份操作流程说明。切换五个步骤，看哪些输入保持相同，哪些状态发生变化。', 'This is a protocol walkthrough. Move through five steps to see which inputs are shared and which state changes.') + '</p>' + controls + '<div id="event-walkthrough">' + panels + '</div><noscript><p class="small">' + t('JavaScript 已关闭：以上五个步骤完整展开，仍可依次阅读。', 'JavaScript is disabled: all five steps remain expanded and readable.') + '</p></noscript>')

    add("matrix", ("四组实验：保持什么、改变什么", "Four groups: what stays and what changes"),
        table([t('组别', 'Group'), t('历史处理', 'History handling'), t('改变的状态', 'Changed state')], [
            ['A-H', t('保留并纠正', 'Retain and correct'), t('正常更新位置、速度与协方差', 'Normal position, velocity and covariance update')],
            ['A-R', t('重新初始化并纠正', 'Reinitialize and correct'), t('当前框初始化；零速度；默认初始协方差', 'Current-box initialization; zero velocity; default initial covariance')],
            ['B-H', t('保留并纠正', 'Retain and correct'), t('历史保留，加入新框提示', 'History retained, new box prompt added')],
            ['B-R', t('重新初始化并纠正', 'Reinitialize and correct'), t('目标旧推理状态清除，再用同框初始化', 'Old target inference state cleared, initialized with the same box')],
        ], 'recovery-groups') +
        '<p>' + t('<strong>共同固定：</strong>模型权重、视频和事件、纠正框及目标对应关系、外部 ID。<strong>在各自 H/R 配对内固定：</strong>纠正后的生命周期规则与后续观测安排；A/B 仍保留各自原生规则。每个分支必须隔离可变状态，不能让一个分支的更新泄漏到另一个。', '<strong>Hold fixed:</strong> weights, video and event, correction box and routing, external ID. <strong>Within each H/R pair:</strong> fix post-correction lifecycle rules and subsequent observation schedules; A and B keep their own native rules. Isolate mutable branch state so one update cannot leak into another.') + '</p>' +
        '<details><summary>' + t('实现时最容易混淆的操作', 'Operations that are easy to confuse') + '</summary><ul><li>' + t('ByteTrack 的 <code>re_activate()</code> 仍进行卡尔曼更新，继承历史；名字中的“重新激活”不代表重新初始化。A-R 需要显式执行目标级初始状态构造。', 'ByteTrack <code>re_activate()</code> performs a Kalman update and inherits history. Reactivation is not reinitialization; A-R needs explicit target-level initial-state construction.') + '</li><li>' + t('SAM 的 <code>clear_old_points=True</code> 只控制该帧的提示点，不等于清除完整目标历史。全局 <code>reset_state()</code> 又可能影响所有目标，不能直接冒充目标级操作。', 'SAM <code>clear_old_points=True</code> controls that frame’s prompt points, not all target history. A global <code>reset_state()</code> can affect every object and is not a substitute for target-level resetting.') + '</li><li>' + t('纠正帧必须真正参与之后的传播；检查提示帧是否作为固定的 conditioning 输出保留，记录自动清理历史的配置。相同外部框不保证两组纠正帧 mask 相同。', 'The correction must actually affect subsequent propagation. Verify conditioning-frame retention and record automatic memory-clearing settings. Identical external boxes need not produce identical correction-frame masks.') + '</li></ul></details>' +
        '<p class="source-note">' + source('yolo', 'trackers/byte_tracker.py', 'ByteTrack v8.3.221') + ' · ' + source('yolo', 'trackers/utils/kalman_filter.py', 'Kalman initialization / update') + ' · ' + source('sam', 'sam2/sam2_video_predictor.py', 'SAM video predictor') + '</p>')

    add("readouts", ("如何解释结果", "How to interpret the results"),
        table([t('层次', 'Level'), t('观察量', 'Readouts'), t('能回答什么', 'What it answers')], [
            [t('完整 A0/B0', 'Complete A0/B0'), 'mask HOTA · DetA · AssA · IDF1 · FPS · VRAM', t('自动系统的整体质量与成本', 'Automatic-system quality and cost')],
            [t('共同恢复指标', 'Shared recovery measures'), t('定位、正确跟随比例、恢复时间、持续时长、复发', 'Localization, correct-following fraction, recovery time, duration, recurrence'), t('同一次纠正之后，谁继续跟对了指定目标', 'Whether each branch continues following the designated target')],
            [t('A 内部诊断', 'A diagnostics'), t('运动预测框偏差、检测关联、身份错误', 'Motion-box error, detection association, identity errors'), t('运动状态是否帮助之后的关联', 'Whether motion state helps subsequent association')],
            [t('B 内部诊断', 'B diagnostics'), t('mask IoU、漂移、错误前景', 'Mask IoU, drift, false foreground'), t('视觉状态是否帮助之后的掩码传播', 'Whether visual state helps mask propagation')],
        ], 'readout-roles') +
        '<p>' + t('阈值、持续成功的标注时刻数及观察窗口先在开发／验证数据上确定。每段视频先汇总事件，再汇总视频，避免多个相关事件被当成独立样本。', 'Choose thresholds, required successful annotation instants and observation windows on development/validation data. Aggregate events within each video before summarizing videos, rather than treating correlated events as independent samples.') + '</p>' +
        '<h3>' + t('有价值的结果不只是一种策略获胜', 'Useful findings need not identify one universal winner') + '</h3><ul><li>' + t('重置的收益只在某些运动变化或漂移事件中出现：说明适用条件，而不是普遍规则。', 'Reset benefits appear only after certain motion changes or drift: identify conditions rather than a universal rule.') + '</li><li>' + t('差异很快被后续观察消除：说明历史影响的持续时间有限。', 'Subsequent observations quickly erase differences: history has a limited duration of influence.') + '</li><li>' + t('局部恢复改善但完整 IDF1 未提高：继续检查提示路由、删除轨迹和其他目标的影响。', 'Local recovery improves but complete-system IDF1 does not: inspect routing, deleted tracks and effects on other objects.') + '</li><li>' + t('两种策略差不多：如实报告，并检查状态干预确实生效。', 'Strategies perform similarly: report it and verify that the state intervention actually took effect.') + '</li></ul>' +
        '<p>' + t('纠正前真实 IoU 只是历史可靠性的诊断代理，不是内部记忆质量本身，也不能输入自动策略。自然场景分组中的相关性不能单独证明因果。', 'Pre-correction ground-truth IoU is only a diagnostic proxy for history reliability, not internal memory quality itself, and cannot drive the automatic policy. Natural-scene grouping alone does not establish causality.') + '</p>' +
        '<p class="source-note">' + source('eval', 'hota.py', 'TrackEval HOTA') + ' · ' + source('eval', 'identity.py', 'TrackEval IDF1') + ' · ' + link(f'{home}#chapter-6', t('返回指标课程', 'Return to the metrics lesson')) + '</p>')

    add("scope", ("数据、范围与交付", "Data, scope and deliverables"),
        '<p>' + t('YouTube-VIS 2021 通过 SlotCurri 的 Google Drive 预处理版本获取。使用带标注的导出部分：其文档中的训练导出仅含视频，validation 导出含实例 mask，属于原始带标注训练数据的内部划分。目标为 person、dog、cat、horse、car 五类的 200 段视频，须先核验标注和类别覆盖。确认后，随机种子 550，按完整视频划分 120 开发、40 验证、40 保留评估。同源片段同组，先划分再抽帧。', 'Obtain YouTube-VIS 2021 through SlotCurri’s preprocessed Google Drive release. Use the annotated export: its documented training export is video-only, while the validation export contains instance masks and comes from an internal split of the original labeled training data. Target 200 videos covering person, dog, cat, horse and car, subject to label and category coverage. Once confirmed, use seed 550 for whole-video splits of 120 development, 40 validation and 40 held-out evaluation. Related clips stay together; split before frame sampling.') + '</p>' +
        '<p>' + t('本地审计已确认 300 段带标注视频，其中 226 段包含五个目标类别。数量足够，但类别不均衡；正式 120/40/40 划分还需约束调整，不能直接使用 seed 550 初始结果。原始时间戳未附带，恢复时长应先按导出步数统计，不可直接换算成秒。', 'The local audit confirms 300 annotated videos, with 226 containing the five target classes. Counts are sufficient but imbalanced. The formal 120/40/40 split needs coverage adjustments rather than accepting the initial seed-550 output. Original timestamps are absent: report recovery duration in exported steps unless source timing is recovered.') + '</p>' +
        '<p>' + link(f'dataset{suffix}.html', t('数据说明、逐帧真实样本与准备约束', 'Data guide, real annotated frames and preparation constraints')) + '</p>' +
        '<ol><li>' + t('小规模预实验先验证干预代码、事件覆盖和标注时间间隔。', 'Use a small pilot to verify intervention code, event coverage and annotation timing.') + '</li><li>' + t('锁定事件选择、恢复标准及输入安排后，再查看保留评估结果。', 'Lock event selection, recovery definitions and input schedules before inspecting held-out results.') + '</li><li>' + t('交付基线、四组配对结果、恢复曲线、失败案例和条件解释。有证据时最多增加一项自动策略验证；没有明显收益同样报告。', 'Deliver baselines, four-group paired results, recovery curves, failures and conditional explanations. Add at most one automatic-policy validation if supported; report no-benefit outcomes too.') + '</li></ol>' +
        '<p>' + link(f'{home}#proposal', t('阅读与下载最新版中英文 proposal', 'Read and download the current bilingual proposal')) + ' · ' + link(f'math{suffix}.html#research', t('查看状态更新的数学定义', 'Mathematical definitions of state updates')) + '</p>')

    add("sources", ("从哪些研究出发", "Research starting points"),
        '<ul class="source-list">' + ''.join('<li>' + link(url, name) + '<p>' + t(zh, en) + '</p></li>' for url, name, zh, en in [
            ('https://arxiv.org/abs/2110.06864', 'ByteTrack', '两阶段检测关联与轨迹维护。', 'Two-stage detection association and track maintenance.'),
            ('https://arxiv.org/abs/2203.14360', 'OC-SORT', '遮挡和非线性运动下，观察如何修正累积的运动状态误差。', 'How observations correct accumulated motion-state errors under occlusion and nonlinear motion.'),
            ('https://arxiv.org/abs/2408.00714', 'SAM 2', '提示、视觉记忆与视频掩码传播。', 'Prompts, visual memory and video-mask propagation.'),
            ('https://arxiv.org/html/2410.16268v3', 'SAM2Long', '通过有限候选历史路径和记忆选择应对误差传播。整段最佳路径选择不等于零延迟在线输出。', 'Bounded candidate history paths and memory selection address error propagation. Whole-sequence path selection is not zero-latency online output.'),
            ('https://arxiv.org/html/2411.11922v2', 'SAMURAI', '将运动一致性用于候选掩码与视觉记忆选择。', 'Motion consistency supports candidate-mask and visual-memory selection.'),
        ]) + '</ul><p>' + t('这些是机制依据和相关工作，不是本项目必须新增复现的五套系统。', 'These are mechanistic references and related work, not five additional systems required for reproduction.') + '</p>')

    return (t('实验设计：历史状态与错误恢复', 'Experiment Design: Historical State and Error Recovery'),
            '<p class="lead">' + t('先看 A/B 自动流程，再走一遍相同纠正条件下的四组实验，最后理解我们准备如何读结果。', 'Start with the automatic A/B pipelines, walk through four groups under the same correction, then see how the results will be interpreted.') + '</p>', pages)
