# 波导理论仿真

当前通用框架为 **`waveguide_sim` Python 包**：输入波导形状/折射率及入射复光场，沿 z 使用经典四阶 Runge–Kutta（RK4），输出计算网格上各位置的复光场。支持一个或两个横向维度，默认保存每个传播步。所有示例物理参数为 assumed，模型为标量傍轴传播。

```powershell
python -m pip install -e .
python -m waveguide_sim
```

在自己的 Python 程序中使用 `from waveguide_sim import Grid, Waveguide, gaussian_beam, simulate`。[完整使用示例与模型契约](docs/agent/rk4-package.md)。正式包在 `src/waveguide_sim/`，验证在 `tests/test_optics_rk4.py`；无需报告或界面即可计算。

下文保留迁移及旧报告流程的历史说明；旧 `simulate.py` 与双击脚本仍走各自分步法/模态演示，不是新包的RK4入口。

这是从 Agamemnon 迁出的独立理论研究项目，迁移日期：2026-10-30。

- 双击 **打开报告.cmd**：打开最近生成的中文交互报告（旧报告均保留）。
- 双击 **运行仿真.cmd**：按默认参数重新计算，成功后自动打开新报告；窗口会显示计算状态。
- 改参数：编辑 `src/Agamemnon.Optics/example.json`，然后重新运行。
- 代码：`src/Agamemnon.Optics/`；科学测试：`tests/test_optics.py`。
- 现有结果：`artifacts/optics/`；初次探索失败结果也保留。
- 模型、单位、限制与验证：[完整说明](docs/agent/optical-simulation.md)。

在本目录打开 PowerShell 也可以运行：

```powershell
.\simulate-optics.ps1 -Test
.\simulate-optics.ps1 -OpenReport
```

当前用 Python、NumPy 和 Pillow 运行，没有独立EXE。启动器优先使用本机已有的 Codex Python，未把运行环境复制进此文件夹；换电脑需要安装依赖，详见 [代码使用说明](src/Agamemnon.Optics/README.md)。

所有物理参数均为理论假设。当前是单横向维度的平板波导模型，不是实际材料标定或完整三维器件设计。没有设备操作、加工导出或已注册的Agent工具。

## 报告 v2（2026-10-30）

报告提供候选概览、可播放的光场传播、左右功率、当前与输入截面光强对比、折射率分布、多间距曲线、参数定义和逐项误差阈值；可导出当前曲线CSV、PNG和原始数据，也可由浏览器打印/保存PDF。播放只浏览已有采样，不重新求解。

它目前是双波导专用流程与可复用的1+1D静态传播内核。底层可传自定义输入场和非负弱折射率增量数组；当前JSON入口仍针对双高斯波导。均匀介质衍射与单波导已有科学测试；多通道需补充通道指标与基准；弯曲、分叉、沿z变化、第二横向维度及三维/偏振/反射/非线性/真实损耗尚未实现。

## LAMP三维波导图像特征演示（2026-10-30）

双击 **运行图像特征仿真.cmd**，重新计算并打开论文启发的独立演示；**打开报告.cmd** 总是打开最近生成的报告。也可运行：

```powershell
.\simulate-optics.ps1 -Scenario lamp -OpenReport
.\simulate-optics.ps1 -Scenario lamp -Config src/Agamemnon.Optics/lamp_example.json
```

报告可切换字母H/圆形渐变/棋盘格，以及Sobel X、Sobel Y、均值模糊、Laplacian；比较零相位基线与已编程相位的输出。点击图像或拖动滑窗，查看9路输入及沿假设三维路径传播的复模振幅。普通卷积的带符号结果假设有理想相干读出；直接强度响应为模平方，两者单独展示。

这是LAMP机制启发的3×3小规模理论扩展：每次用一个核，9通道＋3个理想相位平面，程序组织滑窗。没有全场三维BPM、作者64通道样品复现、完整CNN分类器、实验标定或真实性能指标。配置与可追溯来源见 [LAMP契约](docs/agent/lamp-convolution.md)。

## 通用光场传播（2026-10-30 新增）

上文关于“第二横向维度尚未实现”的描述仅适用于旧 coupler 流程。现在新增独立的通用 BPM 入口，不影响旧双波导/LAMP报告：

```powershell
.\simulate-optics.ps1 -Scenario bpm -OpenReport
.\simulate-optics.ps1 -Scenario bpm -Config src/Agamemnon.Optics/bpm_scan_example.json -OpenReport
```

默认配置 `src/Agamemnon.Optics/bpm_example.json` 描述两横向维度上的两条波导，其中一条沿z缓弯并渐变半宽。可修改波长、背景折射率、各波导节点位置/半宽/增量、输入位置/束腰/倾角和传播长度；报告播放连续复光场求解后的采样光强，输出原始复场NPZ。波长扫描示例为一横向维度，逐候选验证并比较末端指定区域功率。

通用范围是1+1D或2+1D标量傍轴模型，不是全矢量Maxwell；所有示例物理参数 assumed。每个候选都进行半步长、半网格和扩大窗口验证；失败明确标记。区域功率不是导模效率，输入高斯也不是本征导模。后续Agent可通过JSON配置和结构化结果封装，当前未注册任何Agent工具。

完整[输入/输出与Agent调用契约](docs/agent/general-bpm.md)，[本轮验证记录](docs/reports/general-bpm-20261030.md)。

## 推荐日常入口：Python场景

直接运行 `python simulate.py --open-report`，或双击 **运行通用光场仿真.cmd**。修改 `src/Agamemnon.Optics/scene_example.py` 开头的 PARAMETERS 即可；SCAN定义扫描候选。新物理形状只修改该场景中的折射率/复场函数，共用求解器保持固定。

支持任意可分辨的弱实折射率表达式、复振幅与相位输入；自定义函数同样接受完整收敛检查。报告新增相位/折射率截面，结果保存目标模板重叠。示例全为assumed，无需先有实验数据即可做数学探索。详细[使用和场景协议](docs/agent/python-scenes.md)。旧JSON入口继续兼容。

本轮最终验证：纯Python入口36项回归通过；示例与三间距扫描完成。见[验证记录](docs/reports/python-scenes-20261030.md)。
