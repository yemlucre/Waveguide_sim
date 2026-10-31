"""Build and validate a LAMP-inspired modal optical convolution demonstration."""
import argparse
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib,json,os,platform,sys
from pathlib import Path
import numpy as np
import PIL
from lamp import (MODEL_VERSION,LampParameters,build_network,centres,train_kernel,
                  evaluate_image,snapshot_transfers,transfer)
from lamp_report import write_lamp_report


KERNELS={
 'sobel_x':dict(name='Sobel X · 竖直边缘',kernel=[[-1,0,1],[-2,0,2],[-1,0,1]]),
 'sobel_y':dict(name='Sobel Y · 水平边缘',kernel=[[-1,-2,-1],[0,0,0],[1,2,1]]),
 'blur':dict(name='均值模糊',kernel=(np.ones((3,3))/9).tolist()),
 'laplacian':dict(name='Laplacian · 边界变化',kernel=[[0,1,0],[1,-4,1],[0,1,0]])}


def example_images():
    y,x=np.mgrid[:24,:24]
    frame=np.zeros((24,24));frame[4:20,4:7]=1;frame[4:20,17:20]=1;frame[10:13,4:20]=1
    disk=np.clip((8-np.sqrt((x-11.5)**2+(y-11.5)**2))/2,0,1)*(0.3+0.7*x/23)
    checker=(((x//4+y//4)%2)*.85+.1)
    return dict(letter_h=dict(name='字母 H',pixels=frame.tolist()),
                soft_disk=dict(name='圆形与渐变',pixels=disk.tolist()),
                checker=dict(name='棋盘格',pixels=checker.tolist()))


def run_study(p,epochs=2400,restarts=3):
    net=build_network(p)
    refined=build_network(replace(p,step_mm=p.step_mm/2))
    mixer_error=max(float(np.linalg.norm(a-b,2)) for a,b in zip(net['mixers'],refined['mixers']))
    images=example_images();results={};arrays={}
    rng=np.random.default_rng(781)
    probes=rng.normal(size=(9,200))+1j*rng.normal(size=(9,200))
    zero=transfer(net['mixers'],np.zeros((3,9)))
    for index,(key,definition) in enumerate(KERNELS.items()):
        fit=train_kernel(net['mixers'],definition['kernel'],seed=20261030+index,epochs=epochs,restarts=restarts)
        matrix=fit['matrix'];norm=np.linalg.norm(fit['kernel'])
        unitarity=float(np.linalg.norm(matrix.conj().T@matrix-np.eye(9),2))
        fine_matrix=transfer(refined['mixers'],fit['phases'])
        step_difference=float(np.linalg.norm(fine_matrix-matrix,2))
        ideal=fit['kernel'].ravel()@probes
        actual=norm*(matrix@probes)[4]
        probe_error=float(np.linalg.norm(actual-ideal)/np.linalg.norm(ideal))
        zs,matrices=snapshot_transfers(net,fit['phases'])
        evaluations={}
        for name,image in images.items():
            evaluation=evaluate_image(image['pixels'],fit['kernel'],matrix)
            evaluation_zero=evaluate_image(image['pixels'],fit['kernel'],zero)
            evaluations[name]=dict(reference=evaluation['reference'].tolist(),
                coherent_real=evaluation['field'].real.tolist(),coherent_imag=evaluation['field'].imag.tolist(),
                raw_intensity=evaluation['intensity'].tolist(),intensity_rescaled=evaluation['intensity_rescaled'].tolist(),
                unprogrammed_real=evaluation_zero['field'].real.tolist(),unprogrammed_imag=evaluation_zero['field'].imag.tolist(),
                unprogrammed_intensity_rescaled=evaluation_zero['intensity_rescaled'].tolist(),
                relative_error=evaluation['complex_relative_error'],imaginary_rms=evaluation['imaginary_rms'])
        arrays[key+'_transfer']=matrix;arrays[key+'_phases']=fit['phases'];arrays[key+'_snapshot_transfers']=matrices
        arrays[key+'_z_mm']=zs;arrays[key+'_centres_um']=np.array([centres(p,z) for z in zs])
        results[key]=dict(name=definition['name'],kernel=fit['kernel'].tolist(),kernel_norm=float(norm),
            learned_real=fit['learned_kernel'].real.tolist(),learned_imag=fit['learned_kernel'].imag.tolist(),
            phases_rad=fit['phases'].tolist(),row_l2_error=fit['row_l2_error'],
            loss_history=fit['history'],best_restart=fit['restart'],best_epoch=fit['epoch'],
            unitarity_error=unitarity,half_step_operator_difference=step_difference,random_complex_probe_relative_error=probe_error,
            transfer_real=matrix.real.tolist(),transfer_imag=matrix.imag.tolist(),
            snapshot_real=np.round(matrices.real,9).tolist(),snapshot_imag=np.round(matrices.imag,9).tolist(),
            z_mm=zs.tolist(),centres_um=[centres(p,z).tolist() for z in zs],images=evaluations,
            passed=bool(fit['row_l2_error']<1e-3 and unitarity<1e-9 and step_difference<.01 and probe_error<.002))
    zero_z,zero_snapshots=snapshot_transfers(net,np.zeros((3,9)))
    passed=all(r['passed'] for r in results.values())
    result=dict(model_version=MODEL_VERSION,status='verified_modal_demo' if passed else 'numerical_checks_failed',
                timestamp_utc=datetime.now(timezone.utc).isoformat(),parameters=asdict(p),images=images,kernels=results,
                mixer_half_step_difference=mixer_error,output_channel=4,phase_z_mm=net['phase_z_mm'],
                encoding='pixel_value_is_real_field_amplitude_no_patch_normalization',
                operation='valid_stride_1_deep_learning_cross_correlation_not_flipped_mathematical_convolution',
                detector='signed_result_requires_assumed_ideal_phase_referenced_coherent_readout; CCD observes abs(a)^2',
                reproduction_status='paper_inspired_concept9_demo_not_authors_64_channel_chip_or_CNN_experiment',
                model_scope='discrete_mode_CMT_on_assumed_3D_paths_not_continuous_2plus1D_BPM',
                source_parameters=dict(reported=dict(signal_wavelength_nm=800,coupling_prefactor_per_mm=6.1688,
                    coupling_decay_per_um=.2641,coupling_fit_distance_um=[10,17],source_locator='SI p.10 Fig.4b / Note3',
                    actual_sample_channels=64,concept_channels=9),
                    assumed=['90 mm concept path, 3 radial fanout stages, 15..700 um pitch, quintic paths',
                    'isotropic exponential coupling beyond 10..17 um fit, all channel pairs, equal beta reference',
                    '3 ideal per-channel instantaneous phase screens, no thermal crosstalk or heater power conversion',
                    'amplitude encoding, sequential sliding windows, coherent detector for signed values',
                    'no bend/radiation/material loss or full-field mode profiles, analytic Adam optimization instead of experimental SPSA']),
                unprogrammed_snapshot_real=np.round(zero_snapshots.real,9).tolist(),unprogrammed_snapshot_imag=np.round(zero_snapshots.imag,9).tolist(),
                thresholds=dict(row_l2=1e-3,unitarity=1e-9,half_step_operator_difference=.01,random_probe_relative_error=.002),
                paper_url='https://www.nature.com/articles/s41467-026-72316-9',
                supplementary_url='https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-026-72316-9/MediaObjects/41467_2026_72316_MOESM1_ESM.pdf')
    return result,arrays


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'artifacts'/'optics'/('lamp-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('lamp_example.json'))
    args=parser.parse_args();spec=json.loads(args.config.read_text(encoding='utf-8-sig'))
    p=LampParameters(**spec['parameters']).validate()
    if args.output.exists() and any(args.output.iterdir()):raise ValueError('Output directory must be empty')
    result,arrays=run_study(p,**spec.get('training',{}))
    result['source_reference']=json.loads(Path(__file__).with_name('lamp_paper_reference.json').read_text(encoding='utf-8'))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    np.savez_compressed(args.output/'modal_fields.npz',**arrays)
    write_lamp_report(args.output,result)
    source=Path(__file__).parent
    hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in source.iterdir() if f.suffix in ('.py','.html','.js','.json')}
    manifest=dict(python=sys.version,numpy=np.__version__,pillow=PIL.__version__,platform=platform.platform(),
                  model_version=MODEL_VERSION,source_hashes=hashes,
                  files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in args.output.iterdir() if f.is_file()})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],output=str(args.output.resolve()),
                         kernels={k:dict(row_l2_error=v['row_l2_error'],half_step=v['half_step_operator_difference'],passed=v['passed']) for k,v in result['kernels'].items()}),ensure_ascii=False,indent=2))
    return 0 if result['status']=='verified_modal_demo' else 2


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps(dict(status='error',error=str(error)),ensure_ascii=False),file=sys.stderr);sys.exit(1)
