SHELVED OPTIONAL STUDY -- 人为历史污染探索，2026-10-21搁置

用户要求：先隔离人为污染分析，后期确实需要再考虑纳入。

这不是原proposal或原16段H/R设计的组成部分。当前主线只包括：
修正版A0/B0基线；原生历史上的同框H/R；骑手/猫长窗口；单次刷新消融；
后来另行授权的自然持续失败补充。隔离内容不进入这些实验的任何主线评分。

隔离内容
  source/history_check.py.txt
  source/history_check_state.py.txt
  source/history_check_audit.py.txt
  source/history_check_report.py.txt
  tests/test_history_check.py.txt
  HISTORY_CHECK_GUIDE.txt

代码与测试保存为.py.txt，保持内容不变，不能被当前Python包导入或默认pytest收集。
其中11项可选检查不再计入主线测试数。原先90项通过属于当时全体检查，
不应与隔离后的主线79项测试数混淆。

原始结果保留在原路径，避免破坏plan.json、源码快照和相对视频链接：
  ../../runs/history-check-four-20261020-3080/
  ../../runs/history-check-four-20261020-analysis/
上述相对路径以experiments/optional_studies/history_pollution为起点时，应上溯两层。
这些目录均为本地忽略的run，不进入当前结果汇总或正式结论。
其中还包含关闭SAM后续刷新/发现/TTL的诊断设置，即使部分分支使用准确框，
也不能摘出当作原生H/R证据使用。整批56分支及其前史审计统一搁置。

如用户以后决定恢复
  先重新审阅实验动机和配置，不自动续跑。
  source/中的四个.py.txt可以原样复制回experiments/tracking_lab/并恢复.py后缀；
  测试可原样复制回experiments/tests/；导读可复制回experiments/。
  不覆盖任何已存在文件；重新测试后才能显式执行。
  原始run/code/中的冻结推理源码仍保持原样，便于核对恢复内容。

这里的搁置不是删除，也不影响原始基线、16段主清单、proposal或学习网站。
