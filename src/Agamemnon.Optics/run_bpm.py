"""Structured offline general BPM CLI; see docs/agent/general-bpm.md."""
import argparse
import base64
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html import escape
import io
import json
from pathlib import Path
import platform
import sys
import numpy as np
import PIL
from PIL import Image
from bpm import Grid, MODEL_VERSION, gaussian_input, propagate, verify, validate_guides


def cases(spec):
    if set(spec)-{'grid','guides','input','scan','roi_um'}:
        raise ValueError('unknown configuration keys')
    base={k:deepcopy(v) for k,v in spec.items() if k != 'scan'}
    if 'scan' not in spec:
        return [('base',base)]
    scan=spec['scan']
    if set(scan) != {'path','values'} or not 1 <= len(scan['values']) <= 12:
        raise ValueError('scan requires path and 1..12 values')
    path=scan['path'].split('.')
    if path[0] not in ('grid','guides','input'):
        raise ValueError('scan path must start with grid, guides or input')
    result=[]
    for value in scan['values']:
        item=deepcopy(base); parent=item
        for key in path[:-1]:
            parent=parent[int(key)] if isinstance(parent,list) else parent[key]
        key=int(path[-1]) if isinstance(parent,list) else path[-1]
        if isinstance(parent,dict) and key not in parent:
            raise ValueError('scan path must reference an existing parameter')
        parent[key]=value
        result.append((f'{scan["path"]}={value}',item))
    return result


def prepare(spec):
    g=Grid(**spec['grid']).validate()
    guides=spec['guides']; validate_guides(g,guides)
    launch=lambda h: gaussian_input(h,**spec['input'])
    # Preflight all mandatory refinement grids before any long propagation.
    from dataclasses import replace
    for h in (g,replace(g,step_um=g.step_um/2,samples=2),replace(g,points=tuple(2*n for n in g.points),samples=2),
              replace(g,points=tuple(3*n//2 for n in g.points),windows_um=tuple(1.5*w for w in g.windows_um),samples=2)):
        validate_guides(h,guides); launch(h)
    roi=spec.get('roi_um')
    if roi is not None:
        if len(roi) != len(g.points): raise ValueError('ROI dimension mismatch')
        for pair,w in zip(roi,g.windows_um):
            if len(pair)!=2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and np.isfinite(v) for v in pair) or not -w/2 <= pair[0] < pair[1] <= w/2:
                raise ValueError('ROI requires finite [lower,upper] inside each transverse window')
    return g,guides,launch,None


def run_study(spec):
    prepared=[(name,item,prepare(item)) for name,item in cases(spec)]
    return run_prepared(prepared)


def run_prepared(prepared, targets=None, objective='roi_power'):
    """Shared orchestration; Python callbacks and Gaussian JSON use identical checks."""
    if sum(int(np.prod(p[2][0].points))*min(p[2][0].samples,int(np.ceil(p[2][0].length_um/p[2][0].step_um))+1) for p in prepared)>32000000:
        raise ValueError('study storage exceeds 32 million complex values')
    rows=[]; runs=[]
    for case_index,(name,item,(g,guides,launch,index_factory)) in enumerate(prepared):
        r=propagate(g,guides,launch(g),index_fn=None if index_factory is None else index_factory(g))
        check=verify(g,guides,launch,index_factory=index_factory)
        dv=float(np.prod(np.divide(g.windows_um,g.points)))
        power=abs(r['fields'])**2*dv
        metrics={'output_power':float(power[-1].sum()),'centroid_um':r['centroid_um'][-1].tolist()}
        if targets is not None and targets[case_index] is not None:
            target=np.asarray(targets[case_index](g),dtype=complex)
            norm=float(np.sum(abs(target)**2)*dv)
            if target.shape!=tuple(g.points) or not np.all(np.isfinite(target)) or not np.isfinite(norm) or norm<=0:
                raise ValueError('target field must be finite, nonzero and match grid')
            metrics['target_overlap']=float(abs(np.vdot(target,r['fields'][-1])*dv)**2/norm)
            r['target_field']=target/np.sqrt(norm)
        if 'roi_um' in item:
            coords=np.meshgrid(*r['axes_um'],indexing='ij',sparse=True)
            mask=np.logical_and.reduce(np.broadcast_arrays(*((q>=a)&(q<b) for q,(a,b) in zip(coords,item['roi_um']))))
            if not np.any(mask): raise ValueError('ROI contains no grid cells')
            r['roi_power']=power[:,mask].sum(axis=1)
            metrics['roi_power']=float(r['roi_power'][-1])
        scan_ok=r['max_power_drift']<1e-8 and r['max_edge_power']<1e-4 and r['max_high_frequency_power']<1e-6
        rows.append(dict(name=name,input=item,metrics=metrics,verification=check,
                         diagnostics={k:r[k] for k in ('max_power_drift','max_edge_power','max_high_frequency_power','actual_step_um','input_power_before_normalization')},
                         status='verified_theoretical_propagation' if scan_ok and check['passed'] else 'numerical_checks_failed'))
        runs.append(r)
    eligible=[i for i,row in enumerate(rows) if row['status']=='verified_theoretical_propagation' and 'roi_power' in row['metrics']]
    best=max(eligible,key=lambda i:rows[i]['metrics']['roi_power']) if eligible else None
    selectable=[i for i,row in enumerate(rows) if row['status']=='verified_theoretical_propagation' and objective in row['metrics']]
    selected=max(selectable,key=lambda i:rows[i]['metrics'][objective]) if selectable else None
    return dict(model_version=MODEL_VERSION,parameter_origin='assumed_not_measured',timestamp_utc=datetime.now(timezone.utc).isoformat(),
                status='verified_theoretical_propagation' if all(row['status']=='verified_theoretical_propagation' for row in rows) else 'numerical_checks_failed',
                cases=rows,best_verified_roi_case=best,best_verified_case=selected,objective=objective,
                selection='maximum requested final metric among supplied verified cases only; target overlap is against supplied template, not automatically a guided mode; not global optimum',
                coordinates='x,y transverse; z propagation; um; fields array [sample,x] or [sample,x,y]; no device mapping'),runs


def heatmap(a,maximum):
    a=np.clip(a/max(maximum,1e-30),0,1)
    rgb=np.stack((255*np.sqrt(a),255*a,255*np.minimum(1,3*a)),axis=-1).astype('uint8')
    return Image.fromarray(rgb)


def png_data(im):
    buf=io.BytesIO(); im.save(buf,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')


def phase_map(field,maximum):
    intensity=abs(field)**2
    hsv=np.stack(((np.angle(field)+np.pi)/(2*np.pi)*255,np.full(field.shape,255),
                  np.where(intensity>maximum*1e-6,255,0)),axis=-1).astype('uint8')
    return Image.frombytes('HSV',field.shape[::-1],hsv.tobytes()).convert('RGB')


def index_map(dn,maximum):
    t=np.clip(dn/max(maximum,1e-30),-1,1)
    return Image.fromarray(np.stack((255*(1-np.maximum(-t,0)),255*(1-abs(t)),255*(1-np.maximum(t,0))),axis=-1).astype('uint8'))


def write_report(output,result,runs):
    sections=[]; viewers=[]
    for i,(row,r) in enumerate(zip(result['cases'],runs)):
        intensity=abs(r['fields'])**2
        is2=intensity.ndim==3
        # Horizontal x, vertical z. In 2D integrate over y (units 1/um).
        projection=intensity.sum(axis=2)*(row['input']['grid']['windows_um'][1]/row['input']['grid']['points'][1]) if is2 else intensity
        im=heatmap(projection,float(projection.max())).resize((700,350))
        im.save(output/f'case_{i}_xz.png')
        if is2:
            frames=[png_data(heatmap(frame.T[::-1],float(intensity.max())).resize((400,400))) for frame in intensity]
        else:
            frames=[png_data(heatmap(frame[None,:],float(intensity.max())).resize((600,100))) for frame in intensity]
        orient=lambda a:a.T[::-1] if is2 else a[None,:]
        size=(400,400) if is2 else (600,100)
        phases=[png_data(phase_map(orient(f),float(intensity.max())).resize(size)) for f in r['fields']]
        index_frames=[]; dn_max=0.
        if 'refractive_index' in r:
            dn=r['refractive_index']-row['input']['grid']['background_index']
            dn_max=float(np.max(abs(dn)))
            index_frames=[png_data(index_map(orient(a),dn_max).resize(size)) for a in dn]
        viewers.append(dict(frames=frames,phase=phases,index=index_frames,z=r['z_um'].tolist(),centroid=r['centroid_um'].tolist(),roi=r.get('roi_power',np.array([])).tolist()))
        windows=row['input']['grid']['windows_um']
        sections.append(f'<section><h2>{escape(row["name"])}</h2><p>{escape(row["status"])}</p>'
                        f'<p>x: {-windows[0]/2:g} … {windows[0]/2:g} µm →；z: 0 … {r["z_um"][-1]:g} µm ↓。颜色由黑到亮，线性强度，同案例帧共用色标。</p>'
                        f'<img class="map" src="{png_data(im)}" alt="沿z的x方向光强分布，二维场对y积分">'
                        f'<p>横截面：x →；'+('y ↑。光强单位 1/µm²。' if is2 else '光强单位 1/µm。')+
                        f'相位色环 −π…π rad（光强低于峰值1e−6处遮黑）。折射率增量蓝负/白零/红正，范围±{dn_max:.4g}。</p>'
                        f'<select aria-label="截面显示内容" id="mode{i}" onchange="show({i})"><option value="frames">光强</option><option value="phase">相位</option>'+ ('<option value="index">折射率增量</option>' if index_frames else '')+f'</select><br><img id="frame{i}" alt="所选物理量的横截面">'
                        f'<p><input aria-label="传播位置" id="slider{i}" type="range" min="0" max="{len(frames)-1}" value="0"><button onclick="play({i})">播放 / 暂停</button></p><p id="readout{i}"></p>'
                        f'<details><summary>参数、指标与收敛检查</summary><pre>{escape(json.dumps(row,ensure_ascii=False,indent=2))}</pre></details></section>')
    data=json.dumps(viewers,allow_nan=False)
    summary=f'<p>比较指标：{escape(result.get("objective","roi_power"))}；已验证候选编号（0起点）：{result.get("best_verified_case")}。仅比较本次候选。</p>'
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>通用波导光场传播</title>
<style>body{font-family:system-ui;background:#f5f4f0;color:#17242b;max-width:1000px;margin:auto;padding:24px}section{background:white;padding:24px;margin:24px 0;border-radius:14px}img{max-width:100%;image-rendering:auto}.map{width:700px}input{width:65%}pre{white-space:pre-wrap;overflow-wrap:anywhere}button{padding:8px}h1{font-size:30px}</style>
<h1>通用波导 · 光场传播</h1><p>标量傍轴 / 薛定谔形式 / 分步傅里叶。所有物理参数 assumed，未标定；光场演化不代表光子轨迹或设备状态。</p><p>周期边界、无吸收层。标为失败的结果不可作为已验证设计。区域功率包含辐射和尾场，不是导模效率。</p>
<p><a href="result.json">完整结果 JSON</a> · <a href="fields.npz">复场与坐标 NPZ</a> · <a href="manifest.json">来源与哈希</a></p>'''+summary+''.join(sections)+'''<script>const data='''+data+''';const timers={};function show(i){const d=data[i],j=+document.getElementById('slider'+i).value,mode=document.getElementById('mode'+i).value;document.getElementById('frame'+i).src=d[mode][j];document.getElementById('readout'+i).textContent='z = '+d.z[j].toFixed(2)+' µm；质心 = '+d.centroid[j].map(x=>x.toFixed(3)).join(', ')+' µm'+(d.roi.length?'；区域功率 = '+(100*d.roi[j]).toFixed(3)+'%':'')}function play(i){if(timers[i]){clearInterval(timers[i]);delete timers[i];return}timers[i]=setInterval(()=>{const s=document.getElementById('slider'+i);s.value=(+s.value+1)%data[i].frames.length;show(i)},120)}data.forEach((_,i)=>{document.getElementById('slider'+i).oninput=()=>show(i);show(i)})</script></html>'''
    (output/'index.html').write_text(html,encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,help='Gaussian JSON config, or parameter overrides JSON with --scene')
    parser.add_argument('--scene',type=Path,help='Trusted executable Python scene, API_VERSION=1')
    parser.add_argument('--open-report',action='store_true')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'artifacts'/'optics'/datetime.now().strftime('bpm-%Y%m%d-%H%M%S-%f'))
    args=parser.parse_args(argv)
    config=args.config if args.config is not None else (None if args.scene else Path(__file__).with_name('bpm_example.json'))
    spec={} if config is None else json.loads(config.read_text(encoding='utf-8-sig'))
    if args.output.exists() and any(args.output.iterdir()): raise ValueError('output directory must be empty')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'input.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if args.scene:
        from python_scene import load_scene, run_python_study
        (args.output/'scene_source.py').write_bytes(args.scene.read_bytes())
        with redirect_stdout(sys.stderr): result,runs=run_python_study(load_scene(args.scene),spec)
        result['scene_source']=str(args.scene.resolve())
        result['scene_source_sha256']=hashlib.sha256((args.output/'scene_source.py').read_bytes()).hexdigest()
    else:
        result,runs=run_study(spec)
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    arrays={}
    for i,r in enumerate(runs):
        for k in ('fields','z_um','centroid_um','roi_power','refractive_index','target_field'):
            if k in r: arrays[f'case_{i}_{k}']=r[k]
        for j,a in enumerate(r['axes_um']): arrays[f'case_{i}_{"xy"[j]}_um']=a
    np.savez_compressed(args.output/'fields.npz',**arrays)
    write_report(args.output,result,runs)
    manifest=dict(python=sys.version,numpy=np.__version__,pillow=PIL.__version__,platform=platform.platform(),model_version=MODEL_VERSION,
                  input_sha256=None if config is None else hashlib.sha256(config.read_bytes()).hexdigest(),
                  launcher_sha256=hashlib.sha256((Path(__file__).resolve().parents[2]/'simulate.py').read_bytes()).hexdigest(),
                  source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
                  package_source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve().parents[1]/'waveguide_sim').glob('*.py')},
                  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file()})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],output=str(args.output.resolve()),best_verified_roi_case=result['best_verified_roi_case'],
                         best_verified_case=result['best_verified_case'],objective=result['objective']),ensure_ascii=False))
    if args.open_report:
        import webbrowser
        webbrowser.open((args.output/'index.html').resolve().as_uri())
    return 0 if result['status']=='verified_theoretical_propagation' else 2


if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,TypeError,KeyError,IndexError,OSError,ImportError,SyntaxError,AttributeError) as error:
        print(json.dumps(dict(status='error',error=str(error)),ensure_ascii=False),file=sys.stderr); sys.exit(1)
