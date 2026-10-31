# 只保留 Python/RK4 框架：清理与验证

日期：2026-10-31。按用户要求移除旧报告流程，只保留新的Python仿真包。

## 最终结构

- `src/waveguide_sim/`：`grid.py`、`geometry.py`、`solver.py`、包导出及 `__main__.py`。
- `tests/test_optics_rk4.py`：只验证当前包；保留原7项RK4科学测试，新增网格/加密协议验证。
- `simulate.py`：直接调用当前包内示例；`simulate-optics.ps1` 只保留Python运行/测试辅助功能，以满足项目规定的科学测试命令。
- 文档与能力清单只描述 `optics.rk4_field_simulation`。包版本0.2.0。

删除原 `src/Agamemnon.Optics/`、包内旧分步算法 `bpm.py`、报告HTML/JS/生成与打开入口、CMD启动器、旧场景协议及专用双波导/LAMP/lantern演示和对应测试。旧文档从当前说明中移除，历史验证文档归档到本地 `artifacts/cleanup-20261031-140549-4824/retired-docs/`；Git保留原代码历史。现有结果和失败记录未覆盖或清除。

## API 变化

从旧分步代码中提取仍需使用的Grid、axes和refinement_grids，唯一实现放在 `grid.py`；RK4方程、阶段、诊断、收敛门槛不变。删除无效的Grid.samples，截面保存仅由store_every控制，存储预算按实际保存帧数计算；0.1调用若传了samples应删除该参数。旧场景/报告命令行选项不再支持。

## 验证

- `simulate-optics.ps1 -Test`：8项全部通过，包括四阶收敛、解析二维衍射、弯曲波导细化、边界失败、非法/不稳定输入、NPZ及网格验证；原RK4判据未放宽。
- `python simulate.py --output artifacts/python-only-20261031-final/source-e2e`：退出0，verified_theoretical_propagation，场形状 `(201,64,64)`，主运行功率漂移4.44e−16。
- 主/半步长/半网格/扩大窗口均通过；末端相对复场L²差分别约2.15e−12、5.83e−9、2.42e−10，与清理前示例一致。
- 本地离线构建安装0.2.0后，`python -m waveguide_sim --output .../installed-e2e` 退出0，所有主运行/收敛检查通过，复场同为 `(201,64,64)`；安装目录只包含当前5个Python源文件（__init__、__main__、grid、geometry、solver）和缓存，无bpm或报告模块。安装包及包入口独立验证记录在 `artifacts/python-only-20261031-final/`，安装构建不使用历史build目录。

所有示例物理参数均为 assumed_not_measured；上述仅为标量傍轴离散模型的数值一致性检查，不代表实测标定或设备状态。仍为周期边界、单向线性弱导引模型，无矢量/反射/偏振/非线性等扩展，无Agent/MCP注册。
