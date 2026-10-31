# Matplotlib依赖与教程绘图验证

日期：2026-10-31。包版本0.2.0；本次只调整依赖与文档示例，未修改求解器、物理模型或误差判据。全部示例物理参数为 `assumed_not_measured`。

## 变更

- `pyproject.toml` 将 `matplotlib>=3.7` 加入安装依赖，保留 `numpy>=1.24`。项目现有 `.venv` 已重新安装包并补齐依赖。
- 教程第4节整合NPZ保存、主运行与收敛检查、可选数据查询、传播/输出强度绘图。顶部声明列明网格、几何、材料、入射场、输出、采样和显示开关的修改位置。`INSPECT_DATA=False` 默认关闭查询；`SHOW_PLOT=True` 默认显示图窗，PNG先于图窗保存。
- 第9节提供只读取已有二维NPZ的独立示例，在新的子目录保存图片，使用文件坐标恢复积分间距，不重算传播或覆盖数据。
- README、契约、维护入口和能力清单同步更新。求解器和内置CLI不调用Matplotlib，`agentExposed=false`。

## 环境与验证

使用项目 `.venv/Scripts/python.exe`，Python 3.12.10、NumPy 2.5.4、Matplotlib 3.11.2、Tk 8.6。

1. `python -m pip install -e .` 成功；安装元数据包含 `numpy>=1.24`、`matplotlib>=3.7`。`python -m pip check` 显示 `No broken requirements found`。最初受限执行时pip临时目录写入被拒绝，重试获准的项目环境安装成功；失败临时目录保留，未删除历史输出。
2. `simulate-optics.ps1 -Test -Python .\.venv\Scripts\python.exe`：8项测试全部通过，涵盖解析解、四阶收敛、几何、边界失败、稳定性、NPZ读写与拒绝覆盖。
3. 编译教程全部Python代码块；直接提取第4节执行，仅将输出根目录指向本次验证目录，设 `SHOW_PLOT=False`、`INSPECT_DATA=True`。生成 `(201,64,64)` 复场及1600×640 PNG，主运行和收敛检查通过。半步长、半横向间距、扩大窗口的末端相对复场L²差分别为 `2.1499e-12`、`5.8257e-9`、`2.4188e-10`，均小于原门槛0.002。
4. 核对NPZ重读后复场及z坐标完全相同；输出强度与相位正确，最近采样点为 `(0,0,10)` µm；沿y积分后再沿x积分的功率与 `result.power` 一致。两张图的绘图数组与对应转置后的数据完全一致。
5. 在独立变量环境执行第9节，只指定NPZ路径和关闭显示。重读积分结果与第4节一致，PNG正常生成。另以TkAgg执行默认 `SHOW_PLOT=True` 分支，实际进入 `show(block=True)` 图形事件循环，验证图片已经保存，再于600 ms后自动关闭图窗。两条流程均无遗留图窗；原NPZ的SHA256未改变。
6. 人工查看生成的PNG：传播图、末端强度图、坐标、色条与检查状态标题均可读，无文字裁切。`git diff --check` 通过。

验证证据保存在新目录 `artifacts/matplotlib-verification-20261031-144700/`：`verify_tutorial.py`、`verification.json`、各节执行日志及 `my-run-20261031-144450-415635/` 内的NPZ、检查JSON、主图与独立重绘图片。该目录是本次验证记录，不是并行正式源码。

本次仅在上述环境实测；最低依赖版本组合及其他图形后端未单独验证。一维横截面不适用本教程的二维绘图片段。图片可用于检查理论结果，不能替代收敛、材料标定或实验验证。
