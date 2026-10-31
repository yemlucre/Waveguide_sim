# 理论波导计算首版交付

日期：2026-10-30。用户尚未做实验，授权自定义参数先开发理论部分。新增 `src/Agamemnon.Optics/` 独立Python模型、`tests/test_optics.py`、根 `simulate-optics.ps1`；正式.NET代码、解决方案、设备、设置、日志、构建入口未在本任务修改，无新EXE或快捷方式目标。保留任务开始时已有的大量未提交改动。

模型/接口/状态/文件/限制详见[agent契约](../agent/optical-simulation.md)，[使用说明](../../src/Agamemnon.Optics/README.md)，[交互报告](../../artifacts/optics/coupler-theory-delivery/index.html)。42项静态能力（含新增独立Python理论能力），MCP仍50项，新能力agentExposed=false。

默认参数全部assumed：λ₀=780nm、n₀=1.45、Δn峰值=0.003、高斯增量1/e半宽2.5µm；扫描中心距10/12/14/16/18µm，最长20mm。10µm的首次右半空间50%目标在3.4214179mm，重算49.997282%；12µm在10.6785495mm。14/16/18µm在20mm内未达目标。此指标不是分离端口效率，没有加工映射。

候选数值检查：功率漂移2.38e−13、全步最大边缘功率1.66e−5；半步长右侧功率差7.92e−6、半网格差2.12e−7、扩大窗口差9.91e−5、独立本征分解场L²误差0.001687，均通过显式阈值。全扫描只有守恒和边缘检查，收敛细化针对选中候选。

验证：根simulate-optics.ps1 -Test，9项科学/边界回归通过；默认完整CLI退出0，result状态verified_theoretical_candidate。报告图片已目视核对。agent-browser本机文件浏览验证间距下拉、滑块读数/观察线、图片解码，宽屏和390px窄屏无横向溢出；截图在 artifacts/tests/optics/report-desktop.png、report-mobile.png。最终报告中文状态措辞同步后再次加载检查。源码/结果哈希、JSON、能力ID/源码和受影响文档本地链接另由交付核对检查。

初次8µm/步长5µm探索边缘检查失败，结果保留 artifacts/optics/first-theory；最终演示范围明确为10..18µm、步长2µm，未降低阈值。无真实材料数据、实验/硬件操作、三维/端口/工艺校准；不作实际器件性能保证。未安装新依赖，使用本机已有NumPy 2.3.5和Pillow 12.3.0。
