"""Passive figure-2 structure and waveguide parameter sweep, no active phase.

python run_passive_lantern.py --config passive_study_config.py --output NEW_DIR
"""
import argparse
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
import numpy as np
import PIL
from passive_lantern import (MODEL_VERSION,isolated_mode,coupling_table,pair_coupling,
                            modal_propagate,local_pair_check)
from passive_report import write_report


def array_checks(mode):
    return dict(energy_per_um=mode['energy_per_um'],residual_per_um=mode['residual_per_um'],edge_power=mode['edge_power'],rms_radius_um=mode['rms_radius_um'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('passive_study_config.py'))
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'artifacts'/'optics'/datetime.now().strftime('passive-%Y%m%d-%H%M%S-%f'))
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): raise ValueError('output directory must be empty')
    args.output.mkdir(parents=True,exist_ok=True)
    config_path=args.config.resolve()
    (args.output/'study_config.py').write_bytes(config_path.read_bytes())
    spec=importlib.util.spec_from_file_location('_passive_study',config_path)
    config=importlib.util.module_from_spec(spec); spec.loader.exec_module(config)
    if config.GEOMETRY.rows!=8 or config.GEOMETRY.columns!=8: raise ValueError('this report expects 8x8 geometry')
    if not 1<=len(config.MATERIAL_CASES)<=9 or not 1<=len(config.PITCHES_UM)<=6: raise ValueError('maximum 9 materials and 6 pitches')
    input_spec=dict(geometry=asdict(config.GEOMETRY),pitches_um=config.PITCHES_UM,materials=[dict(name=n,**asdict(m)) for n,m in config.MATERIAL_CASES],input_channel=config.INPUT_CHANNEL)
    (args.output/'input.json').write_text(json.dumps(input_spec,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    rows=[]; runs=[]; arrays={}; modes=[]; tables=[]
    for material_index,(name,m) in enumerate(config.MATERIAL_CASES):
        print(f'Computing assumed mode: {name}',file=sys.stderr,flush=True)
        mode=isolated_mode(m); table=coupling_table(m,mode); modes.append(mode); tables.append(table)
        arrays[f'material_{material_index}_mode']=mode['mode']
        arrays[f'material_{material_index}_mode_x_um']=np.arange(mode['grid'].points[0])*mode['grid'].windows_um[0]/mode['grid'].points[0]-mode['grid'].windows_um[0]/2
        arrays[f'material_{material_index}_coupling_distances_um']=table['distances_um']
        arrays[f'material_{material_index}_coupling_per_mm']=table['coupling_per_mm']
        beta=2*np.pi*m.background_index/m.wavelength_um-mode['energy_per_um']
        for pitch in config.PITCHES_UM:
            p=replace(config.GEOMETRY,pitch_um=pitch).validate()
            print(f'Propagating 64 channels: {name}, pitch={pitch:g} um',file=sys.stderr,flush=True)
            r=modal_propagate(p,table,beta,config.INPUT_CHANNEL)
            refined=modal_propagate(replace(p,step_mm=p.step_mm/2,samples=2),table,beta,config.INPUT_CHANNEL)
            field_error=float(np.linalg.norm(r['fields'][-1]-refined['fields'][-1]))
            power_error=float(np.sum(abs(r['power'][-1]-refined['power'][-1])))
            tail_bound=(p.rows*p.columns-1)*p.length_mm*table['cutoff_coupling_per_mm']
            checks=dict(half_step_output_field_l2=field_error,half_step_output_power_l1=power_error,
                        max_power_drift=max(r['max_power_drift'],refined['max_power_drift']),
                        coupling_tail_conservative_field_bound=tail_bound,isolated_mode=array_checks(mode))
            checks['passed']=(field_error<.002 and power_error<.002 and checks['max_power_drift']<1e-8 and tail_bound<.002
                              and mode['energy_per_um']<0 and mode['residual_per_um']<1e-5 and mode['edge_power']<1e-6)
            c=pair_coupling(m,mode,pitch)['coupling_per_mm']
            row=dict(name=f'{name} / {pitch:g} µm',material_name=name,material=asdict(m),geometry=asdict(p),coupling_per_mm=c,
                     half_transfer_length_mm=float(np.pi/(4*c)) if c>0 else None,
                     metrics=dict(input_retention=float(r['power'][-1,config.INPUT_CHANNEL]),effective_channels=float(r['effective_channels'][-1]),
                                  participation=float(r['participation'][-1]),peak_effective_channels=float(r['effective_channels'].max()),output_power=float(r['power'][-1].sum())),
                     verification=checks)
            rows.append(row); runs.append(r)
            i=len(rows)-1
            for key in ('z_mm','fields','power','effective_channels','positions_um'): arrays[f'case_{i}_{key}']=r[key]
            # Persist progress, including failed diagnostics, before proceeding.
            (args.output/'progress.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('Verifying baseline mode refinement and continuous local BPM',file=sys.stderr,flush=True)
    m=config.MATERIAL_CASES[0][1]; mode=modes[0]; pitch=config.LOCAL_CHECK_PITCH_UM
    fine=isolated_mode(m,points=512,imaginary_step_um=1.,iterations=8000)
    step=isolated_mode(m,imaginary_step_um=1.,iterations=8000)
    window=isolated_mode(m,points=384,window_um=192.)
    cs=[pair_coupling(m,s,pitch)['coupling_per_mm'] for s in (mode,fine,step,window)]
    coefficient_checks=dict(base_per_mm=cs[0],half_grid_relative_error=abs(cs[1]-cs[0])/cs[0],
                            half_imaginary_step_relative_error=abs(cs[2]-cs[0])/cs[0],larger_window_relative_error=abs(cs[3]-cs[0])/cs[0])
    coefficient_checks['passed']=max(coefficient_checks[k] for k in ('half_grid_relative_error','half_imaginary_step_relative_error','larger_window_relative_error'))<.02
    local=local_pair_check(m,mode,pitch,length_um=config.LOCAL_CHECK_LENGTH_UM)
    local_half=local_pair_check(m,mode,pitch,length_um=config.LOCAL_CHECK_LENGTH_UM,step_um=1.)
    local_grid=local_pair_check(m,fine,pitch,length_um=config.LOCAL_CHECK_LENGTH_UM)
    local_window=local_pair_check(m,window,pitch,length_um=config.LOCAL_CHECK_LENGTH_UM)
    dx=mode['grid'].windows_um[0]/mode['grid'].points[0]
    base=local['run']['fields'][-1]
    comparisons=[local_half['run']['fields'][-1],local_grid['run']['fields'][-1][::2,::2],local_window['run']['fields'][-1][64:320,64:320]]
    local_checks=dict(pitch_um=pitch,length_um=config.LOCAL_CHECK_LENGTH_UM,
                      bpm_vs_cmt_max_right_power_difference=local['max_power_difference'],
                      basis_projection_remaining_power=float(local['projection_total'][-1]),
                      half_step_field_l2=float(np.linalg.norm(base-comparisons[0])*dx),
                      half_grid_field_l2=float(np.linalg.norm(base-comparisons[1])*dx),
                      larger_window_field_l2=float(np.linalg.norm(base-comparisons[2])*dx),
                      max_edge_power=max(s['run']['max_edge_power'] for s in (local,local_half,local_grid,local_window)),
                      max_power_drift=max(s['run']['max_power_drift'] for s in (local,local_half,local_grid,local_window)),
                      mode_coefficient_refinement=coefficient_checks)
    local_checks['passed']=(local_checks['bpm_vs_cmt_max_right_power_difference']<.02 and min(local['projection_total'])>.98
                            and max(local_checks[k] for k in ('half_step_field_l2','half_grid_field_l2','larger_window_field_l2'))<.002
                            and local_checks['max_edge_power']<1e-4 and local_checks['max_power_drift']<1e-8 and coefficient_checks['passed'])
    # Check lookup interpolation separately on the baseline full structure.
    half_table=coupling_table(m,mode,spacing_um=.25)
    p=replace(config.GEOMETRY,pitch_um=pitch)
    rr=modal_propagate(p,half_table,2*np.pi*m.background_index/m.wavelength_um-mode['energy_per_um'],config.INPUT_CHANNEL)
    base_index=next(i for i,r in enumerate(rows) if r['material']==asdict(m) and r['geometry']['pitch_um']==pitch)
    table_error=float(np.linalg.norm(rr['fields'][-1]-runs[base_index]['fields'][-1]))
    result=dict(model_version=MODEL_VERSION,timestamp_utc=datetime.now(timezone.utc).isoformat(),parameter_origin='assumed_not_measured',
                active_phase_modulation=False,input_channel=config.INPUT_CHANNEL,input=input_spec,cases=rows,local_verification=local_checks,
                baseline_half_lookup_spacing_field_l2=table_error,selection=None,
                source='Cao et al. 2026, SI Fig.3/Table 1; half-cosine reconstruction, not author CAD',
                limitations='No bend radiation/material loss/polarization/fabrication disorder; full-chip discrete CMT, not continuous BPM. Pairwise isotropic coupling from assumed Gaussian isolated-mode projection. Passive path-length phase included. Local BPM validation only baseline straight pair; no globally optimal parameter selection.')
    result['status']='verified_passive_theoretical_study' if all(r['verification']['passed'] for r in rows) and local_checks['passed'] and table_error<.002 else 'numerical_checks_failed'
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    np.savez_compressed(args.output/'modal_fields.npz',**arrays)
    np.savez_compressed(args.output/'local_pair_fields.npz',**{k:local['run'][k] for k in ('fields','z_um','centroid_um')},
                        x_um=local['run']['axes_um'][0],y_um=local['run']['axes_um'][1],right_projected_power=local['right_projected_power'],cmt_right_power=local['cmt_right_power'])
    write_report(args.output,result,runs,local_checks)
    manifest=dict(model_version=MODEL_VERSION,python=sys.version,numpy=np.__version__,pillow=PIL.__version__,platform=platform.platform(),
                  config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
                  sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
                  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file()})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],output=str(args.output.resolve()),cases=len(rows),local_checks=local_checks),ensure_ascii=False))
    return 0 if result['status']=='verified_passive_theoretical_study' else 2


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    try: sys.exit(main())
    except (ValueError,TypeError,KeyError,OSError,ImportError) as error:
        print(json.dumps(dict(status='error',error=str(error)),ensure_ascii=False),file=sys.stderr); sys.exit(1)
