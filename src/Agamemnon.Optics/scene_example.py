"""Edit PARAMETERS for routine studies; edit the two functions for a new model.

All physical values are assumed_not_measured. All lengths in um.
This is an executable trusted Python scene, not a measured device description.
"""
import numpy as np
from bpm import Grid, finite
from python_scene import Scene

API_VERSION = 1
DESCRIPTION = 'Assumed moving super-Gaussian guides and coherent complex two-spot input'
PARAMETERS = dict(
    dimensions=2, wavelength_um=.78, background_index=1.45,
    window_um=128., points=256, length_um=200., step_um=1., samples=31,
    gap_um=10., radius_um=4., delta_index=.003, bend_um=1.,
    waist_um=3., relative_amplitude=.25, relative_phase_rad=1.2,
)
SCAN = None  # e.g. dict(parameter='gap_um', values=[8.,10.,12.])
OBJECTIVE = 'target_overlap'


def refractive_index(g,z,q,p):
    """Absolute n(x[,y],z). Replace this expression for any weak real profile."""
    t=z/g.length_um; shift=p['bend_um']*t*t*(3-2*t)
    x=q[0]; c=-p['gap_um']/2+shift
    radial_y=0 if len(q)==1 else (q[1]/p['radius_um'])**4
    left=np.exp(-((x-c)/p['radius_um'])**4-radial_y)
    right=np.exp(-((x-p['gap_um']/2)/p['radius_um'])**4-radial_y)
    return g.background_index+p['delta_index']*(left+right)


def initial_field(g,q,p):
    """Complex amplitude with coherent amplitude and phase control."""
    x=q[0]; other=0 if len(q)==1 else (q[1]/p['waist_um'])**2
    left=np.exp(-((x+p['gap_um']/2)/p['waist_um'])**2-other)
    right=np.exp(-((x-p['gap_um']/2)/p['waist_um'])**2-other)
    return left+p['relative_amplitude']*np.exp(1j*p['relative_phase_rad'])*right


def target_field(g,q,p):
    """An assumed output Gaussian template, NOT a solved guide eigenmode."""
    other=0 if len(q)==1 else (q[1]/p['waist_um'])**2
    return np.exp(-((q[0]-p['gap_um']/2)/p['waist_um'])**2-other)


def build(parameters):
    p=dict(parameters)
    for key,value in p.items(): finite(value,key)
    if type(p['dimensions']) is not int or p['dimensions'] not in (1,2): raise ValueError('dimensions must be 1 or 2')
    for key in ('gap_um','radius_um','waist_um'): finite(p[key],key,True)
    finite(p['length_um'],'length_um',True)
    if p['delta_index']<0 or 2*p['delta_index']>0.01*p['background_index']: raise ValueError('weak nonnegative guide increment required')
    if p['relative_amplitude']<0: raise ValueError('relative_amplitude must be nonnegative')
    if 1.5*abs(p['bend_um'])/p['length_um']>.1: raise ValueError('bend slope exceeds 0.1')
    dim=p['dimensions']
    g=Grid(wavelength_um=p['wavelength_um'],background_index=p['background_index'],
           windows_um=(p['window_um'],)*dim,points=(p['points'],)*dim,
           length_um=p['length_um'],step_um=p['step_um'],samples=p['samples']).validate()
    if min(p['radius_um'],p['waist_um'])<4*p['window_um']/p['points']: raise ValueError('resolve radius/waist with >=4 cells')
    if p['gap_um']/2+abs(p['bend_um'])+4*max(p['radius_um'],p['waist_um'])>=p['window_um']/2: raise ValueError('insufficient boundary margin')
    roi=[[0.,p['gap_um']/2+2*p['radius_um']]]+([[-2*p['radius_um'],2*p['radius_um']]] if dim==2 else [])
    return Scene(g,lambda h,q:initial_field(h,q,p),lambda h,z,q:refractive_index(h,z,q,p),
                 roi_um=roi,target_field=lambda h,q:target_field(h,q,p),description=DESCRIPTION)
