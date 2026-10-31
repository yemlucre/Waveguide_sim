from dataclasses import replace
from pathlib import Path
import sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'/'Agamemnon.Optics'))
from passive_lantern import Material,Geometry,isolated_mode,pair_coupling,coupling_table,positions,arc_excess,modal_propagate,local_pair_check


class PassiveLanternChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=Material(); cls.mode=isolated_mode(cls.m,points=128,window_um=64.,imaginary_step_um=2.,iterations=2500)
        cls.table=dict(distances_um=np.array([10.,60.]),coupling_per_mm=np.array([.1,.1]))

    def test_reported_stagger_geometry_and_overlap(self):
        p=Geometry()
        np.testing.assert_allclose(positions(p,0),positions(p,100))
        xy=positions(p,14.25).reshape(8,8,2)
        np.testing.assert_allclose(np.diff(xy[0,:,0]),700)
        np.testing.assert_allclose(np.diff(xy[1,:,0]),15)
        # First layer is returning while second is expanding: both are active.
        mid=positions(p,18.).reshape(8,8,2)
        self.assertGreater(np.ptp(mid[0,:,0]),105)
        self.assertGreater(np.ptp(mid[1,:,0]),105)
        np.testing.assert_allclose(mid[:,:,1],positions(p,0).reshape(8,8,2)[:,:,1])

    def test_arclength_quadrature_additivity_and_straight_zero(self):
        p=Geometry()
        np.testing.assert_allclose(arc_excess(p,0,5),0,atol=1e-14)
        np.testing.assert_allclose(arc_excess(p,8,8.02),arc_excess(p,8,8.01)+arc_excess(p,8.01,8.02),atol=1e-12)
        self.assertTrue(np.all(arc_excess(p,8,8.02)>=0))

    def test_static_two_channel_exact_exchange_and_conservation(self):
        p=Geometry(rows=1,columns=2,start_mm=10,length_mm=30,expanded_pitch_um=15,step_mm=.05,samples=21)
        r=modal_propagate(p,self.table,11.,0)
        np.testing.assert_allclose(r['power'][:,1],np.sin(.1*r['z_mm'])**2,atol=1e-12)
        self.assertLess(r['max_power_drift'],1e-11)

    def test_passive_path_phase_and_step_refinement(self):
        p=Geometry(rows=2,columns=2,length_mm=40,step_mm=.05,samples=2)
        distances=np.arange(10.,60.01,.5)
        smooth_table=dict(distances_um=distances,coupling_per_mm=.1*np.exp(-.3*(distances-15)))
        a=modal_propagate(p,smooth_table,11.,0)
        b=modal_propagate(replace(p,step_mm=.025),smooth_table,11.,0)
        self.assertLess(np.linalg.norm(a['fields'][-1]-b['fields'][-1]),.002)
        self.assertLess(a['max_power_drift'],1e-10)

    def test_mode_bound_and_coupling_trend(self):
        self.assertLess(self.mode['energy_per_um'],0)
        self.assertLess(self.mode['residual_per_um'],1e-5)
        self.assertLess(self.mode['edge_power'],1e-6)
        near=pair_coupling(self.m,self.mode,12)['coupling_per_mm']
        far=pair_coupling(self.m,self.mode,18)['coupling_per_mm']
        self.assertGreater(near,far*5)

    def test_continuous_pair_bpm_matches_modal_projection(self):
        r=local_pair_check(self.m,self.mode,15,length_um=200)
        self.assertLess(r['max_power_difference'],.002)
        self.assertLess(r['run']['max_power_drift'],1e-10)

    def test_invalid_geometry_and_material(self):
        for p in (Geometry(pitch_um=0),Geometry(rows=9),Geometry(length_mm=10),Geometry(step_mm=.2)):
            with self.assertRaises(ValueError): p.validate()
        with self.assertRaises(ValueError): Material(delta_index=.1).validate()
        with self.assertRaises(ValueError): positions(Geometry(),101)


if __name__=='__main__': unittest.main()
