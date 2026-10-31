"""Offline report only: modal powers are never labelled continuous spatial fields."""
import json
from html import escape
from PIL import Image,ImageDraw,ImageFont
import numpy as np


def summary_png(output,rows,runs):
    image=Image.new('RGB',(1400,740),'#f5f4ef'); draw=ImageDraw.Draw(image)
    font_path='C:/Windows/Fonts/msyh.ttc'
    try: title=ImageFont.truetype(font_path,28); font=ImageFont.truetype(font_path,19); small=ImageFont.truetype(font_path,16)
    except OSError: title=font=small=ImageFont.load_default()
    draw.text((32,20),'无源交错扇出波导｜间距与光学参数比较',font=title,fill='#142d39')
    draw.text((32,65),'8×8 / 100 mm / 主动调相为零 / 光学参数 assumed / 离散模态功率，非整片连续BPM',font=font,fill='#52616b')
    for j,pitch in enumerate((12.,15.,18.)):
        ix=next(i for i,r in enumerate(rows) if r['material_name']=='基准' and r['geometry']['pitch_um']==pitch)
        r=rows[ix]; run=runs[ix]; x0=40+j*450; y0=155; size=38
        draw.text((x0,110),f'中心距 {pitch:g} µm',font=title,fill='#142d39')
        p=run['power'][-1].reshape(8,8); maximum=max(float(p.max()),1e-30)
        for row in range(8):
            for col in range(8):
                t=float(p[row,col]/maximum); color=(int(25+225*t),int(37+150*t),int(65+70*t))
                x=x0+col*size; y=y0+row*size
                draw.rectangle((x,y,x+size-2,y+size-2),fill=color)
        draw.text((x0,y0+325),f"末端有效通道数 {r['metrics']['effective_channels']:.2f} / 64",font=font,fill='#142d39')
        draw.text((x0,y0+358),f"输入通道留存 {100*r['metrics']['input_retention']:.2f}%",font=font,fill='#142d39')
        draw.text((x0,y0+391),f"两导耦合 C = {r['coupling_per_mm']:.4f} mm⁻¹",font=font,fill='#142d39')
        draw.text((x0,y0+424),f"两导首次50%长度 {r['half_transfer_length_mm']:.2f} mm",font=font,fill='#142d39')
    draw.text((32,640),'颜色各面板按自身峰值显示，数值比较请看报告；有效通道数 = exp(功率分布熵)。',font=small,fill='#52616b')
    draw.text((32,675),'这是选参探索：更均匀不一定更适合目标任务；弯曲辐射、加工误差和实测折射率尚未包含。',font=small,fill='#52616b')
    image.save(output/'spacing-comparison.png')


def write_report(output,result,runs,local):
    rows=result['cases']; summary_png(output,rows,runs)
    cases=[]; geometry={}
    for row,r in zip(rows,runs):
        ix=np.unique(np.r_[np.arange(0,len(r['z_mm']),2),len(r['z_mm'])-1]).astype(int)
        key=str(row['geometry']['pitch_um'])
        geometry[key]=np.round(r['positions_um'][ix],5).tolist()
        cases.append(dict(name=row['name'],geometry_key=key,z=np.round(r['z_mm'][ix],7).tolist(),
                          powers=np.round(r['power'][ix],10).tolist(),metrics=row['metrics'],checks=row['verification']))
    data=json.dumps(dict(cases=cases,geometry=geometry,input_channel=result['input_channel']),ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    options=''.join(f'<option value="{i}">{escape(r["name"])}</option>' for i,r in enumerate(rows))
    table=''.join(f'<tr><td>{escape(r["material_name"])}</td><td>{r["material"]["radius_um"]:g}</td><td>{r["material"]["delta_index"]:g}</td><td>{r["geometry"]["pitch_um"]:g}</td><td>{r["coupling_per_mm"]:.5f}</td><td>{r["half_transfer_length_mm"]:.2f}</td><td>{r["metrics"]["effective_channels"]:.2f}</td><td>{100*r["metrics"]["input_retention"]:.2f}%</td><td>{"通过" if r["verification"]["passed"] else "未通过"}</td></tr>' for r in rows)
    local_text=json.dumps(local,ensure_ascii=False,indent=2)
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>无源交错扇出波导选参</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f2ed;color:#18323f;font:16px system-ui}main{max-width:1180px;margin:auto;padding:28px}section{background:white;border-radius:18px;padding:24px;margin:22px 0}h1{font-size:34px}h2{font-size:23px}p{line-height:1.7}.muted{color:#536570}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}canvas{width:100%;display:block;border:1px solid #dce2e4;border-radius:10px}select,button{padding:10px;font:inherit}input{width:70%}pre{white-space:pre-wrap;overflow-wrap:anywhere}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}img{max-width:100%}a{color:#145e93}@media(max-width:700px){main{padding:14px}section{padding:16px}.grid{grid-template-columns:1fr}h1{font-size:27px}select{max-width:100%}}</style>
<main><h1>无源交错扇出波导 · 参数探索</h1><p>按图二重建：8×8通道、100 mm传播；每层9 mm展开＋0.5 mm保持＋9 mm收回，层间错开9.5 mm，最大扇出间距700 µm。主动调相为零。</p>
<p class="muted">整片采用耦合模近似，显示离散通道功率；局部用连续2+1D傍轴BPM核对。所有材料参数与圆形高斯折射率截面均为 assumed，不是实测器件。保留自然路径长度相位，忽略弯曲辐射损耗、偏振与加工无序。</p>
<p><a href="result.json">完整结果</a> · <a href="modal_fields.npz">模振幅/几何/孤立模式</a> · <a href="local_pair_fields.npz">局部连续复光场</a> · <a href="manifest.json">来源与哈希</a></p>
<section><h2>先比较波导间距</h2><img src="spacing-comparison.png" alt="12、15、18微米间距比较"><p>有效通道数越大，末端功率越分散；它不是准确率、传输效率或统一的最佳设计目标。两导50%长度只适用于等传播常数的直线双波导，不能替代整片的多通道演化。</p></section>
<section><h2>沿结构观察光的转移</h2><label>参数组合 <select id="case">'''+options+'''</select></label><p id="status"></p><canvas id="paths" width="1080" height="340" aria-label="各层扇出路径与传播位置"></canvas><p class="muted">上图为x-z投影：横轴z 0..100 mm，纵轴x −2.45..2.45 mm；颜色区分深度层，深度层在投影中可能重合。</p><p><input id="z" type="range" min="0" max="250" value="0" aria-label="传播位置"><button id="play">播放 / 暂停</button></p><div class="grid"><div><h3>当前通道功率</h3><canvas id="power" width="480" height="430" aria-label="8乘8通道功率"></canvas><p class="muted">按通道编号排成8×8；颜色为log显示，百分数为真实功率。此布局不是扇出段的物理横截面。</p></div><div><h3>功率沿z的变化</h3><canvas id="curve" width="480" height="430" aria-label="输入通道与参与度曲线"></canvas><p>蓝线：输入通道功率（0..1）；橙线：有效通道数/64（0..1）。</p><pre id="readout"></pre></div></div><details><summary>本候选验证与指标</summary><pre id="checks"></pre></details></section>
<section><h2>间距 × 波导尺寸 × 折射率增量</h2><p>radius为折射率增量1/e半宽，µm；Δn为无量纲增量。C由对应假设孤立二维导模的双导投影计算，非直接套用固定经验曲线。</p><div class="scroll"><table><thead><tr><th>组合</th><th>radius µm</th><th>Δn</th><th>间距 µm</th><th>C mm⁻¹</th><th>50%长度 mm</th><th>末端有效通道</th><th>留存</th><th>数值检查</th></tr></thead><tbody>'''+table+'''</tbody></table></div></section>
<section><h2>局部连续光场交叉检查</h2><p>只针对基准材料、15 µm间距的直线双波导单元；不能据此宣称整个扇出结构的连续场或弯曲损耗已验证。</p><pre>'''+escape(local_text)+'''</pre></section>
<section><h2>如何用它选择参数</h2><p>先根据希望的耦合长度和功率扩散范围缩小间距、半宽、Δn候选，再对目标结构做局部连续场与弯曲损耗验证。没有指定目标输出时，本报告不自动宣布某组参数“最好”。</p><p>几何尺寸来源：Cao等论文补充Fig.3/Table 1。首起点5 mm、逐行顺序、半余弦插值、等横截面、各向同性两体耦合与恒定有效折射率均属于重建/建模假设。</p><a href="https://www.nature.com/articles/s41467-026-72316-9">论文与补充材料</a></section></main><script>const DATA='''+data+''';
const colors=['#4778ae','#c57435','#438c76','#965e9d','#8e9347','#4598a6','#ba6170','#7a77bb'];let timer=null;
function line(ctx,points,color,width=2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke()}
function entropy(p){return Math.exp(-p.reduce((s,v)=>s+(v>0?v*Math.log(v):0),0))}
function show(){let c=DATA.cases[+document.getElementById('case').value],slider=document.getElementById('z');slider.max=c.z.length-1;let j=Math.min(+slider.value,c.z.length-1),p=c.powers[j],geom=DATA.geometry[c.geometry_key],zz=c.z[j];
document.getElementById('status').textContent=c.name+'；z = '+zz.toFixed(2)+' mm';document.getElementById('readout').textContent='总功率 '+p.reduce((a,b)=>a+b,0).toFixed(8)+'\n输入通道留存 '+(100*p[DATA.input_channel]).toFixed(3)+'%\n有效通道数 '+entropy(p).toFixed(2)+' / 64';document.getElementById('checks').textContent=JSON.stringify({metrics:c.metrics,verification:c.checks},null,2);
let cv=document.getElementById('paths'),ctx=cv.getContext('2d');ctx.clearRect(0,0,cv.width,cv.height);ctx.font='14px system-ui';ctx.fillStyle='#36515e';ctx.fillText('z (mm) →',16,22);ctx.fillText('x (mm)',16,46);for(let ch=0;ch<64;ch++){line(ctx,c.z.map((z,i)=>[45+z*9.9,170-geom[i][ch][0]/2450*125]),colors[Math.floor(ch/8)],1)}line(ctx,[[45+zz*9.9,30],[45+zz*9.9,310]],'#111',2);ctx.fillText('0',40,330);ctx.fillText('100',1010,330);
cv=document.getElementById('power');ctx=cv.getContext('2d');ctx.clearRect(0,0,480,430);ctx.font='13px system-ui';for(let r=0;r<8;r++){for(let col=0;col<8;col++){let q=p[r*8+col],v=Math.max(0,(Math.log10(Math.max(q,1e-6))+6)/6);ctx.fillStyle=`rgb(${20+220*v},${35+140*v},${60+35*v})`;ctx.fillRect(55+col*49,20+r*49,47,47);ctx.fillStyle='white';ctx.fillText((q*100).toFixed(1),58+col*49,49+r*49)}ctx.fillStyle='#18323f';ctx.fillText('r'+(r+1),16,49+r*49)}
cv=document.getElementById('curve');ctx=cv.getContext('2d');ctx.clearRect(0,0,480,430);line(ctx,[[40,20],[40,380],[460,380]],'#8e9da4',1);line(ctx,c.z.map((z,i)=>[40+4.2*z,380-350*c.powers[i][DATA.input_channel]]),'#337bae');line(ctx,c.z.map((z,i)=>[40+4.2*z,380-350*entropy(c.powers[i])/64]),'#d18b39');line(ctx,[[40+4.2*zz,20],[40+4.2*zz,380]],'#222',1);ctx.fillStyle='#36515e';ctx.font='14px system-ui';ctx.fillText('0',30,405);ctx.fillText('100 mm',400,405);ctx.fillText('1',16,25)}
document.getElementById('case').onchange=show;document.getElementById('z').oninput=show;document.getElementById('play').onclick=()=>{if(timer){clearInterval(timer);timer=null}else timer=setInterval(()=>{let s=document.getElementById('z');s.value=(+s.value+1)%(+s.max+1);show()},100)};show();</script></html>'''
    (output/'index.html').write_text(html,encoding='utf-8')
