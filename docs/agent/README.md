# 理论仿真维护入口

检查日期：2026-10-31。当前只维护 `waveguide_sim` Python/RK4 包；原报告、场景脚本、双波导/LAMP/分步求解流程及相关测试已删除。

- [项目使用说明](../../README.md)
- [Python/RK4 完整契约](rk4-package.md)：物理模型、单位、坐标、输入输出、采样、稳定性与收敛。
- [能力清单](capabilities.json)：仅1项独立理论能力，agentExposed=false。
- [本轮清理与验证记录](../reports/python-only-20261031.md)
- [首次RK4包验证记录（历史）](../reports/rk4-package-20261030.md)

共享数值方法独立于界面、Agent和设备。功能变化同步维护契约及能力清单，不把理论参数或结果当作实测/设备状态。改计算代码后运行 `simulate-optics.ps1 -Test` 和适用的端到端/收敛检查，不放宽判据。输出默认新目录，保留已有结果和失败记录。

旧验证文档已归档到本地 artifacts/cleanup-20261031-140549-4824/retired-docs/；旧源码可通过Git历史追溯，不保留并行正式源码副本。后续不触及 Agamemnon 的设备、设置和日志。
