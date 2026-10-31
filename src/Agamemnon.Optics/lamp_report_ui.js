'use strict';
const study=JSON.parse(document.getElementById('lamp-data').textContent);
const $=id=>document.getElementById(id);
const kernelKeys=Object.keys(study.kernels),imageKeys=Object.keys(study.images);
let kernelKey=kernelKeys[0],imageKey=imageKeys[0],patchIndex=157,zIndex=0,mode='programmed',playing=false,raf=0,last=0,csvUrl=null;
const kernel=()=>study.kernels[kernelKey],image=()=>study.images[imageKey].pixels;
const data=()=>kernel().images[imageKey];
const fmt=x=>Math.abs(x)<.0005?'0.000':x.toFixed(3);
const exp=x=>x.toExponential(2);
$('paper-link').href=study.paper_url;$('si-link').href=study.supplementary_url;
$('footer').textContent=study.model_version+' · '+new Date(study.timestamp_utc).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+' CST';
$('status').textContent=study.status==='verified_modal_demo'?'理论模态演示 · 数值验证通过':'模型数值检查未通过';
if(study.status!=='verified_modal_demo')$('status').classList.add('warn');
kernelKeys.forEach(key=>$('kernel').add(new Option(study.kernels[key].name,key)));
imageKeys.forEach(key=>$('image').add(new Option(study.images[key].name,key)));
const descriptions={sobel_x:'检测左右方向的亮度变化，突出竖直边缘。',sobel_y:'检测上下方向的亮度变化，突出水平边缘。',blur:'对3×3像素取平均，平滑局部变化。',laplacian:'比较中心与邻域，突出局部边界变化。'};
function surface(id){
 const c=$(id),w=c.clientWidth,h=c.clientHeight,dpr=Math.min(devicePixelRatio||1,2);c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);
 const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);ctx.font='11px Segoe UI, Microsoft YaHei, sans-serif';return {c,ctx,w,h};
}
function signedColor(value,limit){
 let a=Math.min(1,Math.abs(value)/Math.max(limit,1e-12)),end=value>=0?[199,69,61]:[46,101,185];
 return `rgb(${end.map(v=>Math.round(249+(v-249)*a)).join(',')})`;
}
function warmColor(value,limit=1){let a=Math.min(1,Math.max(0,value/Math.max(limit,1e-12)));return `rgb(${Math.round(250-32*a)},${Math.round(248-153*a)},${Math.round(244-187*a)})`;}
function map(id,values,type,limit,highlight){
 const s=surface(id),n=values.length,m=values[0].length,side=Math.min(s.w-26,s.h-31),left=(s.w-side)/2,top=7,cell=side/m;
 s.c.mapBox={left,top,side,m,n};
 values.forEach((row,r)=>row.forEach((v,c)=>{s.ctx.fillStyle=type==='signed'?signedColor(v,limit):type==='gray'?`rgb(${[0,0,0].map(()=>Math.round(v*255)).join(',')})`:warmColor(v,limit);s.ctx.fillRect(left+c*cell,top+r*side/n,cell+.3,side/n+.3);}));
 if(highlight){const [r,c,size]=highlight;s.ctx.strokeStyle='#de684c';s.ctx.lineWidth=2;s.ctx.strokeRect(left+c*cell+1,top+r*side/n+1,size*cell-2,size*side/n-2);}
 s.ctx.fillStyle='#748399';s.ctx.textAlign='center';s.ctx.fillText(type==='signed'?'蓝 −'+limit.toFixed(2)+'   /   红 +'+limit.toFixed(2):type==='gray'?'0 黑   →   1 白':'0   →   '+limit.toFixed(3),s.w/2,top+side+17);
}
function currentPatch(){const r=Math.floor(patchIndex/22),c=patchIndex%22;return Array.from({length:9},(_,i)=>image()[r+Math.floor(i/3)][c+i%3]);}
function multiply(real,imag,input){return real.map((row,i)=>[row.reduce((v,x,j)=>v+x*input[j],0),imag[i].reduce((v,x,j)=>v+x*input[j],0)]);}
let trajectory=[];
function computeTrajectory(){
 const k=kernel(),input=currentPatch(),real=mode==='programmed'?k.snapshot_real:study.unprogrammed_snapshot_real,imag=mode==='programmed'?k.snapshot_imag:study.unprogrammed_snapshot_imag;
 trajectory=real.map((r,i)=>multiply(r,imag[i],input));
}
function updateMaps(){
 const k=kernel(),d=data(),r=Math.floor(patchIndex/22),c=patchIndex%22;
 const field=mode==='programmed'?d.coherent_real:d.unprogrammed_real;
 const intensity=mode==='programmed'?d.intensity_rescaled:d.unprogrammed_intensity_rescaled;
 const signedLimit=Math.max(1e-9,...d.reference.flat().map(Math.abs),...field.flat().map(Math.abs));
 const intensityLimit=Math.max(1e-9,...d.reference.flat().map(v=>v*v),...intensity.flat());
 map('input-map',image(),'gray',1,[r,c,3]);map('reference-map',d.reference,'signed',signedLimit,[r,c,1]);
 map('field-map',field,'signed',signedLimit,[r,c,1]);map('intensity-map',intensity,'warm',intensityLimit,[r,c,1]);
 $('field-state').textContent=mode==='programmed'?'已编程 · 假设理想相干读出':'零相位基线 · 假设理想相干读出';
 $('prop-state').textContent=mode==='programmed'?'当前：已编程相位':'当前：全部相位为零';
 $('patch-location').textContent=`行 ${r+1} / 列 ${c+1}`;
 $('reference-value').textContent=fmt(d.reference[r][c]);$('field-value').textContent=fmt(field[r][c]);
 $('patch-values').innerHTML=currentPatch().map(v=>`<span>${v.toFixed(3)}</span>`).join('');
 let errorSq=0,referenceSq=0;
 field.forEach((row,i)=>row.forEach((v,j)=>{errorSq+=(v-d.reference[i][j])**2;referenceSq+=d.reference[i][j]**2;}));
 const metrics=[['当前图像实部相对误差',exp(Math.sqrt(errorSq/Math.max(referenceSq,1e-24))),'对照同一参考核'],['已编程核行L²误差',exp(k.row_l2_error),'与演示图像无关'],['已编程随机复输入误差',exp(k.random_complex_probe_relative_error),'200组独立输入探针'],['当前窗口缩放后强度',fmt(intensity[r][c]),'不保留卷积正负号']];
 $('metrics').innerHTML=metrics.map(m=>`<div class="kpi"><div class="label">${m[0]}</div><div class="value">${m[1]}</div><div class="note">${m[2]}</div></div>`).join('');
 if(csvUrl)URL.revokeObjectURL(csvUrl);
 const csv=['row,column,reference,signed_field_real,rescaled_intensity'];
 field.forEach((row,i)=>row.forEach((v,j)=>csv.push([i,j,d.reference[i][j],v,intensity[i][j]].join(','))));
 csvUrl=URL.createObjectURL(new Blob([csv.join('\n')],{type:'text/csv;charset=utf-8'}));$('csv').href=csvUrl;
}
function updateKernel(){
 const k=kernel(),matrix=(id,values)=>{$(id).innerHTML=values.flat().map(v=>`<span style="color:${v<-.0005?'#3268dc':v>.0005?'#bc6042':'#77879b'}">${fmt(v)}</span>`).join('');};
 const norm=k.kernel_norm,zeroReal=study.unprogrammed_snapshot_real.at(-1)[4].map(v=>v*norm),zeroImag=study.unprogrammed_snapshot_imag.at(-1)[4].map(v=>v*norm);
 matrix('target-kernel',k.kernel);matrix('learned-real',mode==='programmed'?k.learned_real:Array.from({length:3},(_,r)=>zeroReal.slice(r*3,r*3+3)));matrix('learned-imag',mode==='programmed'?k.learned_imag:Array.from({length:3},(_,r)=>zeroImag.slice(r*3,r*3+3)));
 $('kernel-description').textContent=descriptions[kernelKey];
 $('phase-maps').innerHTML=k.phases_rad.map((p,i)=>`<div><h4>平面 ${i+1} · z=${study.phase_z_mm[i]} mm</h4><canvas id="phase-${i}" role="img" aria-label="第${i+1}相位平面的设置"></canvas></div>`).join('');
 k.phases_rad.forEach((programmedValues,i)=>{const values=mode==='programmed'?programmedValues:programmedValues.map(()=>0);
  const s=surface('phase-'+i),side=Math.min(s.w,s.h-6),cell=side/3,left=(s.w-side)/2;
  values.forEach((v,j)=>{const phase=((v%(2*Math.PI))+2*Math.PI)%(2*Math.PI),r=Math.floor(j/3),c=j%3;
   s.ctx.fillStyle=`hsl(${phase/(2*Math.PI)*300+20} 35% 86%)`;s.ctx.fillRect(left+c*cell+2,r*cell+2,cell-4,cell-4);
   s.ctx.fillStyle='#23344c';s.ctx.textAlign='center';s.ctx.fillText(phase.toFixed(2),left+(c+.5)*cell,(r+.5)*cell+4);
  });
 });
 const checks=[['目标核行拟合',k.row_l2_error,study.thresholds.row_l2,'拟合完整复权重，不仅比较一幅图的外观。'],['无损传输酉性',k.unitarity_error,study.thresholds.unitarity,'理想模型中功率守恒；不表示真实芯片无损。'],['传播步长减半',k.half_step_operator_difference,study.thresholds.half_step_operator_difference,'相位不变，重新积分空间路径，比较传输算符。'],['独立随机复输入',k.random_complex_probe_relative_error,study.thresholds.random_probe_relative_error,'用未参与训练的200组复向量验证同一核的响应。']];
 $('checks').innerHTML=checks.map(([name,v,t,why])=>`<div class="check"><div class="check-head"><span>${name}</span><b class="${v<t?'':'bad'}">${v<t?'通过':'未通过'}</b></div><div class="check-values"><span>实际 ${exp(v)}</span><span>阈值 &lt; ${exp(t)}</span></div><div class="meter"><span style="width:${Math.max(.5,Math.min(100,v/t*100))}%"></span></div><p>${why}</p></div>`).join('');
 $('diagnostics').textContent=JSON.stringify({kernel:kernelKey,best_epoch:k.best_epoch,best_restart:k.best_restart,row_l2_error:k.row_l2_error,unitarity_error:k.unitarity_error,half_step_operator_difference:k.half_step_operator_difference,random_complex_probe_relative_error:k.random_complex_probe_relative_error,images:Object.fromEntries(Object.entries(k.images).map(([key,v])=>[key,{complex_relative_error:v.relative_error,imaginary_rms:v.imaginary_rms}]))},null,2);
}
function heat(){
 const s=surface('modal-heat'),k=kernel(),l=48,t=20,r=s.w-18,b=s.h-37,cell=(b-t)/9,inputPower=currentPatch().reduce((sum,v)=>sum+v*v,0);
 const X=z=>l+z/study.parameters.length_mm*(r-l);
 trajectory.forEach((field,j)=>field.forEach(([re,im],channel)=>{
  const power=(re*re+im*im)/Math.max(inputPower,1e-20),v=Math.min(1,power*3);
  s.ctx.fillStyle=`rgb(${Math.round(9+90*v)},${Math.round(21+182*v)},${Math.round(43+134*v)})`;
  s.ctx.fillRect(X(k.z_mm[j]),t+channel*cell,Math.max(1,X(k.z_mm[Math.min(j+1,k.z_mm.length-1)])-X(k.z_mm[j])),cell+.2);
 }));
 s.ctx.fillStyle='#748399';s.ctx.textAlign='right';for(let i=0;i<9;i++)s.ctx.fillText('WG'+String(i+1).padStart(2,'0'),l-6,t+(i+.5)*cell+4);
 s.ctx.textAlign='center';for(let i=0;i<=3;i++)s.ctx.fillText(String(study.parameters.length_mm*i/3),X(study.parameters.length_mm*i/3),b+19);
 s.ctx.fillText('传播距离 z / mm',(l+r)/2,s.h-3);
 s.ctx.strokeStyle='white';s.ctx.setLineDash([4,4]);s.ctx.beginPath();s.ctx.moveTo(X(k.z_mm[zIndex]),t);s.ctx.lineTo(X(k.z_mm[zIndex]),b);s.ctx.stroke();
 s.ctx.setLineDash([]);s.ctx.textAlign='left';s.ctx.fillText('色标：暗 0 → 亮 ≥ 33%（仅显示饱和）',l,12);
}
function modal(){
 const s=surface('modal-grid'),field=trajectory[zIndex],inputPower=currentPatch().reduce((sum,v)=>sum+v*v,0),side=Math.min(s.w-40,s.h-40),cell=side/3,left=(s.w-side)/2;
 let total=0;
 field.forEach(([re,im],j)=>{
  const power=re*re+im*im;total+=power;const fraction=power/Math.max(inputPower,1e-20),a=Math.min(1,fraction*3),r=Math.floor(j/3),c=j%3,cx=left+(c+.5)*cell,cy=17+(r+.5)*cell,phase=Math.atan2(im,re);
  s.ctx.fillStyle=`rgb(${Math.round(242-199*a)},${Math.round(246-100*a)},${Math.round(251-87*a)})`;s.ctx.beginPath();s.ctx.arc(cx,cy,cell*.35,0,Math.PI*2);s.ctx.fill();
  s.ctx.strokeStyle='#30558b';s.ctx.beginPath();s.ctx.moveTo(cx,cy);s.ctx.lineTo(cx+Math.cos(phase)*cell*.24,cy-Math.sin(phase)*cell*.24);s.ctx.stroke();
  s.ctx.fillStyle='#253a55';s.ctx.textAlign='center';s.ctx.fillText('WG'+String(j+1).padStart(2,'0'),cx,cy-cell*.37);s.ctx.fillText((fraction*100).toFixed(1)+'%',cx,cy+cell*.47);
 });
 $('power-value').textContent=inputPower>0?(total/inputPower*100).toFixed(5)+'%':'无输入光';
}
function geometry(){
 const s=surface('geometry'),k=kernel(),project=(z,xy)=>[z+.45*xy[0]/1000*40,-.45*xy[0]/1000*40+.75*xy[1]/1000*40];
 const paths=Array.from({length:9},(_,j)=>k.centres_um.map((xy,i)=>project(k.z_mm[i],xy[j])));
 const all=paths.flat(),xmin=Math.min(...all.map(p=>p[0])),xmax=Math.max(...all.map(p=>p[0])),ymin=Math.min(...all.map(p=>p[1])),ymax=Math.max(...all.map(p=>p[1]));
 const scale=Math.min((s.w-65)/(xmax-xmin),(s.h-55)/(ymax-ymin)),X=x=>(s.w-(xmax-xmin)*scale)/2+(x-xmin)*scale,Y=y=>25+(ymax-y)*scale;
 const inputPower=currentPatch().reduce((sum,v)=>sum+v*v,0);
 paths.forEach((points,ch)=>{
  for(let i=1;i<points.length;i++){
   const [re,im]=trajectory[i][ch],power=(re*re+im*im)/Math.max(inputPower,1e-20);
   s.ctx.strokeStyle=`hsl(${210-170*Math.min(1,power*3)} 55% ${70-25*Math.min(1,power*3)}%)`;s.ctx.lineWidth=1.7;
   s.ctx.beginPath();s.ctx.moveTo(X(points[i-1][0]),Y(points[i-1][1]));s.ctx.lineTo(X(points[i][0]),Y(points[i][1]));s.ctx.stroke();
  }
  s.ctx.fillStyle='#d67b54';s.ctx.beginPath();s.ctx.arc(X(points[zIndex][0]),Y(points[zIndex][1]),3.2,0,Math.PI*2);s.ctx.fill();
 });
 s.ctx.fillStyle='#748399';s.ctx.textAlign='center';s.ctx.fillText('传播 z：0 → '+study.parameters.length_mm+' mm；路径按模态功率着色，橙点为当前截面。',s.w/2,s.h-8);
}
function drawPropagation(){zIndex=+$('z').value;$('z-value').textContent=kernel().z_mm[zIndex].toFixed(2)+' mm';heat();modal();geometry();}
function stop(){playing=false;cancelAnimationFrame(raf);$('play').textContent='▶ 播放传播';}
function update(){stop();kernelKey=$('kernel').value;imageKey=$('image').value;mode=$('mode').value;patchIndex=+$('patch').value;$('z').max=kernel().z_mm.length-1;$('z').value=Math.min(+$('z').value,+$('z').max);updateMaps();updateKernel();computeTrajectory();drawPropagation();}
$('image').onchange=update;$('kernel').onchange=update;$('mode').onchange=update;$('patch').oninput=()=>{stop();patchIndex=+$('patch').value;updateMaps();computeTrajectory();drawPropagation();};
$('next-patch').onclick=()=>{$('patch').value=(+$('patch').value+1)%484;$('patch').oninput();};
['input-map','reference-map','field-map','intensity-map'].forEach(id=>$(id).onclick=e=>{
 const c=$(id),box=c.mapBox,rect=c.getBoundingClientRect(),x=e.clientX-rect.left-box.left,y=e.clientY-rect.top-box.top;
 if(x<0||y<0||x>=box.side||y>=box.side)return;
 let row=Math.floor(y/box.side*box.n),column=Math.floor(x/box.side*box.m);
 if(id==='input-map'){row-=1;column-=1;}row=Math.max(0,Math.min(21,row));column=Math.max(0,Math.min(21,column));$('patch').value=row*22+column;$('patch').oninput();
});
$('z').oninput=()=>{stop();drawPropagation();};
$('play').onclick=()=>{if(playing){stop();return;}playing=true;last=0;if(+$('z').value>=+$('z').max)$('z').value=0;$('play').textContent='Ⅱ 暂停播放';function tick(time){if(!playing)return;if(time-last>55){last=time;$('z').value=+$('z').value+1;drawPropagation();if(+$('z').value>=+$('z').max){stop();return;}}raf=requestAnimationFrame(tick);}raf=requestAnimationFrame(tick);};
let resize;window.addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(update,120);});document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)document.querySelectorAll('.nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}),{rootMargin:'-10% 0px -65% 0px'});document.querySelectorAll('section[id]').forEach(s=>observer.observe(s));
$('kernel').value=kernelKey;$('image').value=imageKey;update();
