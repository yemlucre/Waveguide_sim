# 理论仿真维护入口

2026-10-30 Python包/RK4：后续通用编程入口为可安装 `waveguide_sim`，几何与复输入→横向谱微分＋经典四阶RK4→每步全截面复场；新增内部能力 `optics.rk4_field_simulation`（agentExposed=false），共4项内部能力。[包契约](rk4-package.md) 定义输入、单位、坐标、步长稳定界、资源与收敛要求。50项回归及已安装包/旧场景端到端通过，见[验证记录](../reports/rk4-package-20261030.md)。旧分步法报告入口保留兼容，非新包默认算法。

检查日期：2026-10-30。本独立项目来自 Agamemnon；模型与原有结果原样迁移，设备/设置/SDK不在此项目。

- [光学能力与完整契约](optical-simulation.md)
- [能力索引](capabilities.json)：只有独立理论计算能力，agentExposed=false。
- [首次交付记录](../reports/optics-theory-20261030.md)
- [项目使用说明](../../README.md)

后续变更同步维护本文、对应契约和 capabilities.json；说明检查日期、输入输出、单位、坐标、限制、错误、验证及待实测项。修改计算代码时运行科学测试与适用的端到端/收敛验证，保留失败结果。状态、范围、设备实时值不能从文档或默认参数推定。

2026-10-30 报告v2：显示层新增光场播放、截面与折射率图、多间距比较、参数与阈值诊断、CSV/PNG下载；未修改求解器或增加物理能力。入口/状态/验证见[报告更新](../reports/report-v2-20261030.md)。

2026-10-30 LAMP卷积特征起步：[新能力契约](lamp-convolution.md)。新增内部能力 optics.lamp_modal_correlation，当前2项能力，均agentExposed=false。9通道假设三维路径、离散耦合模、3相位平面、4个3×3核及3幅合成图像；不是全场BPM/完整CNN或作者64通道复现。21项科学与报告回归通过，详细来源、读出假设与验证见契约。

2026-10-30 通用傍轴传播：新增第3项内部能力 optics.general_paraxial_bpm，详见[通用BPM契约](general-bpm.md)。支持1/2横向维度、多波导沿z缓变、复光场、矩形区域指标、参数扫描和逐候选收敛；29项回归通过。仍无Agent/MCP注册；原双波导和LAMP能力不变。

2026-10-30 Python场景协议v1：通用能力现在支持可信Python函数定义绝对折射率与自定义复输入、全自动收敛、目标复场重叠和参数扫描，根simulate.py为纯Python入口。[契约](python-scenes.md)。36项科学/报告回归通过；仍3项能力，均未注册Agent工具。

