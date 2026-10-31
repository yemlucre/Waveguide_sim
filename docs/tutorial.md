# waveguide_sim 使用教程

适用版本：0.2.0；更新日期：2026-10-31。教程中的波长、折射率和几何参数全部为 `assumed_not_measured`，用于学习，未按真实器件标定。

示例核验：二维完整脚本、数据读取及一维示例已运行；二维主运行与收敛检查通过。本次绘图与依赖核验见 [Matplotlib 验证记录](reports/matplotlib-20261031.md)。

一次仿真已得到所有已保存网格点的复光场：`result.field[iz, ix, iy]`。默认 `STORE_EVERY=1` 保存每个传播步，之后可直接拖动x/y/z滑块查看，**无需为每个观察位置重新仿真**。已有NPZ也可用 `python -m waveguide_sim.viewer 路径/fields.npz` 打开。交互查看说明与验证见 [滑块查看器记录](reports/field-viewer-20261031.md)。

## 1. 这个包做什么

一次仿真需要三个输入：

1. **计算网格**：算多大区域、横向分多少点、向前传播多远、每一步多长。
2. **波导**：空间各位置的折射率，可以描述直波导、弯曲波导、渐变截面和多芯结构。
3. **入射场**：输入面上的复振幅，包含幅度和相位。

调用 `simulate(grid, guide, launch)` 后得到各保存截面的复光场。沿 z 使用经典四阶 Runge–Kutta（RK4），横向用 FFT 谱微分计算衍射。无需修改求解器来替换几何或入射场。

当前求解标量、单向、线性、弱导引傍轴传播。两个横向维度加传播方向构成2+1D模型，不含偏振、反射、吸收层或全矢量 Maxwell 求解。所谓“所有位置”是计算网格上的位置。

## 2. 安装

需要 Python 3.10 或更高版本。已在本机项目目录时，在 PowerShell 执行：

```powershell
cd "D:\Destop\波导理论仿真"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -c "import waveguide_sim; print(waveguide_sim.__version__)"
```

最后应显示 `0.2.0`。安装会一并安装 NumPy 和 Matplotlib；已经安装过旧版的用户，也请重新执行 `python -m pip install -e .` 补齐新增依赖。这里使用虚拟环境的完整解释器路径，无需激活环境。后文中的 `python`，在这种安装方式下请换成 `.\.venv\Scripts\python.exe`；在编辑器中也选择这个解释器。

如果从另一台电脑开始，先获取项目，再执行上面的安装步骤：

```powershell
git clone https://github.com/yemlucre/Waveguide_sim.git
cd Waveguide_sim
```

包的安装名是 `waveguide-sim`，Python导入名是 `waveguide_sim`。`pip install -e .` 中的点表示当前项目，不是从PyPI下载同名包。

## 3. 先跑自带示例

```powershell
python -m waveguide_sim
```

它计算一个二维横截面的弯曲渐变折射率波导，执行收敛检查，在**当前工作目录**下新建 `artifacts/rk4/<时间戳>/`。输出包括：

| 文件 | 内容 |
| --- | --- |
| `fields.npz` | 复光场、x/y/z坐标、各截面积分功率及元数据 |
| `input.json` | 示例的几何/材料假设 |
| `result.json` | 诊断、收敛误差和状态 |
| `manifest.json` | 环境及源文件/输出哈希 |

示例中场数组的形状为 `(201,64,64)`：200个传播步加输入面，每个截面64×64点。

在源码项目目录也可执行 `python simulate.py`，两者调用同一个示例。指定输出时使用 `python -m waveguide_sim --output artifacts/my_first_run`；该目录必须尚不存在。

**这个命令运行的是内置示例。要仿真自己的结构，按下一节写Python程序，命令行目前不接收自定义几何文件。**

## 4. 写第一个自己的仿真程序

在项目根目录创建 `my_simulation.py`，复制下面完整代码，然后运行 `python my_simulation.py`。这只是调用包的个人实验脚本；正式求解器仍只维护在 `src/waveguide_sim/`。本节已经包含绘图和可选数据查询，不需要再拼接第8、9节代码。

```python
"""二维自定义仿真：保存 NPZ、检查结果、保存图片并显示图窗。

运行：先在项目根目录 python -m pip install -e .，再 python my_simulation.py。
需要按自己的问题修改：
1. grid：真空波长、参考折射率、x/y窗口和点数、传播长度、步长。
2. shape / guide：截面形状、x/y半宽、弯曲位移、芯层与包层折射率。
3. launch：入射振幅1/e半宽、中心位置、复振幅（含初始相位）。
4. OUTPUT_ROOT / STORE_EVERY：结果根目录、每隔多少传播步保存截面。
5. SHOW_PLOT：True显示图窗，False只保存PNG。
   INTERACTIVE_VIEWER=True：显示可滑动的光场查看器；False显示静态传播图。
   z滑块切换横截面，x/y滑块选点，底部显示复场、强度和相位；关闭窗口后结束。
6. INSPECT_DATA / QUERY_POINT_UM：是否执行数据查询、查询的(x,y,z)位置。
   不需要的数据查询默认关闭；如需查看，将 INSPECT_DATA 改为 True。

所有长度均为微米，折射率无量纲；物理参数均为 assumed_not_measured。
场是缓变复包络，强度为|场|²，未标定为W/m²；数组顺序为(z,x,y)。
本脚本的绘图仅适用于二维横截面；一维模型请使用第11节并另写绘图。
改变网格、几何或入射场后仍需保留诊断与收敛检查；图片不代表验证通过。
"""
from datetime import datetime
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from waveguide_sim import Grid, Waveguide, gaussian_beam, simulate, check_convergence
from waveguide_sim.viewer import view_field

# 显示、存储和查询设置；输出路径相对于运行时的工作目录。
OUTPUT_ROOT = Path('artifacts')
STORE_EVERY = 1
SHOW_PLOT = True
INTERACTIVE_VIEWER = True
INSPECT_DATA = False
QUERY_POINT_UM = (0.0, 0.0, 10.0)

# 1. 计算网格：所有长度单位为微米。
grid = Grid(
    wavelength_um=0.78,
    background_index=1.45,
    windows_um=(48.0, 48.0),
    points=(64, 64),
    length_um=20.0,
    step_um=0.1,
)

# 2. 渐变折射率椭圆波导；这两个设置也需要按结构修改。
GUIDE_RADII_UM = (3.0, 4.0)  # 折射率增量的x/y方向1/e半宽
BEND_X_UM = 1.0             # 波导末端中心相对于输入面沿x的位移

def shape(z_um, coordinates):
    x, y = coordinates
    center_x = 0.5 * BEND_X_UM * (1.0 - np.cos(np.pi * z_um / grid.length_um))
    return np.exp(-((x - center_x) / GUIDE_RADII_UM[0])**2
                  - (y / GUIDE_RADII_UM[1])**2)

guide = Waveguide(shape=shape, core_index=1.453, cladding_index=1.45)

# 3. 输入面：居中的椭圆高斯复场。
launch = gaussian_beam(
    waists_um=(3.0, 4.0),
    center_um=(0.0, 0.0),
    amplitude=1.0 + 0.0j,
)

result = simulate(grid, guide, launch, store_every=STORE_EVERY)
checks = check_convergence(grid, guide, launch)
passed = result.diagnostics['checks_passed'] and checks['passed']

# 每次创建新目录；即使检查失败，也保存场和诊断供排查。
output = OUTPUT_ROOT / ('my-run-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
output.mkdir(parents=True, exist_ok=False)
result.save(output / 'fields.npz')
(output / 'checks.json').write_text(
    json.dumps({'passed': passed, 'diagnostics': result.diagnostics, 'convergence': checks}, indent=2),
    encoding='utf-8',
)
print('场数组形状：', result.field.shape)
print('主运行及收敛均通过：', passed)
print('保存位置：', output.resolve())

# 4. 可选：查看复场、强度、相位、采样点及保存的数据。
x_um, y_um = result.axes_um
z_um = result.z_um
if INSPECT_DATA:
    input_field = result.field[0]
    output_field = result.field[-1]
    output_intensity = abs(output_field)**2  # 等价于 result.intensity[-1]，少算其他截面
    output_phase = np.angle(output_field)   # rad，范围[-pi, pi]

    # 最近的已保存离散点；超出范围时会取最靠近的边界点，不做插值。
    query_x, query_y, query_z = QUERY_POINT_UM
    ix = int(np.argmin(abs(x_um - query_x)))
    iy = int(np.argmin(abs(y_um - query_y)))
    iz = int(np.argmin(abs(z_um - query_z)))
    print('实际采样位置：', x_um[ix], y_um[iy], z_um[iz])
    print('该点复场：', result.field[iz, ix, iy])
    print('各截面相对输入的功率：', result.power / result.power[0])

    # 重新读入刚保存的文件；无需pickle，离开with后这些数组仍可用。
    with np.load(output / 'fields.npz', allow_pickle=False) as data:
        saved_field = data['field']
        saved_z = data['z_um']

# 5. 保存NPZ之后画图：对y积分，显示整束光的x-z分布。
dy = grid.windows_um[1] / grid.points[1]
xz = np.sum(abs(result.field)**2, axis=2) * dy
fig, axes_plot = plt.subplots(1, 2, figsize=(10, 4))
image = axes_plot[0].pcolormesh(z_um, x_um, xz.T, shading='auto')
axes_plot[0].set(xlabel='z (um)', ylabel='x (um)', title='Intensity integrated over y')
fig.colorbar(image, ax=axes_plot[0])

image = axes_plot[1].pcolormesh(x_um, y_um, abs(result.field[-1]).T**2, shading='auto')
axes_plot[1].set(xlabel='x (um)', ylabel='y (um)', title='Output intensity', aspect='equal')
fig.colorbar(image, ax=axes_plot[1])
fig.suptitle('Numerical checks passed' if passed else 'Numerical checks FAILED; diagnostic only')
fig.tight_layout()
fig.savefig(output / 'propagation.png', dpi=160)  # 先保存，即使关闭图窗也保留图片
print('图片位置：', (output / 'propagation.png').resolve())
if SHOW_PLOT and not INTERACTIVE_VIEWER:
    plt.show(block=True)
plt.close(fig)
if SHOW_PLOT and INTERACTIVE_VIEWER:
    # 直接使用内存中的完整复场，不重算、不重复读取NPZ。
    viewer = view_field(result.field, result.axes_um, result.z_um)
    plt.close(viewer.figure)
```

这个例子的波导权重是高斯函数。中心权重为1，远处趋近0，所以折射率为 `1.45 + 0.003 * shape`。3和4 µm分别为折射率增量的x/y方向1/e半宽，不是硬芯半径；高斯输入的3和4 µm则是**光场振幅**1/e半宽。

自定义脚本不像内置示例那样自动归档全部源码及来源；实际研究时应一并保存实验脚本、参数、材料来源及版本信息。

每次运行会新建目录，包含 `fields.npz`、`checks.json` 和 `propagation.png`。静态PNG左图是沿y积分的强度，单位为场单位平方×µm；右图是输出面强度，单位为场单位平方。`SHOW_PLOT=True` 在支持图形界面的环境弹出图窗；默认 `INTERACTIVE_VIEWER=True` 显示三联图和x/y/z滑块。只想导出图片或在无界面环境运行时设 `SHOW_PLOT=False`。PNG始终在显示图窗之前保存，顺序见 [Matplotlib显示说明](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.show.html)。

查看器左侧为整段x-z积分强度，中间为当前z截面强度，右侧为当前z截面的包络相位。拖动z切换截面，拖动x/y移动十字线并查看所选点的复场。强度色标在所有截面间固定，相位范围固定为[-π,π]；零场处相位无定义，弱光区域的相位需谨慎解释。滑块吸附到实际保存坐标，不对未保存的位置插值，也不会重新调用求解器。关闭查看器后数据仍保存在NPZ，可随时按第9节重新打开。

## 5. 如何设置网格

| 参数 | 含义 | 上例 |
| --- | --- | --- |
| `wavelength_um` | 真空波长 | 0.78 µm，即780 nm |
| `background_index` | 包络载波所用的参考折射率n0 | 1.45 |
| `windows_um` | x/y方向计算窗口总宽度 | 48×48 µm |
| `points` | 各横向轴点数 | 64×64 |
| `length_um` | z方向总传播长度 | 20 µm |
| `step_um` | 请求的最大传播步长 | 0.1 µm |

窗口以0为中心，横向间距为窗口宽度/点数。例如x坐标是−24、−23.25……23.25 µm，不重复保存周期端点+24。波导和输入应远离边缘。

实际步数为 `ceil(length_um/step_um)`，实际步长会微调以恰好到达末端。截面保存由 `store_every` 控制；0.2版没有 `samples` 参数。

横向每轴32..1024点，必须为4的倍数；自动收敛检查要求主网格点数为8的倍数且不超过512。显式RK4的稳定步长随网格变化；不要直接假定 `Grid()` 的默认步长适合自己的输入或细化网格，入门可从本教程的显式参数开始。

## 6. 更换波导形状

`shape(z_um, coordinates)` 返回0..1的权重。布尔值也可以：True表示芯区，False表示包层。以下是二维截面的几何写法，可以替换第4节的shape；**这些只演示定义方法，并不宣称所选网格已充分解析硬边界**。

```python
# 圆形硬芯，半径3微米。
def circle(z_um, coordinates):
    x, y = coordinates
    return x*x + y*y <= 3.0**2

# 矩形硬芯，宽6微米、高4微米。
def rectangle(z_um, coordinates):
    x, y = coordinates
    return (np.abs(x) <= 3.0) & (np.abs(y) <= 2.0)
```

硬边界可能需要更细网格，沿z变化的硬边界还可能降低纵向收敛阶数。先检查收敛，再解释结果。

多芯或复杂材料分布可以跳过Waveguide，直接给出**绝对折射率**：

```python
def refractive_index(z_um, coordinates):
    x, y = coordinates
    left = np.exp(-((x + 4.0)/2.5)**2 - (y/3.0)**2)
    right = np.exp(-((x - 4.0)/2.5)**2 - (y/3.0)**2)
    return 1.45 + 0.003 * (left + right)

# 调用方式：simulate(grid, refractive_index, launch)
```

不要只返回0.003这样的折射率增量。所有位置必须满足 `n>0` 且 `abs(n-n0)/n0 <= 0.01`。形状/折射率函数要确定性地按坐标求值，避免绑定固定64×64数组，自动细化时会换网格。

## 7. 更换入射光场

高斯辅助函数的常用设置：

```python
shifted_launch = gaussian_beam(
    waists_um=(3.0, 4.0),
    center_um=(1.0, 0.0),             # 输入横向偏移，微米
    transverse_k_per_um=(0.02, 0.0), # 横向相位梯度，rad/微米
    amplitude=2.0 * np.exp(0.5j),    # 复振幅
)
```

相位梯度不是以度表示的入射角。小角度时，x方向倾角约为 `kx/(2*pi*n0/wavelength_um)` rad。RK4不会自动把功率归一化为1；输入振幅乘2，强度和积分功率会乘4。

两个相干光斑可以写成自定义函数：

```python
def two_spots(coordinates):
    x, y = coordinates
    a = np.exp(-((x + 4.0)/2.5)**2 - (y/3.0)**2)
    b = np.exp(-((x - 4.0)/2.5)**2 - (y/3.0)**2)
    return a + np.exp(1j*np.pi/2) * b

# 调用方式：simulate(grid, guide, two_spots)
```

也可以传同网格的复数组给simulate，但check_convergence需要坐标函数，不能替你猜测采样数据的插值规则。二维输入场最终形状必须是 `(Nx,Ny)`；坐标本身是稀疏广播数组，x形状 `(Nx,1)`、y形状 `(1,Ny)`。

## 8. 读取任意位置的结果

第4节已经包含以下查询，将顶部 `INSPECT_DATA = True` 即可启用。下面单列出来说明；无需重复粘贴：

```python
x_um, y_um = result.axes_um
z_um = result.z_um

input_field = result.field[0]
output_field = result.field[-1]
output_intensity = result.intensity[-1]
output_phase = np.angle(output_field)  # rad，范围[-pi,pi]

# 查询最接近(x=0, y=0, z=10微米)的已保存网格点。
ix = int(np.argmin(abs(x_um - 0.0)))
iy = int(np.argmin(abs(y_um - 0.0)))
iz = int(np.argmin(abs(z_um - 10.0)))
print('实际采样位置：', x_um[ix], y_um[iy], z_um[iz])
print('该点复场：', result.field[iz, ix, iy])
print('各截面相对输入的功率：', result.power / result.power[0])

# 重新读入刚刚保存的文件。
with np.load(output / 'fields.npz', allow_pickle=False) as data:
    saved_field = data['field']
    saved_z = data['z_um']
```

结果按 `(z,x,y)` 排列，不是图片常用的 `(行y,列x)`。这里查询的是最近的离散点；若增大store_every，未保存的传播截面不能从文件中直接读取。

field是缓变复包络ψ。若需要带纵向参考载波的标量场，乘上 `exp(1j*2*pi*n0*z/wavelength_um)`；它仍不包含光学时间振荡。光强为|ψ|²，单位取决于输入场的单位约定，程序不自动把它标定成W/m²。

## 9. 直接读取已有 NPZ 画图

第4节已自动保存并显示传播图。若已有 `fields.npz`，无需重新仿真：将下面代码另存为 `plot_saved.py`，只修改顶部的 `NPZ_PATH`，再运行 `python plot_saved.py`。Matplotlib 已是包依赖，无需另行安装。

如果只想拖动查看，直接运行下面的命令即可；文件只读取一次，随后在内存中切换截面，不写入或修改原文件：

```powershell
python -m waveguide_sim.viewer "artifacts/实际运行目录/fields.npz"
```

下面的完整脚本额外保存静态PNG，再默认打开滑块查看器：

```python
"""只画已有二维NPZ：修改NPZ_PATH；SHOW_PLOT=False时只导出PNG。
INTERACTIVE_VIEWER=True开启x/y/z滑块，False只显示静态图；不重新仿真。
"""
from datetime import datetime
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from waveguide_sim.viewer import view_field

NPZ_PATH = Path(r'artifacts/请替换为实际运行目录/fields.npz')
SHOW_PLOT = True
INTERACTIVE_VIEWER = True

with np.load(NPZ_PATH, allow_pickle=False) as data:
    saved_field = data['field']
    if saved_field.ndim != 3:
        raise ValueError('此绘图脚本需要二维横截面数据，场数组顺序为(z,x,y)')
    x_um, y_um, z_um = data['x_um'], data['y_um'], data['z_um']

# 使用文件中原有坐标，不依赖当前grid或result，也不重新运行传播。
dy = y_um[1] - y_um[0]
xz = np.sum(abs(saved_field)**2, axis=2) * dy
output = NPZ_PATH.parent / ('plot-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
output.mkdir(parents=True, exist_ok=False)  # 新目录，不覆盖已有图片或数据

fig, axes_plot = plt.subplots(1, 2, figsize=(10, 4))
image = axes_plot[0].pcolormesh(z_um, x_um, xz.T, shading='auto')
axes_plot[0].set(xlabel='z (um)', ylabel='x (um)', title='Intensity integrated over y')
fig.colorbar(image, ax=axes_plot[0])

image = axes_plot[1].pcolormesh(x_um, y_um, abs(saved_field[-1]).T**2, shading='auto')
axes_plot[1].set(xlabel='x (um)', ylabel='y (um)', title='Output intensity', aspect='equal')
fig.colorbar(image, ax=axes_plot[1])
fig.tight_layout()
fig.savefig(output / 'propagation.png', dpi=160)
print('图片位置：', (output / 'propagation.png').resolve())
if SHOW_PLOT and not INTERACTIVE_VIEWER:
    plt.show(block=True)
plt.close(fig)
if SHOW_PLOT and INTERACTIVE_VIEWER:
    viewer = view_field(saved_field, (x_um, y_um), z_um)
    plt.close(viewer.figure)
```

此脚本只可视化保存的数据，不重新判断收敛；核验状态请查看原运行目录的 `checks.json`（第4节）或 `result.json`（内置示例）。增大 `store_every` 后，图中的z方向也只包含已保存截面。

## 10. 判断结果是否可信

先看 `result.diagnostics['checks_passed']`，再看 `checks['passed']`；两者都为True才表示当前数值检查通过。

| 检查 | 门槛 | 超限时首先排查 |
| --- | --- | --- |
| 最大相对功率漂移 | <1e−8 | 减小step_um，检查传播精度 |
| 边缘功率比例 | <1e−4 | 扩大横向窗口，同时保持空间分辨率 |
| 高频谱比例 | <1e−6 | 减小横向网格间距，检查形状是否过尖锐 |
| 半步长末端复场相对L²差 | <0.002 | 进一步减小传播步长 |
| 半横向间距末端复场相对L²差 | <0.002 | 增加横向点数 |
| 扩大窗口末端复场相对L²差 | <0.002 | 检查窗口边界影响 |

自动收敛检查会重算4次：主网格、半步长、横向点数加倍、保持间距将窗口扩大1.5倍；输入/折射率均重新按坐标生成。空间加密后还要满足RK4稳定性，原来的step_um可能需要减小。

数值检查通过说明离散结果相互一致，不能代替真实材料参数、模型适用性和实验验证。窗口采用周期边界，触边的光可能从另一边出现，不应把这种回绕解释为真实器件行为。

## 11. 一维入门与存储控制

只计算一个横向维度时，所有横向参数改为长度为1的元组：

```python
grid_1d = Grid(windows_um=(48.0,), points=(64,), length_um=20.0, step_um=0.1)
guide_1d = Waveguide(lambda z,q: np.exp(-(q[0]/3.0)**2), 1.453, 1.45)
launch_1d = gaussian_beam(waists_um=(3.0,))
result_1d = simulate(grid_1d, guide_1d, launch_1d)
print(result_1d.field.shape)  # (201,64)，一维平板模型，省略了y方向
```

大计算可使用 `simulate(grid, guide, launch, store_every=10)`，仍按原步长推进和诊断，只每10步保存一次，输入面和末端始终保存。不要把store_every当作传播步长。

每次最多存1600万个复值。complex128场数组约占 `保存帧数 * Nx * Ny * 16` 字节；这不含RK4临时数组、intensity属性产生的数组、FFT和收敛复算内存。先用小规模配置验证，再扩大计算规模。

例如第4节的 `(201,64,64)` complex128场约占12.6 MiB。一次读取后，滑块直接使用该复场数组；查看器额外保存较小的x-z积分图，并只计算当前截面的强度/相位，不另外展开整个强度和相位体积。NPZ为压缩格式，不能通过 `mmap_mode` 将其中的场数组直接映射为按需访问；当前查看器仍需足够内存一次容纳全部已保存复场。“所有点”始终指有限计算网格；增大 `STORE_EVERY` 会减少可浏览的z截面。

## 12. 常见问题

| 问题 | 处理方法 |
| --- | --- |
| `No module named waveguide_sim` | 在项目根目录安装，确认运行脚本和pip使用同一解释器 |
| RK4 step exceeds stability limit | 按异常给出的上限减小step_um，细化后重新检查 |
| initial_field must ... match grid.points | 检查输入场数组形状，一维是(Nx,)，二维是(Nx,Ny) |
| absolute index requires ... | 返回绝对n，核对参考折射率及弱导引条件；不要删掉保护检查 |
| stored fields exceed ... | 增大store_every或缩小计算规模 |
| FileExistsError | 指定一个尚不存在的输出目录/文件，不覆盖旧实验 |
| 输出是复数 | 正常；用abs(field)**2看强度，用np.angle(field)看相位 |
| 场有结果但checks是False | 保留失败数据，按第10节诊断和细化，不能标为已验证结果 |

包自检：`python -m unittest discover -s tests -v`。完整模型、误差门槛及资源契约见 [RK4契约](agent/rk4-package.md)。
