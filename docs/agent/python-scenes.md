# Python 场景接口 v1：固定工具、替换物理输入

2026-10-30维护：本页属于兼容的旧场景/分步报告流程。新的通用编程入口是 `waveguide_sim` Python包，默认经典四阶RK4，见[包契约](rk4-package.md)。

检查日期：2026-10-30。扩展现有 `optics.general_paraxial_bpm`，未增加运行时工具注册，agentExposed=false。数值方程、傍轴弱导引假设、单位、周期边界和原有误差门槛见 [通用BPM契约](general-bpm.md)。目前没有材料、波导或输入光实测数据，全部示例参数均为 `assumed_not_measured`；验证通过仅指离散计算一致。

## 日常使用

在根目录用具有 NumPy/Pillow 的 Python 运行：

```powershell
python simulate.py --open-report
python simulate.py --scene src/Agamemnon.Optics/scene_example.py
python simulate.py --parameters src/Agamemnon.Optics/scene_scan_overrides.json
python simulate.py --test
```

双击 `运行通用光场仿真.cmd` 会转调现有环境的 Python、运行默认 Python 场景并打开报告；PowerShell 快捷入口为 `simulate-optics.ps1 -Scenario python`。命令行计算入口、场景、数值内核和数据导出均为 Python，PowerShell/CMD仅为本机找解释器和打开结果的便利入口。旧 `-Scenario bpm` 高斯JSON、coupler和lamp均保留。

日常修改 `src/Agamemnon.Optics/scene_example.py` 顶部 `PARAMETERS`：波长、背景折射率、窗口、点数、长度、步长、样本数、间距、半宽、增量、弯曲量、输入束腰、两光斑幅度与相位。不需修改 bpm.py/python_scene.py/run_bpm.py。需要比较多个值时设置：

```python
SCAN = dict(parameter='gap_um', values=[8., 10., 12.])
OBJECTIVE = 'target_overlap'  # 或 'roi_power'
```

需要全新的折射率形状或复场公式时修改场景中的函数，保留固定求解器。示例为两条四次超高斯折射率增量，一条沿z缓移，输入为两个带相对幅度/相位的高斯场的相干叠加；目标是右侧假设高斯模板，不是本征导模。

## 稳定场景协议

独立可信 `.py` 文件导出：

- `API_VERSION = 1`；`PARAMETERS` 为可JSON序列化、有限数值组成的参数字典；可选 `DESCRIPTION`。
- 可选 `SCAN = None` 或 `dict(parameter='已存在的顶层参数名',values=[...])`，最多12项。候选深复制，不修改默认参数。复杂组合可把一个参数定义为数组/字典，或由调用方分别运行。
- `OBJECTIVE` 可为None（只计算光场，默认）、roi_power或target_overlap。设置比较指标时，分别要求Scene提供roi_um或target_field；只计算光场则两者均可不提供。
- `build(parameters) -> python_scene.Scene`，场景对象持有：

```python
Scene(
    grid=Grid(...),
    initial_field=lambda grid, coordinates: complex_field,
    refractive_index=lambda grid, z_um, coordinates: absolute_real_index,
    roi_um=[[xmin, xmax], [ymin, ymax]],  # 一维只保留第一项，可选
    target_field=lambda grid, coordinates: complex_output_template,  # 可选
    description='assumed ...',
)
```

`coordinates` 是稀疏meshgrid，indexing='ij'：一维 `(x,)`，二维 `(x[:,None],y[None,:])`。实际由 axes(grid) 生成，所有长度µm。自定义输入/目标场必须返回与 grid.points 完全相同形状的有限非零复数组。折射率函数返回**绝对实折射率 n**，可以是广播到网格的标量/数组；适配器自动转换为底层 dn=n−n₀，要求 n>0、|n−n₀|/n₀≤0.01。不要把增量直接当绝对n返回。

函数应为确定性的空间数学模型，在每种网格上重新求值，不能绑定主网格数组，也不能依赖调用次数或未固定的随机状态。允许任意形状与复振幅/相位表达式，但必须符合傍轴、弱折射率、实数无损介质假设，且空间/纵向变化可被所选网格/步长分辨；不保证所有函数都能通过数值检查。采样实测数组未来可在回调中用物理坐标插值并显式约定窗口外背景，工具不会擅自猜测文件单位或填充规则。本次无实测数组导入示例。

新场景需自行说明几何、参数单位和来源；例子的参数保护只属于该例子，不限制自定义形状必须高斯。统一协议检查数组、有限性、绝对n范围和资源预算；复杂结构的平滑性和有效傍轴性还需建模者判断。采样回绕与高频风险由固定诊断和收敛检查处理。

## 验证与指标

Scene.preflight 在主网格、半步长、双点数、同dx/dy扩大1.5倍窗口上重新生成输入/目标场，并在z=0、L/2、L检查折射率。随后每个传播步在真实中点检查n，每种复算使用对应网格重建折射率函数。所有候选均使用原门槛：输出复场L²差每项<0.002、功率漂移<1e−8、边缘功率<1e−4、高频功率<1e−6，主扫描也要通过全步诊断。没有关闭验证的快捷选项。

`target_overlap = |∫t*ψ_out dA|² / ∫|t|²dA`，输入已归一化到单位功率，t为提供的目标复场。相位影响此指标；它是指定模板中的投影功率，**仅在目标确为已验证导模时才可解释为对应模功率**。当前模板不满足这项额外证明。roi_power沿用半开矩形积分，包含尾场和辐射。

result.best_verified_case 为按OBJECTIVE最大化的已通过候选下标；无通过者为null。best_verified_roi_case保留兼容旧消费者，是独立按ROI选择的下标，可能与OBJECTIVE的选择不同。不能只读best_verified_roi_case就推定目标光场最佳。没有全局优化、自动选材或真实工艺参数建议。

单次Grid最多1600万采样复值、整个研究最多3200万采样复值（不含临时FFT/折射率/展示内存），最多12候选/100000步；固定收敛要求主网格点数每轴≤512，且为8的倍数以容纳×1.5窗口网格。内存仍依赖维数、样本数和候选数。取消/限时由调用方终止进程，无内部任务队列或自动恢复。

## 输出与未来Agent调用

Python入口不需要JSON；可选 `--parameters overrides.json` 供外部编排，根键仅 parameters（覆盖已存在顶层键）、scan（可设null取消）、objective。原始覆盖保存为input.json，**全部实际默认值和展开后的参数**保存在result.cases[i].input.python_parameters。

stdout为UTF-8精简JSON，退出0=verified_theoretical_propagation，2=numerical_checks_failed，1=捕获的输入/文件/模块协议错误。运行场景时普通print转到stderr，异常数值/用户代码的未捕获错误仍可有traceback，应同时检查进程状态。失败、中断、被终止的进程不得当成功。默认创建新时间戳目录；已有非空输出目录拒绝覆盖。先存输入和场景源码，失败保留部分产物。

fields.npz新增 `case_i_refractive_index`（与复场相同z/xy网格上的绝对实n）与 `case_i_target_field`（单位功率归一化的目标复场，可选），保留复场、坐标、质心和ROI。读取用allow_pickle=False。折射率在保存截面上额外求值，传播实际使用中点值；采样n不能代替全部纵向计算网格。index.html可切换光强、相位、折射率增量；相位范围−π..π，光强低于全案例峰值1e−6的相位遮黑；折射率以±max|n−n₀|定色标。PNG/NPZ为完整窗口，不自动裁剪物理数据。

scene_source.py为运行时复制的场景源，result包含路径与SHA256；manifest保存场景副本/输入/输出、正式源码、根simulate.py和环境版本哈希。建议将场景写为独立文件；Python允许导入其他模块，但自动哈希不递归追踪场景目录外自定义依赖，外部依赖需调用方另行归档。场景是可信的**可执行Python代码**，不是隔离的数据配置解析器；本轮不建立远程代码接收服务。

后续Agent只需用进程参数数组调用 `python simulate.py --scene ... --parameters ... --output ...`，设置外部超时，读取退出码、result.status与best_verified_case，必要时读取NPZ。当前仅本地CLI/API验证；没有Agent/MCP注册、硬件接口或加工导出。

测试与交付见[验证记录](../reports/python-scenes-20261030.md)。

