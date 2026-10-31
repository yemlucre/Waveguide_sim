# Waveguide_sim

用于波导复光场传播与可视化的 Python 仿真包。给定计算网格、波导折射率分布和入射光场，计算光束沿 z 方向传播时的幅度与相位，并支持一次仿真后反复读取、滑动查看。

[快速开始](#快速开始) · [自定义仿真](#自定义仿真) · [完整教程](docs/tutorial.md) · [模型与接口](docs/agent/rk4-package.md)

## 主要功能

- **自定义波导和入射场**：支持一个或两个横向维度，可用坐标函数定义截面、弯曲和渐变折射率，也可输入采样复场。
- **保存完整复光场**：默认保存每个传播步的横截面，保留输入幅度和相位，导出 NPZ 文件。
- **交互查看**：二维横截面结果可通过 x/y/z 滑块查看截面强度、包络相位和所选点的复场。
- **数值验证**：提供功率、边缘、高频诊断，以及传播步长、横向分辨率和窗口大小的收敛检查。

## 快速开始

### 1. 安装

需要 **Python 3.10+**。以下命令在 Windows PowerShell 中运行。

首次获取项目：

```powershell
git clone https://github.com/yemlucre/Waveguide_sim.git
cd Waveguide_sim
```

如果已有项目文件夹，直接在该文件夹打开终端。然后创建虚拟环境并安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

安装会一并安装 NumPy 和 Matplotlib。后续命令使用同一个虚拟环境，无需手动激活；编辑器也请选择 `.venv\Scripts\python.exe`。已有环境更新代码后，重新执行安装命令即可补齐依赖。

### 2. 运行内置示例

```powershell
.\.venv\Scripts\python.exe -m waveguide_sim
```

示例计算一个弯曲的渐变折射率波导，并自动执行收敛检查。每次在当前工作目录下新建 `artifacts/rk4/<时间戳>/`，终端输出中的 `output` 字段是结果目录。

该命令保存仿真数据。**打开图窗请继续下一步。**

### 3. 打开光场，拖动查看

将下面的 `实际运行目录` 替换为上一步生成的时间戳目录名；已有二维 NPZ 文件也可直接使用它的路径：

```powershell
.\.venv\Scripts\python.exe -m waveguide_sim.viewer "artifacts/rk4/实际运行目录/fields.npz"
```

| 操作 | 查看内容 |
| --- | --- |
| 拖动 z 滑块 | 不同传播位置的横截面强度和包络相位 |
| 拖动 x、y 滑块 | 移动十字线，读取所选点的复场、强度和相位 |
| 查看左侧图 | 沿 y 积分后的整段 x-z 强度分布及当前 z 位置 |

文件只读取一次，拖动时直接使用内存中的数据，无需重新仿真。查看器需要支持交互的 Matplotlib 图形后端；Notebook 的静态 inline 图片不支持拖动。

## 自定义仿真

复制[教程第四节的完整脚本](docs/tutorial.md#4-写第一个自己的仿真程序)，在项目根目录保存为 `my_simulation.py`。脚本顶部有使用声明，主要修改位置如下：

| 修改位置 | 设置内容 |
| --- | --- |
| `grid` | 波长、参考折射率、窗口大小、网格点数、传播长度和步长 |
| `shape` / `guide` | 波导形状、弯曲、芯层及包层折射率；也可提供绝对折射率函数 |
| `launch` | 入射光束宽度、位置、复振幅和相位 |
| `STORE_EVERY` | 截面保存间隔；设为 `1` 保留每个传播步 |
| `SHOW_PLOT` / `INTERACTIVE_VIEWER` | 是否显示图窗、是否使用滑块查看器 |
| `OUTPUT_ROOT` / `INSPECT_DATA` | 输出根目录、是否在终端执行额外数据查询 |

运行自己的脚本：

```powershell
.\.venv\Scripts\python.exe my_simulation.py
```

教程脚本会保存 `fields.npz`、`checks.json` 和 `propagation.png`，随后默认打开滑块查看器。只保存数据和图片时，设 `SHOW_PLOT=False`。

## 结果文件与数据约定

内置示例的每个结果目录包含：

| 文件 | 内容 |
| --- | --- |
| `fields.npz` | 复光场、x/y/z 坐标、截面积分功率和元数据 |
| `input.json` | 示例几何与材料参数假设 |
| `result.json` | 主运行诊断、收敛误差和验证状态 |
| `manifest.json` | 运行环境、包源码及输出文件的哈希 |

二维横截面结果按 **`(z, x, y)`** 排列，`result.field[iz, ix, iy]` 是一个网格点的复包络。内置示例的场数组为 `(201, 64, 64)`；一维横截面结果为 `(Nz, Nx)`，当前滑块查看器仅支持二维横截面。

所有长度单位为 **µm**，折射率无量纲。强度为 `abs(field)**2`，相位为 `np.angle(field)`，单位 rad。场不自动归一化，强度和积分功率的单位取决于输入场约定。

> [!NOTE]
> “所有点”指已保存的离散网格点。增大 `STORE_EVERY` 会减少可查看的 z 截面。每次最多保存 1600 万个复值；输出目录和 NPZ 文件均拒绝覆盖已有结果。

## 模型与验证

求解器采用横向 FFT 谱微分和沿 z 的经典四阶 Runge–Kutta（RK4），适用于单向、线性、弱导引的标量傍轴传播，横向边界为周期边界。不包含偏振、背反射、吸收层、非线性或全矢量 Maxwell 求解。

使用结果前，应同时检查主运行诊断和网格收敛。内置示例的 `result.json` 中，`status` 为 `verified_theoretical_propagation` 表示两者均通过；教程脚本查看 `checks.json` 中的 `passed`。全部示例物理参数均为 `assumed_not_measured`，数值检查通过不能代替材料标定和实验验证。

在项目根目录运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 文档与项目结构

| 入口 | 用途 |
| --- | --- |
| [完整教程](docs/tutorial.md) | 安装、自定义脚本、参数设置、数据读取、绘图和收敛排查 |
| [模型与接口契约](docs/agent/rk4-package.md) | 方程、单位、坐标、输入输出、资源限制和验证门槛 |
| [当前验证说明](docs/validation.md) | 测试覆盖、收敛结果、交互查看和本地证据位置 |
| [src/waveguide_sim/](src/waveguide_sim/) | 正式 Python 包，包含网格、几何、求解器和查看器 |
| [tests/](tests/) | 数值方法、数据存储和查看器测试 |
| `artifacts/` | 本地仿真结果与验证记录，不纳入 Git |
