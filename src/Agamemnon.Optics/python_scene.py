"""Version 1 trusted Python scene protocol. No device or UI dependencies.

refractive_index(grid, z_um, sparse_coordinates) returns ABSOLUTE real n.
initial_field(grid, sparse_coordinates) returns complex transverse amplitude.
Each callback must describe the same physical space on every refinement grid.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict, dataclass
import importlib.util
import json
from pathlib import Path
import sys
from typing import Callable
import numpy as np
from bpm import Grid, axes, refinement_grids

SCENE_API_VERSION = 1


def coordinates(g):
    return tuple(np.meshgrid(*axes(g),indexing='ij',sparse=True))


def field_array(value,g,name):
    a=np.asarray(value,dtype=complex)
    if a.shape!=tuple(g.points) or not np.all(np.isfinite(a)) or not 0 < float(np.sum(abs(a)**2)) < np.inf:
        raise ValueError(f'{name} must be finite nonzero complex field with shape {tuple(g.points)}')
    return a


@dataclass(frozen=True)
class Scene:
    grid: Grid
    initial_field: Callable
    refractive_index: Callable
    roi_um: object = None
    target_field: object = None
    description: str = ''

    def launch(self,g):
        return field_array(self.initial_field(g,coordinates(g)),g,'initial_field')

    def target(self,g):
        return field_array(self.target_field(g,coordinates(g)),g,'target_field')

    def index_factory(self,g):
        def dn(z,q):
            n=np.asarray(self.refractive_index(g,z,q))
            if not np.isrealobj(n) or not np.all(np.isfinite(n)):
                raise ValueError('refractive_index must return finite REAL absolute n')
            try: n=np.broadcast_to(n,tuple(g.points))
            except ValueError as error: raise ValueError('refractive_index shape is not broadcastable to grid') from error
            if np.any(n<=0) or np.max(abs(n-g.background_index))>0.01*g.background_index:
                raise ValueError('absolute index n must be positive and |n-n0|/n0 <=0.01')
            return n-g.background_index
        return dn

    def preflight(self):
        g=self.grid.validate()
        if self.roi_um is not None:
            if len(self.roi_um)!=len(g.points): raise ValueError('ROI dimension mismatch')
            for pair,w,x in zip(self.roi_um,g.windows_um,axes(g)):
                if len(pair)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) for v in pair) or not -w/2<=pair[0]<pair[1]<=w/2:
                    raise ValueError('ROI requires finite bounds within window')
                if not np.any((x>=pair[0])&(x<pair[1])): raise ValueError('ROI has no grid cells')
        for h in [g]+refinement_grids(g):
            h.validate(); self.launch(h)
            if self.target_field is not None: self.target(h)
            q=coordinates(h); index=self.index_factory(h)
            for z in (0.,h.length_um/2,h.length_um): index(z,q)
        return self


def load_scene(path):
    """Executes trusted Python, NOT a sandbox or data-only configuration loader."""
    path=Path(path).resolve()
    if path.suffix.lower()!='.py': raise ValueError('scene must be a .py file')
    spec=importlib.util.spec_from_file_location('_optics_user_scene',path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    previous_path=sys.path[:]
    sys.path.insert(0,str(path.parent))
    try:
        with redirect_stdout(sys.stderr): spec.loader.exec_module(module)
        if getattr(module,'API_VERSION',None)!=SCENE_API_VERSION or not callable(getattr(module,'build',None)):
            raise ValueError('scene requires API_VERSION=1 and build(parameters)->Scene')
        return module
    finally:
        sys.modules.pop(spec.name,None)
        sys.path[:]=previous_path


def run_python_study(module, overrides=None):
    from run_bpm import run_prepared
    override={} if overrides is None else overrides
    if set(override)-{'parameters','scan','objective'}: raise ValueError('unknown override keys')
    parameters=deepcopy(module.PARAMETERS)
    if not isinstance(parameters,dict) or not isinstance(override.get('parameters',{}),dict):
        raise ValueError('PARAMETERS and overrides.parameters must be dictionaries')
    unknown=set(override.get('parameters',{}))-set(parameters)
    if unknown: raise ValueError(f'unknown parameters: {sorted(unknown)}')
    parameters.update(deepcopy(override.get('parameters',{})))
    scan=deepcopy(override.get('scan',getattr(module,'SCAN',None)))
    objective=override.get('objective',getattr(module,'OBJECTIVE',None))
    if objective not in (None,'roi_power','target_overlap'): raise ValueError('objective must be None, roi_power or target_overlap')
    expanded=[('base',parameters)]
    if scan is not None:
        if not isinstance(scan,dict) or set(scan)!={'parameter','values'} or scan['parameter'] not in parameters or not isinstance(scan['values'],(list,tuple)) or not 1<=len(scan['values'])<=12:
            raise ValueError('SCAN requires existing parameter and 1..12 values')
        expanded=[]
        for v in scan['values']:
            p=deepcopy(parameters); p[scan['parameter']]=deepcopy(v)
            expanded.append((f'{scan["parameter"]}={v}',p))
    prepared=[]; targets=[]
    for name,p in expanded:
        # Require portable metadata; arrays/complex fields belong in callbacks, not parameter dictionaries.
        json.dumps(p,allow_nan=False)
        scene=module.build(deepcopy(p))
        if not isinstance(scene,Scene): raise ValueError('build must return python_scene.Scene')
        scene.preflight()
        if objective=='target_overlap' and scene.target_field is None: raise ValueError('target_overlap requires target_field')
        if objective=='roi_power' and scene.roi_um is None: raise ValueError('roi_power requires roi_um; choose a metric explicitly')
        metadata=dict(grid=asdict(scene.grid),python_parameters=p,description=scene.description,scene_api_version=SCENE_API_VERSION)
        if scene.roi_um is not None: metadata['roi_um']=scene.roi_um
        prepared.append((name,metadata,(scene.grid,[],scene.launch,scene.index_factory)))
        targets.append(scene.target if scene.target_field is not None else None)
    with redirect_stdout(sys.stderr):
        result,runs=run_prepared(prepared,targets=targets,objective=objective)
    # Save actual absolute index at the same planes as the sampled fields.
    for (_,_,(g,_,_,factory)),r in zip(prepared,runs):
        q=coordinates(g); dn=factory(g)
        r['refractive_index']=np.array([g.background_index+dn(z,q) for z in r['z_um']])
    result['scene_api_version']=SCENE_API_VERSION
    result['scene_description']=getattr(module,'DESCRIPTION','')
    return result,runs
