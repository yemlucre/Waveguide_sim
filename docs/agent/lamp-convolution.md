# LAMP启发的模态光学卷积特征

检查日期：2026-10-30。独立Python能力 `optics.lamp_modal_correlation`，implemented、agentExposed=false，无MCP/设备调用。用户选择优先查看图像卷积/特征提取输入输出；本轮实现小规模理论演示，非作者实验复现。

## 来源与层次

原论文 [Cao et al., Nature Communications 17,5476](https://www.nature.com/articles/s41467-026-72316-9) 的LAMP为三维耦合＋相位调制的矩阵网络，报告图像分类/图案生成，不是直接给出常规CNN卷积层。实际样品64通道；SI p.5给出理想3×3概念并提示弯曲/损耗困难。本模型不是原64通道实际结构。

SI p.10 Fig.4b/Note3的耦合公式经PDF渲染目视确认：C=6.1688exp(−0.2641d)，C单位mm⁻¹、d单位µm；测量间距10..17µm，信号上下文800nm。`lamp_paper_reference.json`保存DOI、源PDF SHA256和定位；原材料保留Agamemnon WaveguideLibrary，未改写。所有对角/远距离及角度关系都视作外推假设，不能当实测。当前没有色散模型，配置波长仅接受800nm。

空间几何沿用此前concept-9-demo的演示假设：9路行列居中，端面15µm中心距，三次径向双轴展开到700µm，再收拢；90mm、起点5/33/61mm、展开10mm/保持4mm/收拢10mm、五次平滑曲线全部assumed，非作者3×3报告尺寸。x/y是横向µm，z是传播mm，非设备坐标或材料埋深；行优先编号WG01..WG09。

模型求解 i da/dz=H(z)a，H非对角为负实C(d)，对角共同β移去（相位约定）；随z用中点矩阵指数推进。三处理想相位面在17/45/73mm，a→diag(exp(iφ))a。等β、各向同性、单模、无损，忽略弯曲辐射、弧长失谐、偏振、热学与非线性。不是连续横截面上的2+1D/三维BPM。报告绘制通道功率/相位，不伪装成连续空间光强。

## 输入与共用入口

- [lamp.py](../../src/Agamemnon.Optics/lamp.py)：LampParameters.validate、centres、hamiltonian、step_operator、build_network、transfer、row_loss_gradient、train_kernel、patches、evaluate_image、snapshot_transfers。独立于UI、设备、Agent。
- [run_lamp.py](../../src/Agamemnon.Optics/run_lamp.py)：run_study和CLI；[默认配置](../../src/Agamemnon.Optics/lamp_example.json)；根simulate-optics.ps1 -Scenario lamp，中文运行图像特征仿真.cmd转调，成功后打开新报告。
- [lamp_report.py](../../src/Agamemnon.Optics/lamp_report.py)与独立HTML/JS模板：显示层沿用既有CSS设计系统，离线运行，不重新训练/求解。旧coupler场景保持默认，-Test发现所有test_optics*.py。

参数必须有限正值；端面pitch 10..17µm、expanded≥pitch，3段起点有序不重叠且位于总长内；传播步长≤0.25mm，单次≤20000步。训练epochs 1..10000，restarts 1..8，固定随机种子。输入图像finite 2D，每维3..256；模型固定9通道，3×3核finite非零。相位为3×9 finite rad；传输矩阵9×9复数。非法输入ValueError，数值/文件错误向上传播；同步操作无重试/续算/内部超时，中断可能无输出或部分文件。

## 卷积定义与读出假设

像素p直接作为实振幅，不逐窗口归一化；因此强度总量随窗口改变，线性计算不会被隐藏的局部归一化破坏。对K求L²范数s，拟合输出WG05的传输行 U[4,:]≈vec(K)/s。使用解析梯度＋Adam，多起点最小化完整复行误差，不是作者实验的强度SPSA或基于图像标签的CNN训练。

滑窗为valid、stride1、行优先，不翻转核，即深度学习常用互相关。每次重编程一个核，同一设置处理所有窗口/图像；程序组织逐窗口输入，不声称与论文全图原生并行方式相同，也不同时实现四输出滤波组。其他8输出仍承载酉变换余量，没有宣称无损实现任意完整非酉卷积矩阵。

输出复场a5；缩放后场s·a5≈K·p；报告带符号图使用其real部分，完整复误差/虚部另记录。这是假设理想相位参考与相干探测，并非论文CCD直接可读。直接探测I=|a5|²，报告尺度恢复图s²I≈|K·p|²，丢失符号。测试验证p与−p得到相同I、相反复场。没有MNIST数据/分类、池化、非线性或准确率/吞吐宣称。

## 输出、状态和文件

result.json记录参数、paper/assumed来源、相位、复矩阵、4核×3合成图的参考/复实虚/直接强度及零相位基线、每核诊断、传播采样与几何坐标。modal_fields.npz保留原始complex128传输/传播矩阵、相位、z_mm和centres_um；JSON中的传播矩阵仅展示时取9位小数。index.html内嵌数据，支持图像/核/零相位对照、滑窗/像素点击、传播播放及CSV导出；CSV行列为0起点，UI显示1起点。

默认artifacts/optics/新时间戳，显式输出必须为空，历史结果保留。manifest含Python/NumPy/Pillow/平台、所有.py/.html/.js/.json源码/输入哈希和输出SHA256。CLI退出0=verified_modal_demo（4核全过），2=numerical_checks_failed，1=捕获的输入/文件错误；系统中断/启动错误另按进程状态。主程序在计算后才创建目录，文件写入非原子，失败可能部分输出。

每核判据：行L²误差<1e−3、酉性算符2范数误差<1e−9、空间步长减半的传输算符2范数差<0.01、200组独立复输入相对误差<0.002。报告图像误差也记录，不以一张图片的视觉相似度作为验证。没有用实测芯片矩阵或全场BPM做交叉验证。

2026-10-30：21项回归通过（原12＋新9）。新测试覆盖解析双导耦合、三维几何、经验系数单位、解析梯度有限差分、核泛化/酉性、互相关索引/幅度与功率缩放、直接探测丢符号、传播矩阵一致性、无效输入。4核行误差约1e−6、半步算符差约1..2e−6。完整交付与浏览器记录见[验证报告](../reports/lamp-convolution-20261030.md)。实机、作者结构、全场/弯曲/热学/真实读出均未验证。
