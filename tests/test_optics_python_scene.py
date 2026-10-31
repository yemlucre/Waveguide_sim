from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import unittest
import numpy as np

SOURCE=Path(__file__).resolve().parents[1]/'src'/'Agamemnon.Optics'
sys.path.insert(0,str(SOURCE))
from bpm import Grid, axes, gaussian_input, propagate, verify
from python_scene import Scene, coordinates, load_scene, run_python_study


def analytic_beam(g,q,tilt,z):
    k=2*np.pi*g.background_index/g.wavelength_um
    return np.exp(-(q[0]-tilt*z)**2/(9+2j*z/k)+1j*k*tilt*q[0]-.5j*k*tilt**2*z)


class PythonSceneChecks(unittest.TestCase):
    def test_field_only_study_needs_no_design_objective(self):
        g=Grid(windows_um=(64.,),points=(128,),length_um=10.,samples=2)
        module=SimpleNamespace(PARAMETERS={},build=lambda p:Scene(g,lambda h,q:np.exp(-(q[0]/3)**2),lambda h,z,q:h.background_index))
        result,runs=run_python_study(module)
        self.assertEqual(result['status'],'verified_theoretical_propagation')
        self.assertIsNone(result['best_verified_case'])
        self.assertIsNone(result['objective'])
        self.assertEqual(runs[0]['fields'].shape,(2,128))

    def test_callback_refinements_and_exact_uniform_phase(self):
        g=Grid(windows_um=(64.,),points=(128,),length_um=30.,samples=3,step_um=2.)
        seen=set(); a=1e-8
        def index(h,z,q):
            seen.add((tuple(h.points),tuple(h.windows_um),h.step_um))
            return np.sqrt(h.background_index**2+a*z)
        scene=Scene(g,lambda h,q:np.exp(-(q[0]/3)**2),index,roi_um=[[-8,8]])
        scene.preflight()
        v=verify(g,[],scene.launch,index_factory=scene.index_factory)
        self.assertTrue(v['passed'],v)
        self.assertIn(((256,),(64.,),2.),seen)
        self.assertIn(((192,),(96.,),2.),seen)
        r=propagate(g,[],scene.launch(g),index_fn=scene.index_factory(g))
        free=propagate(g,[],scene.launch(g))
        phase=np.exp(1j*(2*np.pi/g.wavelength_um)*a*g.length_um**2/(4*g.background_index))
        self.assertLess(np.max(abs(r['fields'][-1]-phase*free['fields'][-1])),1e-12)

    def test_phase_sensitive_target_scan_selects_correct_input(self):
        g=Grid(windows_um=(64.,),points=(128,),length_um=30.,step_um=2.,samples=3)
        def build(p):
            return Scene(g,lambda h,q:analytic_beam(h,q,p['tilt'],0),lambda h,z,q:h.background_index,
                         roi_um=[[-10,10]],target_field=lambda h,q:analytic_beam(h,q,.03,h.length_um))
        module=SimpleNamespace(PARAMETERS={'tilt':.03},SCAN={'parameter':'tilt','values':[-.03,.03]},OBJECTIVE='target_overlap',build=build)
        result,runs=run_python_study(module)
        self.assertEqual(result['status'],'verified_theoretical_propagation')
        self.assertEqual(result['best_verified_case'],1)
        self.assertGreater(result['cases'][1]['metrics']['target_overlap'],1-1e-12)
        k=2*np.pi*g.background_index/g.wavelength_um
        expected=np.exp(-(k*3*.06)**2/4)
        self.assertAlmostEqual(result['cases'][0]['metrics']['target_overlap'],expected,places=10)
        for r in runs:
            self.assertEqual(r['refractive_index'].shape,r['fields'].shape)
            self.assertTrue(np.iscomplexobj(r['fields']))

    def test_non_gaussian_2d_python_scene_and_overrides(self):
        module=load_scene(SOURCE/'scene_example.py')
        result,runs=run_python_study(module,{'parameters':{'window_um':64.,'points':128,'length_um':20.,'samples':3,'bend_um':.25}})
        self.assertEqual(result['status'],'verified_theoretical_propagation')
        self.assertEqual(runs[0]['fields'].shape,(3,128,128))
        self.assertGreater(np.max(abs(runs[0]['fields'][0].imag)),0)
        self.assertEqual(module.PARAMETERS['length_um'],200.)
        self.assertNotEqual(runs[0]['refractive_index'][0].tolist(),runs[0]['refractive_index'][-1].tolist())

    def test_bad_absolute_index_and_custom_fields_rejected(self):
        g=Grid(windows_um=(64.,),points=(128,),length_um=10.,samples=2)
        initial=lambda h,q:np.exp(-(q[0]/3)**2)
        for index in (lambda h,z,q:0.,lambda h,z,q:1.45+.1j,lambda h,z,q:np.nan,
                      lambda h,z,q:np.ones(3),lambda h,z,q:h.background_index+.1):
            with self.subTest(index=index),self.assertRaises(ValueError): Scene(g,initial,index).preflight()
        for field in (lambda h,q:np.zeros(h.points),lambda h,q:np.ones(4),lambda h,q:np.full(h.points,np.inf)):
            with self.assertRaises(ValueError): Scene(g,field,lambda h,z,q:1.45).preflight()

    def test_invalid_parameters_roi_and_missing_target(self):
        module=load_scene(SOURCE/'scene_example.py')
        for override in ({'parameters':{'typo':1}}, {'scan':{'parameter':'missing','values':[1]}},
                         {'objective':'invented'}, {'parameters':{'gap_um':float('nan')}}):
            with self.subTest(override=override),self.assertRaises(ValueError): run_python_study(module,override)
        g=Grid(windows_um=(64.,),points=(128,),length_um=10.)
        scene=Scene(g,lambda h,q:np.exp(-(q[0]/3)**2),lambda h,z,q:1.45,roi_um=[[0.01,.02]])
        with self.assertRaises(ValueError): scene.preflight()
        empty=SimpleNamespace(PARAMETERS={},OBJECTIVE='target_overlap',build=lambda p:replace(scene,roi_um=None))
        with self.assertRaises(ValueError): run_python_study(empty)

    def test_grid_bound_array_is_rejected_during_refinement(self):
        g=Grid(windows_um=(64.,),points=(128,),length_um=10.)
        # A fixed array cannot silently stand in for a physical field on a different grid.
        scene=Scene(g,lambda h,q:np.exp(-(axes(g)[0]/3)**2),lambda h,z,q:1.45)
        with self.assertRaises(ValueError): scene.preflight()


if __name__=='__main__': unittest.main()
