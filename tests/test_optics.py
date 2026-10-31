"""Hardware-free physical/numerical benchmarks. Run via simulate-optics.ps1 -Test."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'/'Agamemnon.Optics'))
from optics import Parameters, eigensystem, find_design, grid, propagate
from run import verify_candidate


class OpticsChecks(unittest.TestCase):
    def setUp(self):
        self.p=Parameters(points=256,window_um=80,length_um=1000,step_um=2,separation_um=10)

    def test_free_gaussian_matches_analytical_diffraction(self):
        p=replace(self.p,length_um=200)
        x=grid(p)
        w=4.0
        r=propagate(p,initial=np.exp(-(x/w)**2),dn=np.zeros(p.points),sample_count=2)
        intensity=abs(r['fields'][-1])**2
        dx=p.window_um/p.points
        variance=float(np.sum(x*x*intensity)*dx)
        k=2*np.pi*p.background_index/p.wavelength_um
        expected=w*w/4*(1+(2*p.length_um/(k*w*w))**2)
        self.assertAlmostEqual(variance/expected,1,places=5)
        self.assertLess(r['max_power_drift'],1e-10)

    def test_single_guide_mode_remains_stationary(self):
        p=self.p
        _,modes=eigensystem(p,single=True)
        from optics import index_increment
        r=propagate(p,initial=modes[:,0],dn=index_increment(p,grid(p),single=True),sample_count=2)
        overlap=abs(np.vdot(r['fields'][0],r['fields'][-1])*(p.window_um/p.points))**2
        self.assertGreater(overlap,0.9999)

    def test_coupler_and_refinements_match_spectral_reference(self):
        v=verify_candidate(replace(self.p,length_um=3421))
        self.assertTrue(v['passed'],v)

    def test_farther_guides_couple_more_slowly(self):
        short=propagate(self.p,sample_count=2)
        far=propagate(replace(self.p,separation_um=16),sample_count=2)
        self.assertGreater(short['right_power'][-1],far['right_power'][-1]*10)

    def test_scan_crossing_is_resimulated(self):
        p=replace(self.p,length_um=6000)
        result,_=find_design(p,[10.,12.],0.5)
        self.assertEqual(result['selected_index'],0)
        self.assertLess(result['target_error'],0.0005)
        self.assertTrue(3300<result['selected_parameters']['length_um']<3600)

    def test_unreachable_target_is_explicit(self):
        result,_=find_design(replace(self.p,length_um=50),[16.],0.5)
        self.assertEqual(result['status'],'target_not_reached')
        self.assertIsNone(result['selected_index'])

    def test_zero_nonfinite_and_wrong_shape_launch_rejected(self):
        for field in (np.zeros(self.p.points),np.full(self.p.points,np.nan),np.ones(3)):
            with self.subTest(shape=field.shape),self.assertRaises(ValueError):
                propagate(self.p,initial=field)

    def test_invalid_parameters_and_targets_rejected(self):
        for changes in ({'wavelength_um':float('nan')},{'step_um':0},{'points':257},{'points':True},{'delta_index':0.2},{'window_um':10},{'radius_um':0.1},{'separation_um':1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(self.p,**changes).validate()
        for target in (-1,0,1,float('nan')):
            with self.subTest(target=target),self.assertRaises(ValueError):
                find_design(self.p,[10],target)

    def test_periodic_boundary_risk_is_reported(self):
        p=replace(self.p,window_um=50,length_um=1000)
        x=grid(p)
        r=propagate(p,initial=np.exp(-((x-22)/2)**2),dn=np.zeros(p.points),sample_count=2)
        self.assertGreater(r['max_edge_power'],0.9)


if __name__=='__main__':
    unittest.main(verbosity=2)
