# Python 仿真包契约 v0.2

检查日期：2026-10-31。能力 `optics.rk4_field_simulation`；正式包 `src/waveguide_sim/`，仅依赖 NumPy。独立理论计算，无设备操作或 Agent/MCP 注册，agentExposed=false。示例全部为 `assumed_not_measured`。v0.2移除全部旧报告/分步流程和未被RK4使用的Grid.samples参数，数值方程、RK4推进及误差判据不变。

## 安装与编程入口

在项目根目录执行 `python -m pip install -e .`，随后任意 Python 程序可导入：

```python
import numpy as np
from waveguide_sim import Grid, Waveguide, gaussian_beam, simulate, check_convergence

grid = Grid(
    wavelength_um=0.78, background_index=1.45,
    windows_um=(48., 48.), points=(64, 64),
    length_um=20., step_um=0.1,
)
# assumed：椭圆渐变折射率截面；中心可随 z 改变，实现弯曲/分叉几何。
guide = Waveguide(
    shape=lambda z, q: np.exp(-((q[0]-z/20)/3)**2-(q[1]/4)**2),
    core_index=1.453, cladding_index=1.45,
)
launch = gaussian_beam(waists_um=(3., 4.))
result = simulate(grid, guide, launch)
psi = result.field                 # (Nz, Nx, Ny)，复包络
intensity = result.intensity       # |psi|²
x_um, y_um = result.axes_um
z_um = result.z_um
checks = check_convergence(grid, guide, launch)
result.save('my_new_fields.npz')    # 文件已存在则拒绝覆盖
```

`python -m waveguide_sim` 执行包内二维弯曲渐变折射率示例，保存每个传播步场和收敛结果到新建 `artifacts/rk4/<时间戳>/`。`--output` 可指定新的目录，已有目录即拒绝。只计算与导出，不依赖报告、Pillow 或浏览器。结果退出0表示数值检查通过，2表示未通过，配置/用户回调异常直接抛出并以非零退出。失败留下已写文件。

## 模型、单位与坐标

取 `E(x,y,z)=psi(x,y,z) exp(i k0 n0 z)`：

`d_z psi = i laplacian_perp(psi)/(2 k0 n0) + i k0 (n²-n0²) psi/(2 n0)`。

横向采用 FFT 谱微分；沿 z 用经典四阶段四阶 Runge–Kutta：

```
k1 = F(z, psi)
k2 = F(z+h/2, psi+h*k1/2)
k3 = F(z+h/2, psi+h*k2/2)
k4 = F(z+h, psi+h*k3)
psi_next = psi + h*(k1+2*k2+2*k3+k4)/6
```

中点折射率供 k2/k3 共用，端点各自求值；没有用分步法代替 RK4。四阶是足够光滑方程下的纵向全局精度；硬边界沿 z 穿过网格可能降阶，需要额外收敛检查。

所有长度 µm；n 无量纲。x/y 是横向窗口中心坐标，z=0 是入射面，无设备坐标映射；x_j=(j−N/2)W/N，数组 indexing='ij'，一横向维度输出 `(Nz,Nx)`、两横向维度输出 `(Nz,Nx,Ny)`。输出为包络，若需要标量载波场可乘 `exp(i*k0*n0*z)`；不包含光学时间振荡。默认不归一化输入或任何传播步，振幅、相位及输入功率均保留。场单位由用户输入约定，强度为场单位平方，积分功率再乘 µm 或 µm²，不自动等同 W 或 W/m²。

## 输入与采样

- `Grid` 定义于 `src/waveguide_sim/grid.py`：横向1或2维，每轴32..1024点、4的倍数、正窗口；正波长、背景n、总长、步长；最多100000步。截面保存仅由 `simulate(..., store_every=...)` 控制。v0.1传入的 `samples` 参数请删除，v0.2不再接受该参数；实际存储预算在simulate中根据真实保存步数检查。
- `Waveguide(shape,core_index,cladding_index)`：shape(z_um,q) 返回广播到网格的0..1布尔/连续权重，n=n_clad+(n_core−n_clad)*weight。可以描述圆/椭圆/矩形截面、弯曲、渐变等；不是自动网格化 CAD/STL 导入器。
- 或直接提供 `refractive_index(z_um,q)`，返回绝对实折射率，可为标量或可广播数组。支持多芯、分叉、自定义渐变介质。必须 n>0、|n−n0|/n0≤0.01；各 RK4 阶段都验证。q 为稀疏物理坐标，一维 `(x,)`，二维 `(x[:,None],y[None,:])`。
- `initial_field` 是同形有限非零复数组，或 `launch(q)`；不得依赖固定网格，否则不能做网格收敛。复数直接保存相干幅相。`gaussian_beam` 辅助函数的 waists_um 是场1/e半宽，transverse_k_per_um 是相位梯度 rad/µm。
- 实际步长 h=L/ceil(L/step_um)，恰好到达末端。默认 `store_every=1`，保存每个步号（包括输入和末端）的整个横截面。大计算可设正整数间隔，末端始终保存。“所有位置”指离散计算网格，连续位置要加密或显式插值，并非连续空间精确解。
- 最多1600万存储复值；超限报错，建议增加 store_every。此预算不含 RK4 临时数组或收敛复算；用户仍需管理实际内存。

## 稳定性、检查和输出

设最大横向频率动能 `Tmax=max(sum(kq²)/(2*k0*n0))`；允许的弱折射率给出 `Vbound=k0*n0*(1.01²−1)/2`。要求 h≤2.8/(Tmax+Vbound)，越界报错，不能只按入射光谱选步长。2.8 是略低于恒定自伴离散算子 RK4 虚轴界限 2sqrt(2) 的保守选择；对随 z 快变介质这不构成无条件稳定/精度保证，仍须细化。空间加密会缩小显式 RK4 稳定步长，不能承诺任意精网格效率。

Result 提供 grid、axes_um、z_um、field、intensity、power、diagnostics；每步监视相对输入功率漂移、窗口外侧20%并集能量和各轴超过0.8 Nyquist的谱能量。`diagnostics.checks_passed` 仅表示这三项 <1e−8、1e−4、1e−6，不代表完整收敛。

`check_convergence(grid,index,launch)` 使用主网格、半步长、半横向间距、同间距×1.5窗口；同一物理坐标函数重新生成折射率和输入。末端复场相对L²差分别 <0.002，保留全局相位；全部复算也要通过上述三门槛。点数需为8的倍数且≤512；主步长也须满足最细网格稳定界，否则明确报错，不自动改步掩盖错误。不能给采样数组猜测插值。只有完整收敛和主运行诊断都通过，示例 CLI 才输出 verified_theoretical_propagation。

NPZ 包含 field、z_um、x_um、可选y_um、power、metadata_json；读取 `allow_pickle=False`。元数据含完整Grid、模型名、诊断和未由包标定的参数来源标记。通用API不自动保存用户回调源码，调用方应归档几何/材料来源；示例入口额外保存 input.json、result.json 和包源码/输出哈希 manifest.json。

## 限制与入口

仅单向、线性、标量、弱导引傍轴，周期横向边界，无吸收层、偏振、背反射、矢量Maxwell、非线性或实测材料模型。2+1D 场传播不代表任意三维电磁结构。触边/欠采样仍返回用于诊断的场，但 checks 为false；不自动修正或重新归一化掩盖误差。RK4不严格守恒，需要用功率漂移检查。

旧报告入口、HTML/JS模板、分步求解流程、旧场景协议及专用演示均已删除。`python simulate.py` 为源目录便利入口，执行与 `python -m waveguide_sim` 相同的包内示例，只接受 `--output` 等包CLI参数。旧 `--scene`、`--parameters`、`--open-report` 和 PowerShell 的场景/报告参数不再支持。`simulate-optics.ps1` 仅是调用Python入口/测试的本机助手，无报告或Pillow依赖。

验证：`simulate-optics.ps1 -Test` 运行 `tests/test_optics_rk4.py`；覆盖网格/加密协议、解析平面波四阶率、纵变折射率四阶段、二维高斯解析复场、几何/幅相/全步保存、不稳定与非法输入、弯曲收敛、边界失败及NPZ拒绝覆盖。当前记录见 `docs/reports/python-only-20261031.md`；首次包验证记录 `docs/reports/rk4-package-20261030.md` 为历史证据，其旧入口/文件路径不再作为当前能力说明。

方法参考：[经典RK4系数及稳定区间](https://ketch.github.io/numipedia/methods/RK44.html)。
