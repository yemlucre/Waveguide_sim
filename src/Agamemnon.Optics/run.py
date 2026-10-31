"""CLI: python run.py [--config example.json] [--output EMPTY_DIRECTORY]."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import numpy as np
import PIL
from optics import MODEL_VERSION, Parameters, eigensystem, find_design, launch_mode, propagate
from report import write_report


def verify_candidate(p):
    base=propagate(p,sample_count=2)
    step=propagate(replace(p,step_um=p.step_um/2),sample_count=2)
    fine=propagate(replace(p,points=p.points*2),sample_count=2)
    window=propagate(replace(p,window_um=p.window_um*1.5,points=p.points*3//2),sample_count=2)
    values,modes=eigensystem(p)
    dx=p.window_um/p.points
    initial=launch_mode(p)
    exact=modes @ (np.exp(-1j*values*p.length_um)*(modes.T.conj()@initial*dx))
    spectral_error=float(np.sqrt(np.sum(abs(base['fields'][-1]-exact)**2)*dx))
    right=float(base['right_power'][-1])
    result=dict(power_drift=base['max_power_drift'],max_edge_power=max(r['max_edge_power'] for r in (base,step,fine,window)),
                half_step_right_power_difference=abs(float(step['right_power'][-1])-right),
                half_grid_right_power_difference=abs(float(fine['right_power'][-1])-right),
                enlarged_window_right_power_difference=abs(float(window['right_power'][-1])-right),
                spectral_reference_field_l2_error=spectral_error,
                supermode_half_beat_length_um=float(np.pi/(2*(values[1]-values[0]))))
    result['passed']=(result['power_drift']<1e-8 and result['max_edge_power']<1e-4
                      and max(result[k] for k in ('half_step_right_power_difference','half_grid_right_power_difference','enlarged_window_right_power_difference'))<0.002
                      and spectral_error<0.01)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('example.json'))
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'artifacts'/'optics'/datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    args=parser.parse_args()
    spec=json.loads(args.config.read_text(encoding='utf-8-sig'))
    p=Parameters(**spec['parameters']).validate()
    # Reserve headroom for all mandatory refinement runs before expensive work.
    replace(p,points=p.points*2).validate()
    replace(p,window_um=p.window_um*1.5,points=p.points*3//2).validate()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Output directory must be empty (previous results are preserved)')
    args.output.mkdir(parents=True,exist_ok=True)
    result,runs=find_design(p,spec['separations_um'],spec['target'])
    result.update(model_version=MODEL_VERSION,parameter_origin='assumed_not_measured',input=spec,
                  timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  metric='integral_x_positive_abs_field_squared_divided_by_input_power',
                  coordinate_system='x transverse, z propagation; um; no device mapping')
    if result['selected_index'] is not None:
        result['verification']=verify_candidate(Parameters(**result['selected_parameters']))
    scan_ok=all(r['max_power_drift']<1e-8 and r['max_edge_power']<1e-4 for r in result['scan'])
    result['scan_numerics_passed']=scan_ok
    result['status']=('numerical_checks_failed' if not scan_ok else 'verified_theoretical_candidate' if result.get('verification',{}).get('passed') and result.get('target_error',1)<0.002
                      else 'numerical_checks_failed' if result['selected_index'] is not None else 'target_not_reached')
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    arrays={}
    for i,r in enumerate(runs):
        for key in ('x_um','z_um','fields','left_power','right_power'):
            arrays[f'gap_{i}_{key}']=r[key]
    np.savez_compressed(args.output/'fields.npz',**arrays)
    write_report(args.output,result,runs,spec['separations_um'])
    manifest=dict(python=sys.version,numpy=np.__version__,pillow=PIL.__version__,platform=platform.platform(),model_version=MODEL_VERSION,
                  source_hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.iterdir() if f.suffix in ('.py','.html','.js')},
                  files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in args.output.iterdir() if f.is_file()})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],output=str(args.output.resolve()),selected=result.get('selected_parameters'),verification=result.get('verification')),ensure_ascii=False,indent=2))
    return 0 if result['status']=='verified_theoretical_candidate' else 2


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps(dict(status='error',error=str(error)),ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
