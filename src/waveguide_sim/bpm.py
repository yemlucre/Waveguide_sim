"""Dimension-independent scalar paraxial BPM. Lengths in um, no UI/device I/O.

i d_z psi = [-laplacian/(2*k0*n0) - k0*(n**2-n0**2)/(2*n0)] psi.
Real index, midpoint Strang splitting, periodic transverse boundaries.
"""
from dataclasses import dataclass, replace
import math
import numpy as np

MODEL_VERSION = 'general-paraxial-1'


def finite(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f'{name} must be finite' + (' and positive' if positive else ''))


@dataclass(frozen=True)
class Grid:
    wavelength_um: float = 0.78
    background_index: float = 1.45
    windows_um: tuple = (64., 64.)
    points: tuple = (128, 128)
    length_um: float = 500.
    step_um: float = 2.
    samples: int = 51

    def validate(self):
        for name in ('wavelength_um', 'background_index', 'length_um', 'step_um'):
            finite(getattr(self, name), name, True)
        if len(self.points) not in (1, 2) or len(self.windows_um) != len(self.points):
            raise ValueError('one or two transverse axes required')
        for n, w in zip(self.points, self.windows_um):
            if type(n) is not int or not 32 <= n <= 1024 or n % 4:
                raise ValueError('points per axis must be multiples of 4 in [32,1024]')
            finite(w, 'window_um', True)
        if type(self.samples) is not int or not 2 <= self.samples <= 401:
            raise ValueError('samples must be integer in [2,401]')
        if math.ceil(self.length_um/self.step_um) > 100000:
            raise ValueError('maximum 100000 steps')
        if math.prod(self.points)*min(self.samples, math.ceil(self.length_um/self.step_um)+1) > 16000000:
            raise ValueError('sample storage exceeds 16 million complex values')
        return self


def axes(g):
    g.validate()
    return tuple((np.arange(n)-n//2)*w/n for n, w in zip(g.points, g.windows_um))


def guide_at(guide, z):
    """Smoothstep segment interpolation, zero slope at every knot."""
    knots = guide['knots']
    zs = [k['z_um'] for k in knots]
    j = min(max(int(np.searchsorted(zs, z, side='right'))-1, 0), len(knots)-2)
    a, b = knots[j:j+2]
    t = np.clip((z-a['z_um'])/(b['z_um']-a['z_um']), 0, 1)
    s = t*t*(3-2*t)
    return tuple((1-s)*np.asarray(a[key])+s*np.asarray(b[key]) for key in ('center_um','radii_um','delta_index'))


def validate_guides(g, guides):
    g.validate()
    if not isinstance(guides, list) or len(guides) > 64:
        raise ValueError('guides must be a list of at most 64 Gaussian guides')
    upper_dn = 0.
    for guide in guides:
        if set(guide) != {'knots'} or not 2 <= len(guide['knots']) <= 100:
            raise ValueError('guide requires 2..100 knots only')
        knots = guide['knots']
        if knots[0]['z_um'] != 0 or knots[-1]['z_um'] != g.length_um:
            raise ValueError('knots must span exactly [0,length_um]')
        for k in knots:
            if set(k) != {'z_um','center_um','radii_um','delta_index'}:
                raise ValueError('unknown or missing knot keys')
            finite(k['z_um'], 'z_um')
            finite(k['delta_index'], 'delta_index')
            if k['delta_index'] < 0:
                raise ValueError('Gaussian guide index increment must be nonnegative')
            if len(k['center_um']) != len(g.points) or len(k['radii_um']) != len(g.points):
                raise ValueError('guide dimension mismatch')
            for c, r, w, n in zip(k['center_um'], k['radii_um'], g.windows_um, g.points):
                finite(c, 'center'); finite(r, 'radius', True)
                if r < 4*w/n or abs(c)+4*r >= w/2:
                    raise ValueError('guide needs >=4 cells per radius and four-radius boundary margin')
        upper_dn += max(k['delta_index'] for k in knots)
        for a,b in zip(knots[:-1],knots[1:]):
            dz=b['z_um']-a['z_um']
            if dz <= 0:
                raise ValueError('knot z must increase strictly')
            # Smoothstep maximum derivative is 1.5. A conservative paraxial geometry guard.
            if 1.5*np.linalg.norm(np.subtract(b['center_um'],a['center_um']))/dz > 0.1:
                raise ValueError('guide path slope exceeds 0.1')
            if 1.5*np.max(abs(np.subtract(b['radii_um'],a['radii_um'])))/dz > 0.1:
                raise ValueError('guide taper slope exceeds 0.1')
    if upper_dn/g.background_index > 0.01:
        raise ValueError('sum of maximum guide increments / n0 must be <=0.01')


def index_profile(g, guides, z, coordinates=None):
    coords = np.meshgrid(*axes(g), indexing='ij', sparse=True) if coordinates is None else coordinates
    dn = np.zeros(g.points)
    for guide in guides:
        c, r, amplitude = guide_at(guide,z)
        dn += amplitude*np.exp(-sum(((q-ci)/ri)**2 for q,ci,ri in zip(coords,c,r)))
    return dn


def gaussian_input(g, center_um, waists_um, tilt_rad=None):
    """Amplitude exp(-sum((q-c)/w)^2); w is 1/e field (1/e^2 intensity)."""
    tilt_rad = [0.]*len(g.points) if tilt_rad is None else tilt_rad
    if any(len(v) != len(g.points) for v in (center_um,waists_um,tilt_rad)):
        raise ValueError('input dimension mismatch')
    for c,w,t,window,n in zip(center_um,waists_um,tilt_rad,g.windows_um,g.points):
        finite(c,'input center'); finite(w,'input waist',True); finite(t,'tilt')
        if w < 4*window/n or abs(c)+4*w >= window/2:
            raise ValueError('input requires four cells per waist and four-waist margin')
    if np.linalg.norm(tilt_rad) > 0.1:
        raise ValueError('input tilt magnitude must be <=0.1 rad')
    coords=np.meshgrid(*axes(g),indexing='ij',sparse=True)
    k=2*np.pi*g.background_index/g.wavelength_um
    return np.exp(-sum(((q-c)/w)**2 for q,c,w in zip(coords,center_um,waists_um))
                  +1j*k*sum(q*t for q,t in zip(coords,tilt_rad)))


def propagate(g, guides, initial, index_fn=None):
    """Custom real dn callback: index_fn(z_um, sparse_coordinates).

    Custom field is normalized once; no normalization during evolution.
    Shape order (x,) or (x,y). No absorber: edge contamination causes failure.
    """
    validate_guides(g,guides)
    coords=np.meshgrid(*axes(g),indexing='ij',sparse=True)
    field=np.array(initial,dtype=complex,copy=True)
    dv=math.prod(w/n for w,n in zip(g.windows_um,g.points))
    if field.shape != tuple(g.points) or not np.all(np.isfinite(field)):
        raise ValueError('initial must be finite complex field with grid shape')
    norm=float(np.sum(abs(field)**2)*dv)
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError('input power must be finite and nonzero')
    field/=math.sqrt(norm)
    freq=np.meshgrid(*(2*np.pi*np.fft.fftfreq(n,w/n) for w,n in zip(g.windows_um,g.points)),indexing='ij',sparse=True)
    count=math.ceil(g.length_um/g.step_um); dz=g.length_um/count
    diffraction=np.exp(-1j*dz*sum(k*k for k in freq)/(2*(2*np.pi/g.wavelength_um)*g.background_index))
    selected=set(np.linspace(0,count,min(count+1,g.samples),dtype=int))
    edge=np.broadcast_to(np.logical_or.reduce(np.broadcast_arrays(*(abs(q)>=0.4*w for q,w in zip(coords,g.windows_um)))),g.points)
    high_k=np.logical_or.reduce(np.broadcast_arrays(*(abs(k)>=0.8*np.pi*n/w for k,n,w in zip(freq,g.points,g.windows_um))))
    max_drift=max_edge=max_high=0.
    fields=[]; zs=[]; moments=[]
    for i in range(count+1):
        if i:
            zmid=(i-0.5)*dz
            dn=np.asarray(index_profile(g,guides,zmid,coords) if index_fn is None else index_fn(zmid,coords))
            if dn.shape != tuple(g.points) or not np.isrealobj(dn) or not np.all(np.isfinite(dn)) or np.max(abs(dn)) > 0.01*g.background_index:
                raise ValueError('index callback must return finite real weak dn with grid shape')
            v=-(2*np.pi/g.wavelength_um)*((g.background_index+dn)**2-g.background_index**2)/(2*g.background_index)
            half=np.exp(-0.5j*dz*v)
            field=half*np.fft.ifftn(diffraction*np.fft.fftn(half*field))
        power=abs(field)**2*dv
        max_drift=max(max_drift,abs(float(power.sum())-1))
        max_edge=max(max_edge,float(power[edge].sum()))
        spectrum=abs(np.fft.fftn(field))**2
        max_high=max(max_high,float(spectrum[high_k].sum()/spectrum.sum()))
        if i in selected:
            fields.append(field.copy()); zs.append(i*dz)
            moments.append([float((power*q).sum()) for q in coords])
    return dict(axes_um=axes(g),z_um=np.array(zs),fields=np.array(fields),centroid_um=np.array(moments),
                max_power_drift=max_drift,max_edge_power=max_edge,max_high_frequency_power=max_high,actual_step_um=dz,
                input_power_before_normalization=norm)


def refinement_grids(g):
    """Fixed convergence protocol, shared by built-in and Python-defined scenes."""
    return [replace(g,samples=2),replace(g,step_um=g.step_um/2,samples=2),
            replace(g,points=tuple(2*n for n in g.points),samples=2),
            replace(g,points=tuple(3*n//2 for n in g.points),windows_um=tuple(1.5*w for w in g.windows_um),samples=2)]


def verify(g, guides, launch, index_factory=None):
    """Full complex endpoint L2 comparisons; same analytic launch on every grid."""
    gs=refinement_grids(g)
    for h in gs: validate_guides(h,guides)
    runs=[propagate(h,guides,launch(h),index_fn=None if index_factory is None else index_factory(h)) for h in gs]
    base=runs[0]['fields'][-1]
    comparable=[runs[1]['fields'][-1],runs[2]['fields'][-1][tuple(slice(None,None,2) for _ in g.points)],
                runs[3]['fields'][-1][tuple(slice(n//4,n//4+n) for n in g.points)]]
    dv=math.prod(w/n for w,n in zip(g.windows_um,g.points))
    errors={key:float(np.sqrt(np.sum(abs(f-base)**2)*dv)) for key,f in zip(('half_step_field_l2','half_grid_field_l2','larger_window_field_l2'),comparable)}
    errors.update(max_power_drift=max(r['max_power_drift'] for r in runs),
                  max_edge_power=max(r['max_edge_power'] for r in runs),
                  max_high_frequency_power=max(r['max_high_frequency_power'] for r in runs))
    errors['passed']=all(errors[k]<0.002 for k in ('half_step_field_l2','half_grid_field_l2','larger_window_field_l2')) and errors['max_power_drift']<1e-8 and errors['max_edge_power']<1e-4 and errors['max_high_frequency_power']<1e-6
    return errors
