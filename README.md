# 波导光场仿真 Python 包

`waveguide_sim` 输入波导形状或绝对折射率分布、入射复光场，在标量傍轴模型中用经典四阶 Runge–Kutta（RK4）沿 z 推进，计算网格上各位置的复光场。支持一个或两个横向维度，默认保存每个传播步的完整横截面。

## 安装与运行

第一次使用请看 [从安装到自定义仿真的完整教程](docs/tutorial.md)，包含可运行脚本、形状/入射场定义、读取数据、绘图及收敛排查。

需要 Python 3.10+ 和 NumPy。在项目根目录执行：

```powershell
python -m pip install -e .
python -m waveguide_sim
```

也可直接从源码运行 `python simulate.py`。两种入口执行同一个 RK4 示例，默认写入新的 `artifacts/rk4/<时间戳>/`。用 `--output 新目录` 指定输出，已有目录拒绝覆盖。

## 在 Python 中使用

```python
import numpy as np
from waveguide_sim import Grid, Waveguide, gaussian_beam, simulate, check_convergence

# 所有示例物理参数均 assumed_not_measured，单位为 µm。
grid = Grid(windows_um=(48.,48.), points=(64,64), length_um=20., step_um=.1)
guide = Waveguide(
    shape=lambda z,q: np.exp(-((q[0]-z/20)/3)**2-(q[1]/4)**2),
    core_index=1.453, cladding_index=1.45,
)
launch = gaussian_beam(waists_um=(3.,4.))
result = simulate(grid, guide, launch)
psi = result.field        # (Nz,Nx,Ny)，复包络
intensity = result.intensity
checks = check_convergence(grid, guide, launch)
result.save('new_fields.npz')
```

`refractive_index(z_um, coordinates)` 也可直接提供绝对实折射率函数；入射场可以是同网格复数组或坐标函数。计算保留输入幅度与相位，不自动归一化。`store_every` 控制保存截面间隔，末端始终保存。

## 目录和验证

- `src/waveguide_sim/`：网格、几何/输入场、RK4 求解器和 Python 示例入口。
- `tests/test_optics_rk4.py`：解析解、四阶收敛、几何/边界/稳定性和数据保存验证。
- [模型、参数单位、接口与限制](docs/agent/rk4-package.md)。
- [当前清理和验证记录](docs/reports/python-only-20261031.md)。

```powershell
python -m unittest discover -s tests -v
# 本机可选测试助手，仍只调用 Python：
.\simulate-optics.ps1 -Test
```

该模型仅为单向、线性、弱导引标量傍轴传播，周期横向边界；不是全矢量 Maxwell 求解。显式 RK4 有网格相关的步长限制，需检查功率、边缘、高频和网格收敛。所有位置指离散网格点；所有示例参数均为理论假设，未标定为实测数据。

本项目于2026-10-30迁出 Agamemnon；旧报告流程已移除。历史结果及失败记录保留在本地 `artifacts/`（不纳入Git），本项目没有设备操作或已注册 Agent 工具。
