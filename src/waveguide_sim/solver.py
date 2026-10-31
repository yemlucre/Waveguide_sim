"""Method of lines: Fourier transverse Laplacian + classical four-stage RK4.

E = psi exp(i*k0*n0*z); d_z psi = i laplacian(psi)/(2*k0*n0)
                               + i*k0*(n**2-n0**2)*psi/(2*n0).
Periodic boundaries; scalar, forward, linear, weak-index paraxial model.
"""
from dataclasses import dataclass
import math
from pathlib import Path
import numpy as np
from .bpm import Grid, axes, refinement_grids


@dataclass
class Result:
    grid: Grid
    axes_um: tuple
    z_um: np.ndarray
    field: np.ndarray
    diagnostics: dict

    @property
    def intensity(self):
        return abs(self.field)**2

    @property
    def power(self):
        dv = math.prod(w/n for w,n in zip(self.grid.windows_um,self.grid.points))
        return self.intensity.sum(axis=tuple(range(1,self.field.ndim)))*dv

    def save(self, path):
        """Save numeric arrays only; refuse overwrite, read with allow_pickle=False."""
        import json
        from dataclasses import asdict
        arrays = dict(field=self.field, z_um=self.z_um, power=self.power,
                      metadata_json=np.array(json.dumps(dict(grid=asdict(self.grid),
                          diagnostics=self.diagnostics, model='scalar-paraxial-rk4-v1',
                          parameter_source='user_supplied_not_calibrated_by_package'))))
        arrays.update({name: value for name,value in zip(('x_um','y_um'),self.axes_um)})
        with Path(path).open('xb') as stream:
            np.savez_compressed(stream, **arrays)


def simulate(grid, refractive_index, initial_field, *, store_every=1):
    """Compute the complex envelope at every transverse point and saved z plane.

    refractive_index(z_um, sparse_coordinates) -> absolute real n (broadcastable).
    initial_field is a grid-shaped complex array or callable(sparse_coordinates).
    No input or step normalization; input amplitude and phase are preserved.
    Default saves every integration plane; store_every=N saves every Nth plus end.
    Grid.samples belongs to legacy reporting and is ignored by this API.
    """
    grid.validate()
    if not callable(refractive_index):
        raise ValueError('refractive_index must be callable')
    if type(store_every) is not int or store_every < 1:
        raise ValueError('store_every must be a positive integer')
    shape = tuple(grid.points)
    axis = axes(grid)
    q = tuple(np.meshgrid(*axis, indexing='ij', sparse=True))
    field = np.array(initial_field(q) if callable(initial_field) else initial_field, dtype=complex, copy=True)
    dv = math.prod(w/n for w,n in zip(grid.windows_um,grid.points))
    p0 = float(np.sum(abs(field)**2)*dv)
    if field.shape != shape or not np.all(np.isfinite(field)) or not math.isfinite(p0) or p0 <= 0:
        raise ValueError('initial_field must be finite nonzero and match grid.points')
    count = math.ceil(grid.length_um/grid.step_um)
    dz = grid.length_um/count
    selected = list(range(0,count+1,store_every))
    if selected[-1] != count:
        selected.append(count)
    if len(selected)*math.prod(shape) > 16000000:
        raise ValueError('stored fields exceed 16 million complex values; increase store_every')
    k0 = 2*np.pi/grid.wavelength_um
    beta = k0*grid.background_index
    freq = np.meshgrid(*(2*np.pi*np.fft.fftfreq(n,w/n) for w,n in zip(grid.windows_um,grid.points)), indexing='ij', sparse=True)
    kinetic = sum(k*k for k in freq)/(2*beta)
    # Triangle-norm upper bound for every allowed weak index, not launch spectrum.
    potential_bound = k0*grid.background_index*(1.01**2-1)/2
    rate_bound = float(np.max(kinetic))+potential_bound
    limit = 2.8/rate_bound
    if dz > limit:
        raise ValueError(f'RK4 step {dz:g} um exceeds conservative stability limit {limit:g} um; reduce step_um')

    def potential(z):
        n = np.asarray(refractive_index(z,q))
        if not np.isrealobj(n) or not np.all(np.isfinite(n)):
            raise ValueError('refractive_index must return finite real absolute n')
        try:
            n = np.broadcast_to(n,shape)
        except ValueError as error:
            raise ValueError('refractive_index shape is not broadcastable to grid.points') from error
        if np.any(n <= 0) or np.max(abs(n-grid.background_index)) > .01*grid.background_index:
            raise ValueError('absolute index requires n>0 and |n-n0|/n0 <= 0.01')
        return k0*(n*n-grid.background_index**2)/(2*grid.background_index)

    def rhs(psi,v):
        return -1j*np.fft.ifftn(kinetic*np.fft.fftn(psi))+1j*v*psi

    edge = np.logical_or.reduce(np.broadcast_arrays(*(abs(c) >= .4*w for c,w in zip(q,grid.windows_um))))
    high = np.logical_or.reduce(np.broadcast_arrays(*(abs(k) >= .8*np.pi*n/w for k,n,w in zip(freq,grid.points,grid.windows_um))))
    fields = np.empty((len(selected),*shape), dtype=complex)
    drift = edge_power = high_power = 0.
    saved = 0
    for i in range(count+1):
        if i:
            z = (i-1)*dz
            v0,vm,v1 = potential(z),potential(z+dz/2),potential(i*dz)
            k1 = rhs(field,v0)
            k2 = rhs(field+dz*k1/2,vm)
            k3 = rhs(field+dz*k2/2,vm)
            k4 = rhs(field+dz*k3,v1)
            field = field+dz*(k1+2*k2+2*k3+k4)/6
        if not np.all(np.isfinite(field)):
            raise FloatingPointError(f'nonfinite field at step {i}')
        power = abs(field)**2*dv
        drift = max(drift,abs(float(power.sum())/p0-1))
        edge_power = max(edge_power,float(power[edge].sum())/p0)
        spectrum = abs(np.fft.fftn(field))**2
        high_power = max(high_power,float(spectrum[high].sum()/spectrum.sum()))
        if saved < len(selected) and i == selected[saved]:
            fields[saved] = field
            saved += 1
    diagnostics = dict(method='classical_RK4', actual_step_um=dz, steps=count,
                       conservative_step_limit_um=limit, max_relative_power_drift=drift,
                       max_edge_power=edge_power, max_high_frequency_power=high_power,
                       input_power=p0, normalized=False)
    diagnostics['checks_passed'] = drift < 1e-8 and edge_power < 1e-4 and high_power < 1e-6
    return Result(grid,axis,np.asarray(selected)*dz,fields,diagnostics)


def check_convergence(grid, refractive_index, launch):
    """Rebuild analytic launch on half-step, half-spacing, and larger-window grids.

    Full complex relative L2 errors retain global phase. A sampled input array is
    deliberately not accepted: resampling requires a physical interpolation rule.
    """
    if not callable(launch):
        raise ValueError('convergence requires a physical-coordinate launch callable')
    if any(n % 8 or n > 512 for n in grid.points):
        raise ValueError('convergence requires points divisible by 8 and <=512')
    runs = [simulate(g,refractive_index,launch,store_every=100001) for g in refinement_grids(grid)]
    base = runs[0].field[-1]
    others = [runs[1].field[-1], runs[2].field[-1][tuple(slice(None,None,2) for _ in grid.points)],
              runs[3].field[-1][tuple(slice(n//4,n//4+n) for n in grid.points)]]
    norm = np.linalg.norm(base)
    checks = {name: float(np.linalg.norm(f-base)/norm) for name,f in zip(
        ('half_step_field_l2','half_grid_field_l2','larger_window_field_l2'),others)}
    checks['runs'] = [r.diagnostics for r in runs]
    checks['passed'] = all(checks[k] < .002 for k in ('half_step_field_l2','half_grid_field_l2','larger_window_field_l2')) and all(r.diagnostics['checks_passed'] for r in runs)
    return checks
