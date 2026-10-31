# 通用傍轴光场传播交付（2026-10-30）

新增 `bpm.py`、`run_bpm.py`、二维配置 `bpm_example.json` 和一维波长扫描配置 `bpm_scan_example.json`，均在正式 src/ 内。启动器新增 `-Scenario bpm`，双击根目录 `运行通用光场仿真.cmd` 可重新计算并打开报告。旧coupler/LAMP流程保持原入口。

方程为 i∂zψ=[−∇⊥²/(2k₀n₀)−k₀(n²−n₀²)/(2n₀)]ψ。支持1/2个横向维度、沿z中点取势的Strang分步FFT、多条高斯增量和缓变路径/半宽/增量、解析高斯输入和直接API复输入/实折射率回调。配置扫描为单路径离散候选；逐候选进行完整复场的步长、网格、窗口收敛检查。前向标量傍轴、周期边界，无吸收层。输入与输出/单位/坐标/错误/模型限制见[完整契约](../agent/general-bpm.md)。物理参数均 assumed_not_measured。

## 数值验证

运行 `simulate-optics.ps1 -Test`：29项通过，约97.9秒，其中8项通用BPM测试（原有21项保留）。新增二维解析高斯衍射与倾角位移、二维自由传播可分离性、随z均匀势精确相位、GRIN谐振子质心、原一维内核复场交叉核对、移动/渐变波导完整复场收敛、边界污染明确失败、扫描与输入校验。测试输出保留于 `artifacts/optics/bpm-validation-initial/final-tests.txt`。

初次29项检查有2项科学失败和1项环境错误，详见 `artifacts/optics/bpm-validation-initial/failures.txt`。二维示例64µm窗口出现边缘功率0.01019、扩大窗口场差0.04888；128µm窗口边缘约9.35e−5，但场差0.004327仍失败。128µm失败端到端产物保留于 `artifacts/optics/general-bpm-delivery/`，不作为已验证交付。最终窗口192µm、384点，dx=0.5µm；未降低任何门槛。GRIN基准扩大解析对照窗口并减小步长，6位小数判据不变。原报告测试的Python临时目录在普通受限执行中无法写入；最终通过授权执行完整测试，未修改或跳过测试。

二维端到端：`simulate-optics.ps1 -Scenario bpm -Output artifacts/optics/general-bpm-delivery-v2`。

| 检查 | 实际值 | 门槛 |
|---|---:|---:|
| 半步长输出复场 L²差 | 1.677335e−4 | <0.002 |
| 半网格复场 L²差 | 2.501639e−14 | <0.002 |
| 同dx窗口×1.5复场 L²差 | 6.025748e−5 | <0.002 |
| 四种复算最大功率漂移 | 1.334488e−13 | <1e−8 |
| 四种复算最大边缘功率 | 1.296435e−6 | <1e−4 |
| 四种复算最大高频功率 | 3.812691e−21 | <1e−6 |

二维默认500µm传播后，相对总功率约1，质心 (−0.840598,1.136232)µm，指定x∈[0,10)、y∈[−6,6)区域功率0.357326。这是输入高斯在假设折射率中的相干演化，不是本征导模注入、端口效率或实测芯片。

一维三波长扫描端到端：`artifacts/optics/general-bpm-scan-delivery/`。所有候选通过；0.76/0.78/0.80µm末端ROI功率分别0.377224/0.400012/0.422112；只在这三个离散假设中选0.80µm，不宣称最优器件或真实材料的波长性能（未建色散模型）。最大窗口场差7.259e−5。

## 展示与交付

index.html 包含 x-z 投影、截面播放、z/质心/ROI读数、参数和诊断、JSON/NPZ/来源下载。PNG与NPZ保存完整窗口数据；NPZ包含原始complex128场，报告只显示强度。二维报告x-z图对y积分，横截面y向上。每案例共用帧色标，不跨案例归一比较。所有报告离线运行。

使用 agent-browser 独立会话检查一维扫描报告：所有图片加载成功；播放至第5帧时z=50µm、质心−3.975µm、区域功率1.772%，读数随帧更新；暂停正常；390px视口scrollWidth=390，无横向溢出。截图 `artifacts/optics/general-bpm-scan-delivery/browser.png` 已目视核对。报告显示校验不替代数值与模型验证。

能力清单同步新增 `optics.general_paraxial_bpm`，当前3项均agentExposed=false。JSON进程调用约定为后续Agent封装预留；未实际注册任何MCP/Agent工具。未访问Agamemnon设备、设置、日志，也无加工导出。

最终二维报告补充检查：末端滑块 z=500µm，质心(−0.841,1.136)µm，区域功率35.733%，与JSON舍入一致；全部图片加载，390px宽度无溢出。宽屏/窄屏截图分别为 general-bpm-delivery-v2/browser.png 与 browser-mobile.png。两组端到端产物的JSON状态、NPZ有限复场与形状/采样坐标、manifest所列源码和输出哈希均已逐项核对通过；截图为后续QA产物，不在运行时manifest清单内。
