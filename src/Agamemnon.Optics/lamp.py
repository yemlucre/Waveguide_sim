"""LAMP-inspired 9-channel modal model and programmable 3x3 correlation.

Not a reproduction of the fabricated 64-channel chip, not a spatial BPM solver.
z in mm; transverse centres and distances in um; C in 1/mm; phases in rad.
"""
from dataclasses import asdict,dataclass
import math
import numpy as np

MODEL_VERSION='lamp9-cmt-correlation-1'


@dataclass(frozen=True)
class LampParameters:
    wavelength_nm: float=800.0  # paper's signal wavelength, for provenance only
    pitch_um: float=15.0
    expanded_pitch_um: float=700.0
    length_mm: float=90.0
    step_mm: float=0.1
    rise_mm: float=10.0
    hold_mm: float=4.0
    starts_mm: tuple=(5.0,33.0,61.0)
    coupling_prefactor_per_mm: float=6.1688
    coupling_decay_per_um: float=0.2641

    def validate(self):
        for key,value in asdict(self).items():
            if key=='starts_mm':continue
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                raise ValueError(key+' must be finite and positive')
        if self.wavelength_nm!=800:
            raise ValueError('Empirical C(d) is used only at its paper-context 800 nm; no dispersion model')
        if not 10<=self.pitch_um<=17 or self.expanded_pitch_um<self.pitch_um:
            raise ValueError('tight pitch must be 10..17 um; expanded pitch must not be smaller')
        if self.length_mm/self.step_mm>20000 or self.step_mm>0.25:
            raise ValueError('maximum 20000 steps; step_mm <= .25')
        if len(self.starts_mm)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in self.starts_mm):
            raise ValueError('exactly three finite nonnegative stage starts are required')
        end=0
        for start in self.starts_mm:
            if start<end:raise ValueError('stages must be ordered and nonoverlapping')
            end=start+2*self.rise_mm+self.hold_mm
        if end>self.length_mm:raise ValueError('all stages must fit inside the propagation interval')
        return self


def centres(p,z):
    """Assumed radial fanout/fanin, from the pre-existing concept-9 demo."""
    if not np.isfinite(z) or not 0<=z<=p.length_mm:raise ValueError('z outside geometry')
    h=lambda t:10*t**3-15*t**4+6*t**5
    envelope=0.
    for start in p.starts_mm:
        u=z-start
        if 0<=u<p.rise_mm:envelope=h(u/p.rise_mm)
        elif p.rise_mm<=u<=p.rise_mm+p.hold_mm:envelope=1.
        elif p.rise_mm+p.hold_mm<u<=2*p.rise_mm+p.hold_mm:envelope=1-h((u-p.rise_mm-p.hold_mm)/p.rise_mm)
    pitch=p.pitch_um+(p.expanded_pitch_um-p.pitch_um)*envelope
    return np.array([[(c-1)*pitch,(r-1)*pitch] for r in range(3) for c in range(3)])


def hamiltonian(p,z):
    xy=centres(p,z)
    distances=np.linalg.norm(xy[:,None]-xy[None,:],axis=-1)
    coupling=p.coupling_prefactor_per_mm*np.exp(-p.coupling_decay_per_um*distances)
    np.fill_diagonal(coupling,0)
    # i da/dz = H a; negative coupling is the chosen phase convention.
    return -coupling


def step_operator(h,dz):
    if h.ndim!=2 or h.shape[0]!=h.shape[1] or not np.all(np.isfinite(h)) or not np.allclose(h,h.T.conj(),atol=1e-12):
        raise ValueError('H must be finite and Hermitian')
    if not math.isfinite(dz):raise ValueError('dz must be finite')
    values,modes=np.linalg.eigh(h)
    return (modes*np.exp(-1j*values*dz))@modes.T.conj()


def build_network(p):
    p.validate()
    screens=[s+p.rise_mm+p.hold_mm/2 for s in p.starts_mm]
    z=np.unique(np.round(np.r_[np.linspace(0,p.length_mm,math.ceil(p.length_mm/p.step_mm)+1),screens],12))
    operations=[]
    mixers=[]
    matrix=np.eye(9,dtype=complex)
    for a,b in zip(z[:-1],z[1:]):
        op=step_operator(hamiltonian(p,(a+b)/2),b-a)
        matrix=op@matrix
        operations.append((float(b),op,None))
        for i,screen in enumerate(screens):
            if abs(b-screen)<1e-10:
                mixers.append(matrix);matrix=np.eye(9,dtype=complex)
                operations.append((float(b),None,i))
    mixers.append(matrix)
    return dict(parameters=p,mixers=np.array(mixers),operations=operations,phase_z_mm=screens)


def transfer(mixers,phases):
    phases=np.asarray(phases,dtype=float)
    if phases.shape!=(len(mixers)-1,9) or not np.all(np.isfinite(phases)):
        raise ValueError('phase shape must be (3,9) with finite radians')
    matrix=mixers[0].copy()
    for i,phase in enumerate(phases):matrix=mixers[i+1]@(np.exp(1j*phase)[:,None]*matrix)
    return matrix


def row_loss_gradient(mixers,phases,target,output_channel=4):
    """Analytic gradient of ||U[out,:]-target||^2, not experimental SPSA."""
    prefixes=[]
    matrix=mixers[0].copy()
    for i,phase in enumerate(phases):
        prefixes.append(matrix)
        matrix=mixers[i+1]@(np.exp(1j*phase)[:,None]*matrix)
    residual=matrix[output_channel]-target
    gradient=np.empty_like(phases)
    suffix=mixers[-1].copy()
    for i in range(len(phases)-1,-1,-1):
        derivatives=(1j*suffix[output_channel]*np.exp(1j*phases[i]))[:,None]*prefixes[i]
        gradient[i]=2*np.real(derivatives@residual.conj())
        suffix=(suffix*np.exp(1j*phases[i])[None,:])@mixers[i]
    return float(np.vdot(residual,residual).real),gradient


def train_kernel(mixers,kernel,seed=20261030,epochs=2400,restarts=3):
    kernel=np.asarray(kernel,dtype=float)
    if kernel.shape!=(3,3) or not np.all(np.isfinite(kernel)) or np.linalg.norm(kernel)==0:
        raise ValueError('kernel must be finite nonzero 3x3')
    if not isinstance(epochs,int) or not 1<=epochs<=10000 or not isinstance(restarts,int) or not 1<=restarts<=8:
        raise ValueError('epochs 1..10000, restarts 1..8 required')
    target=kernel.ravel()/np.linalg.norm(kernel)
    rng=np.random.default_rng(seed)
    best=None
    for restart in range(restarts):
        phases=rng.uniform(-np.pi,np.pi,(3,9));m=np.zeros_like(phases);v=np.zeros_like(phases)
        history=[]
        for epoch in range(1,epochs+1):
            loss,g=row_loss_gradient(mixers,phases,target)
            if epoch==1 or epoch%10==0:history.append([epoch,loss])
            if best is None or loss<best['loss']:
                best=dict(loss=loss,phases=phases.copy(),history=history.copy(),restart=restart,epoch=epoch)
            if loss<1e-12:break
            m=.9*m+.1*g;v=.999*v+.001*g*g
            phases-=.025*(m/(1-.9**epoch))/(np.sqrt(v/(1-.999**epoch))+1e-8)
        if best['loss']<1e-10:break
    best['matrix']=transfer(mixers,best['phases'])
    best['kernel']=kernel
    best['learned_kernel']=best['matrix'][4].reshape(3,3)*np.linalg.norm(kernel)
    best['row_l2_error']=math.sqrt(best['loss'])
    return best


def patches(image):
    image=np.asarray(image,dtype=float)
    if image.ndim!=2 or min(image.shape)<3 or max(image.shape)>256 or not np.all(np.isfinite(image)):
        raise ValueError('image must be finite 2D, each dimension 3..256')
    windows=np.lib.stride_tricks.sliding_window_view(image,(3,3))
    return windows.reshape(-1,9).T,(image.shape[0]-2,image.shape[1]-2)


def evaluate_image(image,kernel,matrix):
    """Amplitude encoding, no per-patch normalization; valid DL correlation.

    Signed field requires a phase-referenced coherent detector (assumed).
    CCD-like intensity is |a_out|^2 and cannot retain sign.
    """
    windows,shape=patches(image)
    kernel=np.asarray(kernel,dtype=float)
    matrix=np.asarray(matrix,dtype=complex)
    if kernel.shape!=(3,3) or not np.all(np.isfinite(kernel)) or np.linalg.norm(kernel)==0 or matrix.shape!=(9,9) or not np.all(np.isfinite(matrix)):
        raise ValueError('finite nonzero 3x3 kernel and finite 9x9 transfer required')
    norm=np.linalg.norm(kernel)
    target=(kernel.ravel()@windows).reshape(shape)
    raw=(matrix@windows)[4].reshape(shape)
    field=norm*raw
    error=np.linalg.norm(field-target)/max(np.linalg.norm(target),1e-12)
    return dict(reference=target,field=field,intensity=abs(raw)**2,
                intensity_rescaled=norm**2*abs(raw)**2,
                complex_relative_error=float(error),imaginary_rms=float(np.sqrt(np.mean(field.imag**2))))


def snapshot_transfers(network,phases,max_snapshots=125):
    matrix=np.eye(9,dtype=complex);zs=[0.];matrices=[matrix.copy()]
    stride=max(1,len(network['operations'])//max_snapshots)
    for i,(z,op,screen) in enumerate(network['operations']):
        if screen is None:matrix=op@matrix
        else:matrix=np.exp(1j*phases[screen])[:,None]*matrix
        if i%stride==0 or screen is not None or i==len(network['operations'])-1:
            zs.append(z);matrices.append(matrix.copy())
    return np.array(zs),np.array(matrices)
