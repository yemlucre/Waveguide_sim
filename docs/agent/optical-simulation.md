# 理论波导仿真（独立 Python 内部能力）

2026-10-30 迁移更新：本模块已独立存放于桌面“波导理论仿真”，本文件及全部相对链接随迁移保留。原Agamemnon只保留迁移索引；本项目能力清单只有1项理论能力，无MCP注册。[迁移记录](../reports/migration-20261030.md)。

检查日期：2026-10-30。Agamemnon 桌面版本仍 1.0.1；本模块 `slab-ssfft-1` 独立运行，不随桌面加载。已实现正向仿真、离散间距/长度搜索及离线报告；agentExposed=false，无 MCP 注册或产品按钮，没有对设备的访问。能力 ID `optics.theoretical_coupler`。

## 共用入口与模型

- [optics.py](../../src/Agamemnon.Optics/optics.py)：`Parameters.validate`、`eigensystem`、`launch_mode`、`propagate`、`find_design`。纯数值业务，无 UI、弹窗、设备或 agent 依赖。
- [run.py](../../src/Agamemnon.Optics/run.py)：`verify_candidate` 与 CLI，组织验证、导出及结构化退出码；[report.py](../../src/Agamemnon.Optics/report.py) 只做展示；[启动入口](../../simulate-optics.ps1)。[配置/使用](../../src/Agamemnon.Optics/README.md)。
- i∂ψ/∂z = Hψ，H = −∂²x/(2k₀n₀) − k₀(n²−n₀²)/(2n₀)。标量、线性、傍轴、弱导引、静态平行波导；单横向 x，另一横向不变，是平板模型，不能冒称三维埋入式波导。
- 两个高斯折射率增量相加；radius_um 是增量 1/e 半宽。输入是孤立左波导数值基模，加入右波导后传播；输入一次归一化，不逐步归一化。对称分步 FFT、周期边界、无吸收层。没有散射/材料损耗/反射/偏振模型。
- 所有内部长度 µm；x=横向、z=传播、原点为两中心的中点/输入面，右侧 x>0，和设备 XYZ 无映射。波长为真空波长，折射率无量纲。场规范为 ∑|ψ|²dx=1，强度单位 1/µm，功率为相对输入的无量纲量。

## 输入/限制/输出/错误

配置是 example.json 同结构；参数必须有限正值，points 为 128..2048 偶整数，增量/背景≤0.01，中心距≥2radius，窗口≥中心距+12radius，每半宽≥6格，单次≤100000步。CLI 预留×2网格、×1.5窗口的验证空间，因此配置 points 实际≤1024 且其×1.5仍需为偶整数；最多12个间距候选，target∈(0,1)。这是模型/资源限制，不是设备限制。默认值来源全部 assumed_not_measured，不是材料规格、论文参数或运行回读。

`propagate` 返回 x_um、z_um、复场 samples×points、左右半空间功率、全步最大功率漂移/边缘功率、实际步长。左右功率是半空间积分，包含尾场与辐射，不是分离端口导模效率。`find_design` 对每间距找首次向上穿越目标值的位置，采样插值后重新传播验证；仅在给定离散间距中选最短长度。无穿越返回 target_not_reached / null，不能把最后一个值当成功。

所有计算同步，无内部任务队列、超时、重试/续算；调用方可用进程中断，部分输出保留。非法输入 `ValueError`；文件错误 `OSError`；NumPy 数值/内存错误传播。CLI 输出结构化状态，0=verified_theoretical_candidate，2=target_not_reached/numerical_checks_failed，1=捕获的输入或文件错误。进程本身还有启动失败/中断等系统状态。Python 共用方法不会吞掉异常。

## 存储和验证

默认 artifacts/optics/时间戳，显式输出必须为空；失败可能部分写入，无原子发布/自动覆盖。result.json 包含全部输入、模型版本、UTC运行时间、assumed标记、候选、重算结果及诊断；fields.npz 保存各间距的完整复场采样/坐标/功率，读取不需要 pickle；PNG 为科学图，HTML 内嵌图片/数据，可离线浏览。manifest.json 包含 Python/NumPy/Pillow/平台、源码与输出 SHA256（自身不自哈希）。不接触现有设置/日志/项目文件。计算文件受根 artifacts 忽略规则管理。

2026-10-30：9项科学/边界回归通过，见 [tests/test_optics.py](../../tests/test_optics.py)；包含解析高斯衍射、单导模保持、独立本征分解传播比较、加密/步长/窗口复算、间距趋势、搜索重算、不可达/无效输入、周期边缘风险。默认端到端输出 [报告](../../artifacts/optics/coupler-theory-delivery/index.html)、result.json 与 manifest。逐图已目视核对；宽屏与390px窄屏无横向溢出，切换至12µm、滑块10mm时读数左54.96%/右45.04%，观察线同步；[交付记录](../reports/optics-theory-20261030.md)。没有改动 .NET 源码或引用，因此本轮只运行独立 Python 回归/端到端，不构建桌面EXE，根快捷方式无新构建目标。

判据：全扫描功率漂移<1e−8、边缘区域 |x|≥0.4窗口 的功率<1e−4；候选处步长减半、dx减半、同dx窗口扩大1.5倍，右侧功率绝对差均<0.002；直接本征演化对照场L²误差<0.01；重算目标绝对误差<0.002。只对选中候选做收敛复算，其他曲线只有守恒和边缘监测，不能宣称全参数空间已收敛。

初次探索含8 µm间距、5 µm步长：20 mm扫描边缘功率约1.75e−4，未通过，原失败产物保留 artifacts/optics/first-theory。最终明确将演示搜索区间改为10..18 µm，步长2 µm，未降低阈值；8 µm不属于本次最终已验证候选范围。早期解析高斯测试因传播过长使自由光束触及周期窗口而失败，改为窗口内短距离基准；测试判据未放宽。

当前数值基准不替代独立三维电磁验证。真实折射率、模式场、材料/损耗、端口分离、弯曲、波长/加工容差、实际工艺映射均待后续研究/实验确认。无实机操作、未训练模型或向内置Agent开放工具。

参考：[Optiwave FD-BPM 假设](https://optiwave.com/tutorials/introduction-2/)、[NumPy FFT](https://numpy.org/doc/stable/reference/routines.fft.html)。


## 报告v2与通用性说明（2026-10-30）

数值求解器 optics.py 未变。report.py 的 build_report_data 只构建展示数据，write_report 从 report_template.html / report_ui.js 生成离线HTML；不依赖外部库、字体或网络服务。完整功率数组保持精度；只为显示裁取中央±25µm（小窗口时按0.45窗口裁取），最多约384横向点，强度取8位小数。NPZ保存完整原始复场；横向波导背景范围只作中心附近提示，不定义硬边界。各间距共用绝对强度色标。

报告新增：候选参数/状态概览、间距切换、播放/暂停（离散采样浏览）、目标附近定位、联动功率/光场/截面、静态折射率分布、多间距右侧功率比较、真实参数及单位、8项实际诊断与判据、CSV/PNG/JSON/NPZ下载、浏览器打印入口。目标定位选择最近采样，独立重算候选结果单独显示。没有候选/数值失败时不宣称成功；未执行的诊断显示“未执行”。浏览器Blob CSV只由已计算功率数组生成，切换时撤销旧URL。

simulate-optics.ps1 -Test 改为发现 test_optics*.py，覆盖数值与报告测试；open-report.ps1 按报告文件修改时间选择最新index.html，-PathOnly用于只读验证路径，中文cmd入口转调该脚本。新运行仍创建新目录，旧报告/数据未覆盖。run.py的source_hashes新增模板/交互脚本，避免只哈希Python而遗漏展示源码。

适用范围：当前JSON/自动搜索仍只支持双高斯平行平板波导。propagate接口支持自定义复输入及固定非负弱折射率增量dn数组；已有均匀介质高斯衍射、单波导和双波导验证。多波导静态数组可表达，但没有通道模式效率、独立场景配置或对应基准，不能称为完整支持。沿z变化、弯曲/分叉/锥形、第二横向维度、三维/矢量/反射/非线性/真实损耗未实现。通用BPM能处理的现象不等于本实现已支持。

验证记录、输出与检查边界见[报告v2交付](../reports/report-v2-20261030.md)。不新增仿真能力ID、注册工具或硬件权限。

## 2026-10-30 通用核补充

以上“沿z变化/第二横向维度未实现”均指此旧coupler能力。新增独立 optics.general_paraxial_bpm 及 `-Scenario bpm`，其输入/输出、缓变几何、逐候选验证、限制和Agent状态见[通用契约](general-bpm.md)。当前能力清单共3项，均agentExposed=false；旧求解器和搜索/报告保留。
