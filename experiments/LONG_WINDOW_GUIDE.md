# 长窗口与单次提示刷新消融

这批继续使用本地 RTX 3080、冻结权重和同步修正版基线，不训练、不连接学校、不改网站、不覆盖旧结果。

**本批结果：**[中文结果解释](runs/recovery-long-20261020-study/RESULTS_ZH.md)。先读结果与视频，再按下表定位代码。主实验为`runs/recovery-long-20261020-3080/`，单次刷新消融为`runs/recovery-long-skip-20261020-3080/`，各自有`-repeat/`完整复跑。

## 先理解实验，而不是先读实现细节

1. **主实验：**同一个骑手事件（2718/person GT1/纠正步14）和猫对照（2689/cat GT2/纠正步20），运行纠正后30个导出步。两种框来源 × 四组H/R × 两个事件 = 16分支。
2. **单独消融：**再运行同样的16分支，仅让SAM的指定目标在下一个预定刷新时刻跳过框提示。骑手跳过15步，猫跳过25步；不是根据H/R的匹配结果分别寻找下一次成功刷新。A分支作为不受SAM开关影响的负对照。
3. **统一读数：**从同一份长预测统计8、20、30步窗口，不能把这些窗口当作三次独立实验。
4. **独立复核：**长实验前8步必须与旧16分支完全一致；消融的A预测必须与主实验完全一致；SAM在跳过时刻之前必须一致。另做完整神经推理复跑，而不只重算保存结果。

## 跳过刷新究竟改了什么

H/R共享一个预定时刻。该时刻仍正常传播、匹配和处理其他目标；若指定目标本应匹配到检测，则消费这项匹配但不给它新框提示，不用检测框覆盖其当前传播框，也不更新score和last_detection。下一次自动刷新恢复正常。没有检测匹配就没有实际提示被删掉；记录`skip_refresh_slot`，但没有`skipped_refresh`，这是零实际干预，不能证明刷新没有影响。

不额外延长生命周期；如果少一次刷新导致更早过期，这属于这一干预在原生规则下的实际后果，应与视觉传播质量分别解释。灰色无纠正基线始终使用正常刷新安排，不能冒充“同样跳过一次”的基线。

## 步骤对应代码

| 实验步骤 | 文件 → 入口 | 看什么 |
| --- | --- | --- |
| 固定样本和参数 | `tracking_lab/defaults/recovery_long_normal.json`、`recovery_long_skip.json` | 唯一实验开关、窗口、阈值、事件 |
| 分叉并运行 | `tracking_lab/recovery.py` → `execute()` | 相同前史、相同框、四组、预定跳过步 |
| 记录ByteTrack实际匹配 | `tracking_lab/association_trace.py` → `observe_assignments()` | 高分、低分、未确认轨迹三个阶段的实际代价矩阵和分配 |
| 执行单步 | `tracking_lab/recovery_engines.py` → `ByteEngine.step()`、`SamEngine.step()` | 运动状态、提示、删除与跳过动作 |
| 逐运行复核与视频 | `tracking_lab/recovery_report.py` → `build()` | 固定ID、一次纠正、重置审计、四组MP4 |
| 跨条件与多窗口汇总 | `tracking_lab/recovery_long_report.py` → `build()` | 旧结果一致性、负对照、实际干预、8/20/30步、刷新时间线 |
| 完整复跑对比 | `tracking_lab/recovery_repeat.py` → `compare()` | 两次新推理的ID、框、mask与恢复曲线 |

关联探针只在单个顺序执行的tracker.update作用域内包装已安装库的函数，使用原数组调用原匹配算法一次后复制日志，并在finally恢复；不编辑site-packages，不改阈值或算法。不用于多线程并发。`assignment_cost`才是实际分配使用的矩阵：高分阶段可融合检测置信度，不能只看原始IoU。全局一对一分配中，“代价低于阈值”不保证该候选最终被选中。

## 看哪些产物

- 每个运行的`visuals/*-four-groups.mp4`与`*-curves.png`：固定目标的四组结果，不是全画面误检评估。
- 汇总的`checkpoint-pairs.csv`：先按事件、框来源、系统、窗口读H/R差值。
- `prompt-timeline.csv`：目标的纠正、刷新、跳过、删除与输出状态。
- `assignment-candidates.csv`：指定ByteTrack ID与候选检测的真实代价、阈值及选择结果；完整竞争轨迹矩阵在每个A分支的`state-trace.json → assignments`。
- `*-refresh-curves.png`：SAM正常H/R与跳过一次H/R的四条曲线。
- `study-verification.json`：兼容性和实际干预检查；`repeat-verification.json`：独立完整复跑。

当前恢复标准仍是开发规则：mask IoU≥0.5，连续3个可见导出步。`recovered=true`仅表示窗口内曾达标，不表示一直正确到窗口末尾；需结合最长正确段、末尾连续正确长度、复发和删除动作。当前帧直接纠正不计入主评分，目标换号不能算恢复。30步不是30秒。

## 手动复现（从experiments目录运行，必须选择新的输出目录）

```powershell
..\.venv\Scripts\python.exe -m tracking_lab.recovery --check --baseline runs/stage1-20261017-sync-verified --config tracking_lab/defaults/recovery_long_normal.json
..\.venv\Scripts\python.exe -m tracking_lab.recovery --baseline runs/stage1-20261017-sync-verified --config tracking_lab/defaults/recovery_long_normal.json --output runs/NEW-long-normal
..\.venv\Scripts\python.exe -m tracking_lab.recovery_report --output runs/NEW-long-normal
..\.venv\Scripts\python.exe -m tracking_lab.recovery --baseline runs/stage1-20261017-sync-verified --config tracking_lab/defaults/recovery_long_skip.json --output runs/NEW-long-skip
..\.venv\Scripts\python.exe -m tracking_lab.recovery_report --output runs/NEW-long-skip
..\.venv\Scripts\python.exe -m tracking_lab.recovery_long_report --normal runs/NEW-long-normal --skip runs/NEW-long-skip --previous runs/recovery-rider-cat-20261017-3080 --output runs/NEW-long-study
```

独立复跑使用相同配置和另一个输出目录，运行各自报告后执行`tracking_lab.recovery_repeat --first 主目录 --second 复跑目录 --write-record`。不要覆盖已完成运行来“更新结果”。所有输出与视频仍在本地忽略目录，未进行Git提交／推送。
