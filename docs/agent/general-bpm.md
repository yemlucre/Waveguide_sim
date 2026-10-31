# 通用傍轴光场传播契约

2026-10-30维护：本页为旧分步报告API契约；其唯一数值实现迁至 `src/waveguide_sim/bpm.py`，旧路径仅导入适配。新通用编程入口采用[Python包/RK4契约](rk4-package.md)，不要把本页的二阶Strang算法描述用于新 simulate API。

检查日期 2026-10-30。能力 `optics.general_paraxial_bpm`，模型 `general-paraxial-1`。独立理论计算，agentExposed=false，尚无工具注册。与旧双波导、LAMP 离散模态能力并存；不改写旧结果。所有示例物理参数 `assumed_not_measured`。

## 物理模型和坐标

从标量 Helmholtz 方程取 E=ψ exp(i k₀n₀z)，忽略 ∂²zψ，得到

`i∂zψ = [−∇⊥²/(2k₀n₀) − k₀(n²−n₀²)/(2n₀)]ψ`。

z 对应薛定谔演化参数，折射率形成势阱。跟踪的是复光场、干涉、衍射与功率输运，不是单个光子的轨迹。采用中点势 + 对称分步 FFT，纵向二阶。仅单向、标量、线性、静态介质；结构可沿 z 变化。一个横向维度是平板模型；两个横向维度是具有三维折射率几何的 **2+1D 傍轴 BPM**，不等于全矢量三维 Maxwell 求解。

所有长度 µm，真空波长 µm，折射率无量纲；输入 tilt_rad 为横向相位梯度除以 k₀n₀，小角度近似，单位 rad。x/y 横向、z 传播，原点是窗口中心/输入面，无设备坐标映射。网格 x_j=(j−N/2)dx，数组顺序 `(sample,x)` 或 `(sample,x,y)`。场只在输入归一化一次，∫|ψ|²dA=1；一维强度 1/µm，二维强度 1/µm²。功率相对输入无量纲。

FFT 周期边界、无吸收层，无逐步归一化，无真实材料吸收、非线性、偏振、背向反射、热效应、色散或工艺模型。光场可从芯区辐射至背景，但触边后有周期回绕风险，不能将其视为可信弯曲损耗。几何缓变约束不保证所有输出均傍轴，需检查实际光谱与独立电磁/实验数据。

## 共用数值 API

- `src/Agamemnon.Optics/bpm.py`：`Grid.validate`、`axes`、`guide_at`、`index_profile`、`gaussian_input`、`propagate`、`verify`，仅 NumPy，不访问界面/设备/Agent。
- `propagate(grid, guides, initial, index_fn=None)`：initial 为同网格有限非零复场；自定义回调 `index_fn(z_um,sparse_coordinates)` 返回同网格实数 dn。回调由调用者负责平滑性和物理来源；旧高斯JSON入口保持不变；新增[Python场景入口](python-scenes.md)支持自定义折射率/复场及完整自动verify。支持负 dn 回调，要求 |dn|/n₀≤0.01。API 不将回调声明为已注册 Agent 工具。
- `verify(grid,guides,launch,index_factory=None)`：launch(grid) 在每种网格重新生成同一解析输入，比较整个输出复场，保留全局相位差；不适用于单独采样但没有重采样约定的外来场。
- `run_bpm.py`：`cases` 展开离散扫描，`run_study(spec)` 返回 result 字典和完整 runs；写文件与 HTML 在 CLI 层。同步无队列、重试、超时或续算；调用方用独立进程设时限。数值异常向上传播。

## JSON 输入和资源限制

可直接复制 `bpm_example.json`（两条波导、二维横截面、弯曲＋渐变宽度），或 `bpm_scan_example.json`（一维波长扫描）。根键：

- `grid`：wavelength_um、background_index、windows_um、points、length_um、step_um、samples。维度1或2；points 每轴为32..1024且4的倍数（完整CLI收敛要求为8的倍数）；samples 2..401；最多100000步；单次储存不超过1600万复数。CLI 预留×2点数、×1.5同dx窗口和半步长，因此主网格每轴≤512，实际限制还受样本预算约束。
- `guides`：0..64条高斯波导。每条只含 `knots`，2..100个节点；每节点 `z_um, center_um, radii_um, delta_index`。必须覆盖0与总长，z严格递增。节点间以 `3t²−2t³` 插值位置、半宽和增量，因此节点斜率为0；节点间二阶导数可跳变，不声称为任意光滑路径。适合有限节点的缓弯/锥形/多通道；复杂分叉需用重合与分离的多条高斯定义，并自行确认合成折射率含义。
- 高斯折射率增量为 `dn=ΣΔn exp(−Σ((q−c)/r)²)`，r为折射率增量1/e半宽，不是硬芯径或模式场半径。CLI Δn非负，各通道最大Δn之和/n₀≤0.01；每半宽≥4格，距离窗口边界≥4半宽；中心路径最大斜率范数与每轴半宽斜率≤0.1。这些是数值与模型保护界限，不是设备规格。
- `input`：center_um、waists_um、可选tilt_rad，幅度 exp(−Σ((q−c)/w)²)，w是场1/e、强度1/e²半宽，既非本征导模也非实测输入；最少4格/半宽、边界4半宽，倾角范数≤0.1。直接 API 支持任意有限复输入。
- 可选 `roi_um`：每轴 `[lower,upper]`，位于窗口内且包含网格点。按 lower≤q<upper 离散积分，包含尾场与辐射，**不是分离端口导模效率**。没有 ROI 时只传播，不选设计。
- 可选 `scan`：`{"path":"grid.wavelength_um","values":[0.76,0.78,0.8]}`。1..12个候选；路径以 grid/guides/input 开头，点分隔键或0起点数组下标，必须引用已有参数。可替换标量或整个数组，例如 input.waists_um 或 guides.0.knots.1.center_um。这是单路径离散扫描，复杂组合由外部编排多次调用。改变总长还须同步节点终点，不能只改一个值造成不一致。

## 调用与机器输出

```powershell
.\simulate-optics.ps1 -Scenario bpm -OpenReport
.\simulate-optics.ps1 -Scenario bpm -Config src/Agamemnon.Optics/bpm_scan_example.json
# 为后续 Agent 使用显式参数列表调用，不拼接来自用户的 shell 命令：
python src/Agamemnon.Optics/run_bpm.py --config request.json --output artifacts/optics/new-request-id
```

Agent 集成建议：白名单限制配置及输出路径于本项目、使用进程参数数组、设置资源/时间上限、读取退出码与 result.status、核验 manifest；失败或中断不得当设计成功。只是调用协议建议，未在任何 Agent/MCP 运行时注册或验证。

退出 0=`verified_theoretical_propagation`，2=`numerical_checks_failed`，1=捕获的配置/文件错误（stderr JSON status=error）；启动、系统/内存异常、中断另遵循进程状态。stdout 是精简 JSON，详细结果为 result.json。默认新时间戳目录；指定目录必须为空。创建后先存 input.json，计算失败可能只有输入或部分文件，不自动覆盖/清理。保留旧结果与失败记录。

输出 `fields.npz`（allow_pickle=False）：case_i_fields、case_i_x_um、可选y_um、z_um、centroid_um、可选roi_power。result.json 包含全部展开输入、来源标记、状态、归一化前输入功率、全步诊断、各候选收敛检查及最终ROI。best_verified_roi_case 是已通过候选中末端 ROI 功率最大者的0起点下标，无合格候选为null；不是全局最优，也不是预定耦合比例或最短长度优化。

index.html 离线截面播放、x-z光强图、质心和区域功率、参数/检查/数据下载；播放仅浏览已有样本。二维 x-z 图对 y 积分；横截面横轴x、纵轴y，色标在单案例帧内固定，不同案例不可直接比较颜色。PNG 行为等间隔选出的步号，真实z以读数/NPZ为准。manifest 包含版本、平台、Python/NumPy、输入/源码/输出 SHA256，自身不自哈希。

## 验证门槛

每个候选都做步长减半、dx/dy减半、同dx/dy窗口×1.5复算。输出复场 L²差每项<0.002（网格比较用嵌套点，窗口比较裁取原窗口）；全步功率漂移<1e−8、边缘 |q|≥0.4W 的并集功率<1e−4、任意轴 |k|≥0.8Nyquist 的光谱功率<1e−6。高频门槛监视网格分辨率，不是完整傍轴角谱有效性证明。四次复算及主扫描都要过边缘/守恒/高频检查。逐候选通过只意味着该离散输入的数值一致性，不是物理标定。

`tests/test_optics_bpm.py`：二维解析高斯衍射/倾角质心、二维可分离与一维对照、随z均匀势精确相位、GRIN谐振子质心、旧求解器复场交叉核对、动态曲线收敛、失败不冒充验证、扫描与非法输入。完整记录见 [交付报告](../reports/general-bpm-20261030.md)。

理论背景：[RP Photonics 数值光束传播](https://www.rp-photonics.com/numerical_beam_propagation.html)、[傍轴近似](https://www.rp-photonics.com/paraxial_approximation.html)。后续设计仍需真实折射率、输入模式、波长色散、损耗及加工映射标定；导模投影、吸收边界、自动多变量优化和全矢量求解未实现。

