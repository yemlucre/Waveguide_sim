"""Passive staggered lantern study. x/y in um, z in mm; no active phase.

Isolated 2D scalar modes -> two-mode Galerkin coupling -> finite CMT network.
This approximation omits bend radiation, nonorthogonal many-body corrections,
polarization and fabrication disorder. It is not full-chip spatial BPM.
"""
from dataclasses import dataclass, replace
import math
import numpy as np
from bpm import Grid, axes, propagate as spatial_propagate

MODEL_VERSION='passive-staggered-lantern-1'
_NODES,_WEIGHTS=np.polynomial.legendre.leggauss(4)


@dataclass(frozen=True)
class Material:
    wavelength_um: float=.8
    background_index: float=1.45
    radius_um: float=3.
    delta_index: float=.003

    def validate(self):
        for v in (self.wavelength_um,self.background_index,self.radius_um,self.delta_index):
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not np.isfinite(v) or v<=0: raise ValueError('material values must be finite positive numbers')
        if self.delta_index/self.background_index>.005: raise ValueError('two-guide sum requires 2*dn/n0 <=.01')
        return self


def potential(m,dn):
    return -(2*np.pi/m.wavelength_um)*((m.background_index+dn)**2-m.background_index**2)/(2*m.background_index)


def isolated_mode(m,points=256,window_um=128.,imaginary_step_um=2.,iterations=4000):
    """Imaginary-time projection, normalized during eigensolve only, not propagation."""
    m.validate()
    g=Grid(wavelength_um=m.wavelength_um,background_index=m.background_index,windows_um=(window_um,window_um),points=(points,points),length_um=1.,samples=2)
    x,y=np.meshgrid(*axes(g),indexing='ij',sparse=True); dx=window_um/points
    if m.radius_um/dx<4: raise ValueError('mode index radius needs at least four grid cells')
    dn=m.delta_index*np.exp(-(x*x+y*y)/m.radius_um**2); v=potential(m,dn)
    k0=2*np.pi/m.wavelength_um; k=2*np.pi*np.fft.fftfreq(points,dx)
    kinetic=(k[:,None]**2+k[None,:]**2)/(2*k0*m.background_index)
    u=np.broadcast_to(np.exp(-(x*x+y*y)/(2*m.radius_um)**2),g.points).copy()
    u/=np.sqrt(np.sum(u*u)*dx*dx)
    half=np.exp(-.5*imaginary_step_um*v); diffraction=np.exp(-imaginary_step_um*kinetic)
    for _ in range(iterations):
        u=(half*np.fft.ifftn(diffraction*np.fft.fftn(half*u))).real
        u/=np.sqrt(np.sum(u*u)*dx*dx)
    hu=np.fft.ifftn(kinetic*np.fft.fftn(u)).real+v*u
    energy=float(np.sum(u*hu)*dx*dx)
    residual=float(np.sqrt(np.sum((hu-energy*u)**2)*dx*dx))
    edge=(abs(x)>=.4*window_um)|(abs(y)>=.4*window_um)
    return dict(grid=g,mode=u,energy_per_um=energy,residual_per_um=residual,
                edge_power=float(np.sum(u[edge]**2)*dx*dx),rms_radius_um=float(np.sqrt(np.sum(u*u*(x*x+y*y))*dx*dx)))


def pair_coupling(m,mode,separation_um):
    """Symmetric generalized 2x2 Galerkin eigenvalue splitting; C in 1/mm."""
    g=mode['grid']; n=g.points[0]; dx=g.windows_um[0]/n
    x,y=np.meshgrid(*axes(g),indexing='ij',sparse=True)
    k=2*np.pi*np.fft.fftfreq(n,dx)[:,None]
    f=np.fft.fftn(mode['mode'])
    left=np.fft.ifftn(f*np.exp(1j*k*separation_um/2)).real
    right=np.fft.ifftn(f*np.exp(-1j*k*separation_um/2)).real
    a=m.delta_index*np.exp(-((x+separation_um/2)**2+y*y)/m.radius_um**2)
    b=m.delta_index*np.exp(-((x-separation_um/2)**2+y*y)/m.radius_um**2)
    v=potential(m,a+b); va=potential(m,a); vb=potential(m,b)
    s=float(np.sum(left*right)*dx*dx)
    h00=mode['energy_per_um']+float(np.sum(left*left*(v-va))*dx*dx)
    h01=mode['energy_per_um']*s+float(np.sum(left*right*(v-vb))*dx*dx)
    if not 0<=s<.8: raise ValueError('isolated-mode basis overlaps too strongly or wraps')
    c=(h00*s-h01)/(1-s*s)*1000
    return dict(coupling_per_mm=float(max(c,0)),overlap=s)


def coupling_table(m,mode,spacing_um=.5):
    distances=np.arange(10.,60.0001,spacing_um)
    values=np.array([pair_coupling(m,mode,d)['coupling_per_mm'] for d in distances])
    return dict(distances_um=distances,coupling_per_mm=values,
                cutoff_um=60.,cutoff_coupling_per_mm=float(values[-1]))


@dataclass(frozen=True)
class Geometry:
    pitch_um: float=15.
    rows: int=8
    columns: int=8
    expanded_pitch_um: float=700.
    start_mm: float=5.
    stagger_mm: float=9.5
    rise_mm: float=9.
    hold_mm: float=.5
    fall_mm: float=9.
    length_mm: float=100.
    step_mm: float=.02
    samples: int=501

    def validate(self):
        for key,v in self.__dict__.items():
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v<=0: raise ValueError(key+' must be finite positive')
        if type(self.rows) is not int or type(self.columns) is not int or not 1<=self.rows<=8 or not 1<=self.columns<=8: raise ValueError('rows/columns must be 1..8 integers')
        if not 10<=self.pitch_um<=25 or self.expanded_pitch_um<self.pitch_um: raise ValueError('pitch must be 10..25 um and expanded >= pitch')
        if self.start_mm+(self.rows-1)*self.stagger_mm+self.rise_mm+self.hold_mm+self.fall_mm>self.length_mm: raise ValueError('fanouts exceed length')
        if self.length_mm/self.step_mm>100000 or self.step_mm>.1: raise ValueError('step <=.1mm, maximum 100000 steps')
        if type(self.samples) is not int or not 2<=self.samples<=1001: raise ValueError('samples must be integer 2..1001')
        return self


def positions(p,z,velocity=False):
    if not 0<=z<=p.length_mm: raise ValueError('z outside structure')
    row=np.repeat(np.arange(p.rows),p.columns); col=np.tile(np.arange(p.columns)-(p.columns-1)/2,p.rows)
    u=z-(p.start_mm+row*p.stagger_mm); w=np.zeros(len(row)); derivative=np.zeros(len(row))
    rise=(u>=0)&(u<p.rise_mm); hold=(u>=p.rise_mm)&(u<=p.rise_mm+p.hold_mm)
    fall=(u>p.rise_mm+p.hold_mm)&(u<=p.rise_mm+p.hold_mm+p.fall_mm)
    t=u[rise]/p.rise_mm; w[rise]=(1-np.cos(np.pi*t))/2; derivative[rise]=np.pi*np.sin(np.pi*t)/(2*p.rise_mm)
    w[hold]=1
    t=(u[fall]-p.rise_mm-p.hold_mm)/p.fall_mm; w[fall]=(1+np.cos(np.pi*t))/2; derivative[fall]=-np.pi*np.sin(np.pi*t)/(2*p.fall_mm)
    pitch=p.pitch_um+(p.expanded_pitch_um-p.pitch_um)*w
    xy=np.column_stack((col*pitch,(row-(p.rows-1)/2)*p.pitch_um))
    if velocity: return np.column_stack((col*(p.expanded_pitch_um-p.pitch_um)*derivative,np.zeros(len(row))))
    return xy


def coupling_matrix(p,table,z):
    xy=positions(p,z); d=np.linalg.norm(xy[:,None]-xy[None,:],axis=-1)
    # Adjacent layer fanout crossings may make d < pitch; clamp is forbidden.
    off=~np.eye(len(xy),dtype=bool)
    if np.any(d[off]<table['distances_um'][0]-1e-9): raise ValueError('geometry gives separations below coupling table')
    c=np.exp(np.interp(d,table['distances_um'],np.log(np.maximum(table['coupling_per_mm'],1e-300))))
    c[d>table['distances_um'][-1]]=0
    np.fill_diagonal(c,0)
    return -c


def arc_excess(p,a,b):
    # Gauss-Legendre quadrature; uses actual tangent lengths, not active phase tuning.
    nodes,weights=_NODES,_WEIGHTS
    speeds=np.array([positions(p,(a+b)/2+(b-a)*t/2,velocity=True)[:,0]/1000 for t in nodes])
    # sqrt(1+v^2)-1 written stably near zero.
    extra=speeds**2/(np.sqrt(1+speeds**2)+1)
    return (b-a)/2*np.sum(weights[:,None]*extra,axis=0)*1000  # um


def modal_propagate(p,table,beta_per_um,input_channel=27):
    p.validate(); n=p.rows*p.columns
    if type(input_channel) is not int or not 0<=input_channel<n: raise ValueError('invalid launch channel')
    breaks=[0.,p.length_mm]
    for r in range(p.rows):
        s=p.start_mm+r*p.stagger_mm
        breaks.extend([s,s+p.rise_mm,s+p.rise_mm+p.hold_mm,s+p.rise_mm+p.hold_mm+p.fall_mm])
    z=[0.]
    for a,b in zip(sorted(set(breaks))[:-1],sorted(set(breaks))[1:]):
        z.extend(np.linspace(a,b,max(1,math.ceil((b-a)/p.step_mm))+1)[1:])
    z=np.array(z); selected=set(np.linspace(0,len(z)-1,min(p.samples,len(z)),dtype=int))
    f=np.zeros(n,complex); f[input_channel]=1
    samples=[]; zs=[]; max_drift=0.; max_slope=0.
    for i,zz in enumerate(z):
        if i:
            a=z[i-1]; b=zz; mid=(a+b)/2
            d1=np.exp(1j*beta_per_um*arc_excess(p,a,mid)); d2=np.exp(1j*beta_per_um*arc_excess(p,mid,b))
            h=coupling_matrix(p,table,mid); values,modes=np.linalg.eigh(h)
            f=d2*(modes@(np.exp(-1j*values*(b-a))*(modes.T.conj()@(d1*f))))
            max_drift=max(max_drift,abs(float(np.vdot(f,f).real)-1))
            max_slope=max(max_slope,float(np.max(abs(positions(p,mid,True)[:,0]/1000))))
        if i in selected: samples.append(f.copy()); zs.append(zz)
    fields=np.array(samples); power=abs(fields)**2
    entropy=-np.sum(np.where(power>0,power*np.log(np.maximum(power,1e-300)),0),axis=1)
    return dict(z_mm=np.array(zs),fields=fields,power=power,effective_channels=np.exp(entropy),
                participation=1/np.sum(power**2,axis=1),max_power_drift=max_drift,max_path_slope=max_slope,
                positions_um=np.array([positions(p,t) for t in zs]))


def local_pair_check(m,mode,pitch_um,length_um=1000.,step_um=2.):
    """Continuous 2+1D BPM vs two-mode prediction on a straight two-guide cell."""
    g=replace(mode['grid'],length_um=length_um,step_um=step_um,samples=21)
    x,y=np.meshgrid(*axes(g),indexing='ij',sparse=True); dx=g.windows_um[0]/g.points[0]
    k=2*np.pi*np.fft.fftfreq(g.points[0],dx)[:,None]
    f=np.fft.fftn(mode['mode'])
    left=np.fft.ifftn(f*np.exp(1j*k*pitch_um/2))
    right=np.fft.ifftn(f*np.exp(-1j*k*pitch_um/2))
    overlap=np.vdot(left,right)*dx*dx
    # Symmetric Loewdin orthonormalization of isolated guide fields.
    s=np.array([[1,overlap],[overlap.conjugate(),1]],complex)
    e,v=np.linalg.eigh(s); basis=np.stack((left,right),axis=-1)@(v@np.diag(e**-.5)@v.T.conj())
    dn=m.delta_index*(np.exp(-((x+pitch_um/2)**2+y*y)/m.radius_um**2)+np.exp(-((x-pitch_um/2)**2+y*y)/m.radius_um**2))
    r=spatial_propagate(g,[],basis[...,0],index_fn=lambda z,q:dn)
    projected=np.einsum('xyk,sxy->sk',basis.conj(),r['fields'])*dx*dx
    c=pair_coupling(m,mode,pitch_um)['coupling_per_mm']
    prediction=np.sin(c*r['z_um']/1000)**2
    return dict(run=r,right_projected_power=abs(projected[:,1])**2,
                projection_total=np.sum(abs(projected)**2,axis=1),cmt_right_power=prediction,
                max_power_difference=float(np.max(abs(abs(projected[:,1])**2-prediction))))
