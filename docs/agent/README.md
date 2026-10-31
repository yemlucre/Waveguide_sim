# 理论仿真维护入口

检查日期：2026-10-31。当前维护 `waveguide_sim` Python/RK4 包、光场查看器及对应测试。

- [项目使用说明](../../README.md)
- [从安装到自定义仿真的教程](../tutorial.md)
- [Python/RK4 完整契约](rk4-package.md)：物理模型、单位、坐标、输入输出、采样、稳定性与收敛。
- [能力清单](capabilities.json)：仅1项独立理论能力，agentExposed=false。
- [当前验证说明](../validation.md)：12项测试、收敛、绘图与滑块交互检查，以及本地证据位置。

共享数值方法独立于界面、Agent和设备。功能变化同步维护契约及能力清单，不把理论参数或结果当作实测/设备状态。改计算代码后运行 `simulate-optics.ps1 -Test` 和适用的端到端/收敛检查，不放宽判据。输出默认新目录，保留已有结果和失败记录。

阶段报告原件保存在本地 `artifacts/cleanup-20261031-current-package-01/retired-docs/`，更早的退役文档及结果仍在各历史输出目录。源码和文档历史可通过Git追溯，不保留并行正式源码副本。后续不触及 Agamemnon 的设备、设置和日志。
