"""Run a small assumed curved graded-index guide: python -m waveguide_sim."""
from datetime import datetime
from pathlib import Path
import json
import argparse
import hashlib
import platform
import sys
import numpy as np
from . import Grid, Waveguide, gaussian_beam, simulate, check_convergence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New result directory; existing directories are refused')
    args = parser.parse_args()
    output = args.output or Path('artifacts')/'rk4'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    grid = Grid(windows_um=(48.,48.), points=(64,64), length_um=20., step_um=.1)
    # assumed_not_measured: graded elliptical guide, smooth lateral bend.
    guide = Waveguide(
        shape=lambda z,q: np.exp(-((q[0]-.5*(1-np.cos(np.pi*z/20)))/3)**2-(q[1]/4)**2),
        core_index=1.453, cladding_index=1.45)
    launch = gaussian_beam(waists_um=(3.,4.))
    parameters = dict(parameter_source='assumed_not_measured', wavelength_um=.78,
        core_index=1.453, cladding_index=1.45, radii_um=[3.,4.], bend_um=1.,
        model='scalar-paraxial-rk4-v1', geometry='graded ellipse; center_x=.5*(1-cos(pi*z/20))')
    (output/'input.json').write_text(json.dumps(parameters,indent=2),encoding='utf-8')
    result = simulate(grid,guide,launch)
    result.save(output/'fields.npz')
    checks = check_convergence(grid,guide,launch)
    report = dict(status='verified_theoretical_propagation' if checks['passed'] and result.diagnostics['checks_passed'] else 'numerical_checks_failed',
                  parameters=parameters, diagnostics=result.diagnostics, convergence=checks,
                  shape=list(result.field.shape), output=str(output.resolve()))
    (output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    manifest = dict(python=sys.version, numpy=np.__version__, platform=platform.platform(),
        model='scalar-paraxial-rk4-v1',
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        output_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='verified_theoretical_propagation' else 2


if __name__ == '__main__':
    raise SystemExit(main())
