# 独立项目迁移

2026-10-30 按用户要求迁至桌面 D:/Destop/波导理论仿真。迁移 src/Agamemnon.Optics、tests/test_optics.py、simulate-optics.ps1、artifacts/optics 全部历史结果、artifacts/tests/optics 检查记录、原模型契约和交付说明。

保留相同相对目录，数值源码/原始配置/报告/数据不变；新增中文说明、双击入口及独立能力索引。启动器增加成功后打开报告的可选行为。原 Agamemnon 仅保留迁移说明链接，移除该独立能力，恢复41项静态能力；MCP仍50工具。

迁移文件SHA256逐项检查见 artifacts/migration/transfer.json。历史报告 manifest 仍表示原计算的源码和数据身份。实际迁移后的测试、重新计算和路径检查另记录 verification.json。未移动其他项目源码或设备/设置/日志；没有生成EXE。

迁移后验证：9项科学测试通过；新目录完整仿真退出0，状态verified_theoretical_candidate；原始源码/报告清单SHA256、独立能力和链接、覆盖保护及不可达错误状态通过检查。详见artifacts/migration/verification.json。
