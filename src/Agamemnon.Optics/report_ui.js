'use strict';
const report = JSON.parse(document.getElementById('report-data').textContent);
const runs = report.runs, result = report.result, params = result.input.parameters;
const $ = id => document.getElementById(id);
const colors = ['#3268dc', '#db7545', '#238c81', '#9c78b7', '#9b8a44', '#5289a2'];
const statusNames = {verified_theoretical_candidate:'理论候选 · 数值检查通过', numerical_checks_failed:'数值检查未通过', target_not_reached:'范围内未达到目标'};
let selected = result.selected_index ?? 0, sample = 0, playing = false, frame = 0, lastFrame = 0, csvUrl = null;
const pct = (v, n=2) => (v*100).toFixed(n)+'%';
const small = v => Math.abs(v) < .001 && v !== 0 ? v.toExponential(2) : v.toFixed(4);
const extent = r => [r.x_um[0], r.x_um.at(-1)];
$('date').textContent = ' / '+new Date(result.timestamp_utc).toLocaleDateString('zh-CN', {timeZone:'Asia/Shanghai'});
$('footer-meta').textContent = result.model_version+' · 报告 v2 · '+new Date(result.timestamp_utc).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+' CST';
$('hero-target').textContent = '右侧目标 '+pct(result.target,1);
$('status').textContent = statusNames[result.status] || result.status;
if(result.status!=='verified_theoretical_candidate') $('status').classList.add('warn');
const chosen = result.selected_parameters;
const kpis = [
 ['候选中心间距',chosen?chosen.separation_um.toFixed(1):'—','µm','所扫描离散候选中的选择'],
 ['候选平行耦合长度',chosen?(chosen.length_um/1000).toFixed(4):'—','mm','首次向上达到目标的位置'],
 ['候选重算右侧功率',chosen?pct(result.actual_right_power,3):'—','','相对输入功率 · 半空间指标'],
 ['本次目标比例',pct(result.target,1),'','所有物理输入为理论假设']
];
$('kpis').innerHTML=kpis.map(k=>`<div class="kpi"><div class="label">${k[0]}</div><div class="value">${k[1]}<span class="unit">${k[2]}</span></div><div class="note">${k[3]}</div></div>`).join('');
runs.forEach((r,i)=>$('gap').add(new Option(r.separation_um+' µm',i)));
$('vmax').textContent = report.vmax.toFixed(3)+' 1/µm';
const parameterRows = [
 ['真空波长 λ₀',params.wavelength_um*1000+' nm','物理假设'],['背景折射率 n₀',params.background_index,'无量纲 · 物理假设'],['单条峰值增量 Δn',params.delta_index,'无量纲 · 物理假设'],
 ['高斯折射率半宽',params.radius_um+' µm','增量降至峰值 1/e 的半宽'],['传播长度上限',params.length_um/1000+' mm','本次搜索范围'],['扫描中心间距',result.input.separations_um.join(' / ')+' µm','离散候选 · 非边缘间隙'],
 ['计算窗口',params.window_um+' µm','周期横向边界 · 无吸收层'],['横向网格',params.points+' 点','Δx = '+(params.window_um/params.points).toFixed(4)+' µm'],['最大传播步长',params.step_um+' µm','实际步长按总长均分']
];
$('parameters-grid').innerHTML=parameterRows.map(p=>`<div class="param"><label>${p[0]}</label><b>${p[1]}</b><small>${p[2]}</small></div>`).join('');
$('decision').textContent = chosen ? (result.status==='verified_theoretical_candidate'?'理论设计候选：':'尚未验证的候选：')+
 `中心间距 ${chosen.separation_um} µm，平行耦合段长度 ${(chosen.length_um/1000).toFixed(4)} mm。独立重算右侧功率 ${pct(result.actual_right_power,4)}，与目标相差 ${(result.target_error*100).toFixed(4)} 个百分点。该尺寸只描述理想平行耦合区，不包含输入输出分离段，也不是全局最优结果。`:
 '给定范围内未找到首次向上达到目标的候选。可以扩大传播范围、调整候选间距或改变目标后重新计算；此处不将最近结果标为成功。';
const checks = result.verification || {};
const diagnosticRows = [
 ['全扫描功率漂移',Math.max(...result.scan.map(r=>r.max_power_drift)),1e-8,'输入归一化后，全程相对功率偏差；不作逐步归一化。'],
 ['全扫描边缘功率',Math.max(...result.scan.map(r=>r.max_edge_power)),1e-4,'边缘区域 |x| ≥ 0.4 × 窗口，监测周期边界风险。'],
 ['候选及复算边缘功率',checks.max_edge_power,1e-4,'候选及精细复算中的最大边缘功率。'],
 ['传播步长减半',checks.half_step_right_power_difference,.002,'右侧功率绝对差，检查传播离散误差。'],
 ['横向网格加密',checks.half_grid_right_power_difference,.002,'网格间距减半后，右侧功率的绝对差。'],
 ['扩大计算窗口',checks.enlarged_window_right_power_difference,.002,'保持 Δx，窗口扩大 1.5 倍后的右侧功率差。'],
 ['独立本征演化对照',checks.spectral_reference_field_l2_error,.01,'同一离散哈密顿量，直接本征演化与分步传播的场 L² 差。'],
 ['候选目标误差',result.target_error,.002,'候选独立重算后的右侧功率与目标的绝对差。']
];
$('checks').innerHTML = diagnosticRows.map(([name,value,threshold,why])=>{
 const exists=Number.isFinite(value), passed=exists&&value<threshold;
 return `<div class="check"><div class="check-head"><span>${name}</span><b class="${passed?'':'bad'}">${!exists?'未执行':passed?'通过':'未通过'}</b></div><div class="check-values"><span>实际 ${exists?value.toExponential(2):'—'}</span><span>阈值 &lt; ${threshold.toExponential(0)}</span></div><div class="meter"><span style="width:${exists?Math.min(100,Math.max(.5,value/threshold*100)):0}%;background:${passed?'#5b9b94':'#c97f5a'}"></span></div><p>${why}</p></div>`;
}).join('');
$('raw').textContent=JSON.stringify({status:result.status,model_version:result.model_version,timestamp_utc:result.timestamp_utc,parameter_origin:result.parameter_origin,verification:result.verification??null,scan_numerics_passed:result.scan_numerics_passed},null,2);
function surface(id){
 const c=$(id), w=c.clientWidth,h=c.clientHeight,dpr=Math.min(devicePixelRatio||1,2);
 c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);
 const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
 ctx.font='11px Segoe UI, Microsoft YaHei, sans-serif';ctx.lineJoin='round';
 return {ctx,w,h,l:54,t:27,r:w-20,b:h-39};
}
function axes(s,xmin,xmax,ymin,ymax,xlabel,ylabel,yformat=v=>v.toFixed(1),grid=true){
 const {ctx,l,r,t,b}=s;
 const X=x=>l+(x-xmin)/(xmax-xmin)*(r-l), Y=y=>b-(y-ymin)/(ymax-ymin)*(b-t);
 ctx.lineWidth=1;ctx.textAlign='right';ctx.fillStyle='#8090a3';
 for(let j=0;j<=4;j++){
  const y=ymin+(ymax-ymin)*j/4;
  if(grid){ctx.strokeStyle='#e9edf3';ctx.beginPath();ctx.moveTo(l,Y(y));ctx.lineTo(r,Y(y));ctx.stroke();}
  ctx.fillStyle='#7e8ba0';ctx.fillText(yformat(y),l-9,Y(y)+4);
 }
 ctx.textAlign='center';
 for(let j=0;j<=4;j++){let x=xmin+(xmax-xmin)*j/4;ctx.fillText(x.toFixed(xmax-xmin>10?0:1),X(x),b+19);}
 ctx.fillStyle='#607087';ctx.fillText(xlabel,(l+r)/2,s.h-6);ctx.textAlign='left';ctx.fillText(ylabel,l,t-12);
 return {X,Y};
}
function line(s,m,xs,ys,color,dash=[],width=2){
 const {ctx,l,r,t,b}=s;ctx.save();ctx.beginPath();ctx.rect(l,t,r-l,b-t);ctx.clip();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();
 xs.forEach((x,i)=>i?ctx.lineTo(m.X(x),m.Y(ys[i])):ctx.moveTo(m.X(x),m.Y(ys[i])));ctx.stroke();ctx.restore();
}
function vertical(s,X,x,color='#dd8164'){
 s.ctx.save();s.ctx.strokeStyle=color;s.ctx.setLineDash([4,4]);s.ctx.beginPath();s.ctx.moveTo(X(x),s.t);s.ctx.lineTo(X(x),s.b);s.ctx.stroke();s.ctx.restore();
}
const palette = [[8,14,37],[41,48,111],[20,142,172],[100,215,166],[255,233,124]];
const heatCache=new Map();
function heatImage(i){
 if(heatCache.has(i))return heatCache.get(i);
 const d=runs[i],canvas=document.createElement('canvas');canvas.width=d.z_mm.length;canvas.height=d.x_um.length;
 const ctx=canvas.getContext('2d'),pixels=ctx.createImageData(canvas.width,canvas.height);
 for(let z=0;z<canvas.width;z++)for(let x=0;x<canvas.height;x++){
  let t=Math.min(1,Math.max(0,d.intensity[z][x]/report.vmax))*4,k=Math.min(3,Math.floor(t)),f=t-k,idx=((canvas.height-1-x)*canvas.width+z)*4;
  for(let c=0;c<3;c++)pixels.data[idx+c]=palette[k][c]*(1-f)+palette[k+1][c]*f;
  pixels.data[idx+3]=255;
 }
 ctx.putImageData(pixels,0,0);heatCache.set(i,canvas);return canvas;
}
function drawHeat(){
 const d=runs[selected],s=surface('heat'),[xmin,xmax]=extent(d);
 const m=axes(s,0,d.z_mm.at(-1),xmin,xmax,'传播 z / mm','横向 x / µm',v=>v.toFixed(0),false);
 s.ctx.drawImage(heatImage(selected),s.l,s.t,s.r-s.l,s.b-s.t);
 vertical(s,m.X,d.z_mm[sample],'#ffffff');
}
function drawPower(){
 const d=runs[selected],s=surface('power'),m=axes(s,0,d.z_mm.at(-1),0,1,'传播 z / mm','相对输入功率',v=>(v*100).toFixed(0)+'%');
 line(s,m,[0,d.z_mm.at(-1)],[result.target,result.target],'#a1aab9',[4,5],1);
 line(s,m,d.z_mm,d.left,colors[0]);line(s,m,d.z_mm,d.right,colors[1]);vertical(s,m.X,d.z_mm[sample]);
 [d.left[sample],d.right[sample]].forEach((v,i)=>{s.ctx.fillStyle=colors[i];s.ctx.beginPath();s.ctx.arc(m.X(d.z_mm[sample]),m.Y(v),3.5,0,Math.PI*2);s.ctx.fill();});
}
function drawProfile(){
 const d=runs[selected],[xmin,xmax]=extent(d),s=surface('profile'),m=axes(s,xmin,xmax,0,report.vmax*1.08,'横向 x / µm','光场强度 / 1/µm',v=>v.toFixed(2));
 s.ctx.fillStyle='#3268dc0b';
 [-1,1].forEach(sign=>{let a=m.X(sign*d.separation_um/2-params.radius_um),b=m.X(sign*d.separation_um/2+params.radius_um);s.ctx.fillRect(a,s.t,b-a,s.b-s.t);});
 line(s,m,d.x_um,d.intensity[0],'#a7b2c4',[4,4],1.5);line(s,m,d.x_um,d.intensity[sample],colors[0]);
}
function drawIndex(){
 const d=runs[selected],[xmin,xmax]=extent(d),s=surface('index-profile'),m=axes(s,xmin,xmax,0,Math.max(...d.delta_n)*1.15,'横向 x / µm','折射率增量 Δn',v=>v.toFixed(3));
 line(s,m,d.x_um,d.delta_n,colors[2]);
 $('index-note').textContent='当前中心位于 x = ±'+(d.separation_um/2).toFixed(1)+' µm；增量为两个高斯分布相加。';
}
function drawComparison(){
 const s=surface('comparison'),m=axes(s,0,runs[0].z_mm.at(-1),0,1,'传播 z / mm','右侧功率',v=>(v*100).toFixed(0)+'%');
 line(s,m,[0,runs[0].z_mm.at(-1)],[result.target,result.target],'#a1aab9',[4,4],1);
 runs.forEach((d,i)=>line(s,m,d.z_mm,d.right,colors[i%colors.length],[],i===selected?2.8:1.4));
 $('comparison-legend').innerHTML=runs.map((d,i)=>`<span style="display:inline-block;margin:0 12px 4px 0;color:${colors[i%colors.length]}">━ ${d.separation_um} µm</span>`).join('');
}
function update(){
 const d=runs[selected];sample=+$('position').value;
 $('z-value').textContent=d.z_mm[sample].toFixed(3)+' mm';
 $('left-value').textContent=pct(d.left[sample]);$('right-value').textContent=pct(d.right[sample]);
 drawHeat();drawPower();drawProfile();
}
function stop(){playing=false;cancelAnimationFrame(frame);$('play').textContent='▶ 播放传播';$('play').setAttribute('aria-pressed','false');}
function choose(index){
 stop();selected=+index;$('gap').value=selected;
 const d=runs[selected];$('position').max=d.z_mm.length-1;$('position').value=0;
 $('jump').disabled=d.first_target_length_um===null;
 $('scan-table').innerHTML=runs.map((r,i)=>`<tr class="${i===selected?'selected':''}"><td>${r.separation_um} µm${i===result.selected_index?'<span class="pill">候选</span>':''}</td><td>${r.first_target_length_um===null?'未达到':(r.first_target_length_um/1000).toFixed(4)+' mm'}</td><td>${pct(r.max_right_power)}</td><td><button data-run="${i}" aria-label="查看 ${r.separation_um} 微米间距">查看</button></td></tr>`).join('');
 $('download-figure').href=d.figure;
 if(csvUrl)URL.revokeObjectURL(csvUrl);
 const csv='z_mm,left_power_over_input,right_power_over_input\n'+d.z_mm.map((z,i)=>[z,d.left[i],d.right[i]].join(',')).join('\n');
 csvUrl=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));$('download-csv').href=csvUrl;
 drawIndex();drawComparison();update();
}
$('gap').onchange=()=>choose(+$('gap').value);
$('position').oninput=()=>{stop();update();};
$('scan-table').onclick=e=>{const b=e.target.closest('button[data-run]');if(b){choose(+b.dataset.run);$('explore').scrollIntoView({behavior:'smooth'});}};
$('jump').onclick=()=>{stop();const d=runs[selected],z=d.first_target_length_um/1000;let i=0;d.z_mm.forEach((v,j)=>{if(Math.abs(v-z)<Math.abs(d.z_mm[i]-z))i=j;});$('position').value=i;update();};
$('play').onclick=()=>{
 if(playing){stop();return;}playing=true;lastFrame=0;
 if(+$('position').value>=+$('position').max)$('position').value=0;
 $('play').textContent='Ⅱ 暂停播放';$('play').setAttribute('aria-pressed','true');
 function tick(time){if(!playing)return;if(time-lastFrame>40){lastFrame=time;$('position').value=Math.min(+$('position').max,+$('position').value+1);update();if(+$('position').value>=+$('position').max){stop();return;}}frame=requestAnimationFrame(tick);}frame=requestAnimationFrame(tick);
};
$('print').onclick=()=>{stop();window.print();};
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{drawIndex();drawComparison();update();},100);});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){document.querySelectorAll('.nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}});},{rootMargin:'-10% 0px -65% 0px'});
document.querySelectorAll('section[id]').forEach(s=>observer.observe(s));
choose(selected);
