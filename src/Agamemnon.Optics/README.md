# 理论波导设计起步示例

日期：2026-10-30。独立 Python 数值模块，不加入 .NET 解决方案，无 EXE、设备依赖或 MCP 注册。

从仓库根目录运行：

```powershell
.\simulate-optics.ps1 -Test
.\simulate-optics.ps1
# 可选：指定 Python、配置及空输出目录
.\simulate-optics.ps1 -Python C:\path\python.exe -Config src/Agamemnon.Optics/example.json -Output artifacts/optics/my-study
```

默认优先使用 Codex bundled Python，否则系统 Python；需要 NumPy / Pillow，声明见 requirements.txt。新环境可自行用 `python -m pip install -r src/Agamemnon.Optics/requirements.txt` 安装。本轮使用本机已有依赖，无安装。输出默认为仓库 artifacts/optics/时间戳目录，已有非空目录拒绝覆盖。退出 0 是通过数值检查的理论候选，2 是目标不可达或数值检查失败，1 是输入/文件错误。失败也可能留下部分文件，重试使用新目录。KeyboardInterrupt 停止计算，返回 Python 默认中断状态，无自动续算。

先打开输出 index.html，切换间距、拖动传播位置，观察左右功率；再看扫描表。比如希望分到右侧一半，就寻找右侧曲线首次穿越 0.5 的位置。继续加长可能重新回到左侧，因此仿真帮助选择尺寸，不是判断“波导越长越好”。

全部默认物理参数为 assumed：真空波长 0.78 µm、背景折射率 1.45、单条波导峰值增量 0.003、高斯增量 1/e 半宽 2.5 µm、间距 10/12/14/16/18 µm；计算窗口 120 µm、512 点、最大步长 2 µm、最长传播 20 mm。间距是中心距，不是边缘空隙。target 为右半空间功率相对输入的目标比例。修改 JSON 后重算才能改变物理参数；报告滑块只浏览已有计算结果。

默认候选：10 µm 中心距、约 3.4214 mm 平行长度、右侧 49.9973%。12 µm 时约 10.6785 mm；更大间距在 20 mm 内未达到目标。目标函数是扫描离散候选中首次达到目标的最短长度，不是全局逆向设计。

下一步应加入第二个横向维度、分离端口、模式重叠指标和几何约束。当前不能推导实际曝光/速度，也不输出加工工程；没有折射率/工艺标定，不能直接称为可加工设计。

复场、JSON、哈希及模型边界见 [agent 契约](../../docs/agent/optical-simulation.md)。

## 通用BPM独立入口

运行 `simulate-optics.ps1 -Scenario bpm`，配置 bpm_example.json；一维扫描配置 bpm_scan_example.json。数值核心 bpm.py，CLI/报告 run_bpm.py，契约 docs/agent/general-bpm.md。新增一个或两个横向维度及沿z变化的高斯波导；本文件前述限制保留为旧coupler流程说明。通用核仍无导模端口效率、吸收层、全矢量或加工标定。退出0仅表示数值检查通过的理论传播。

2026-10-30：推荐根 `python simulate.py --open-report`；Python场景模板 scene_example.py、协议 python_scene.py，全部数值与运行逻辑使用Python。场景实现 initial_field / refractive_index / 可选target_field，由 build 返回Scene。自定义函数现在完整参与固定收敛验证，参见 docs/agent/python-scenes.md；此前“仅Python API、无法自动verify”的边界已被这一接口替代。
