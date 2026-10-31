from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
import numpy as np

SOURCE=Path(__file__).resolve().parents[1]/'src'/'Agamemnon.Optics'
sys.path.insert(0,str(SOURCE))
from bpm import Grid, axes, gaussian_input, guide_at, propagate, validate_guides, verify
from run_bpm import cases, run_study


class GeneralBPMChecks(unittest.TestCase):
    def test_2d_free_diffraction_and_tilt(self):
        g=Grid(length_um=100.,samples=2)
        r=propagate(g,[],gaussian_input(g,[0.,0.],[3.,4.],[0.01,-0.02]))
        q=np.meshgrid(*axes(g),indexing='ij',sparse=True)
        power=abs(r['fields'][-1])**2*(64/128)**2
        k=2*np.pi*g.background_index/g.wavelength_um
        for j,w in enumerate((3.,4.)):
            mu=r['centroid_um'][-1,j]
            self.assertAlmostEqual(mu,(1.,-2.)[j],places=6)
            expected=w*w/4*(1+(2*g.length_um/(k*w*w))**2)
            self.assertAlmostEqual(float((power*(q[j]-mu)**2).sum())/expected,1,places=6)
        self.assertLess(r['max_power_drift'],1e-12)

    def test_2d_separable_free_matches_1d(self):
        g=Grid(length_um=50.,samples=2)
        r=propagate(g,[],gaussian_input(g,[0,0],[3,3]))
        h=replace(g,windows_um=(64.,),points=(128,))
        one=propagate(h,[],gaussian_input(h,[0],[3]))
        self.assertLess(np.max(abs(r['fields'][-1]-np.outer(one['fields'][-1],one['fields'][-1]))),1e-13)

    def test_time_dependent_uniform_index_exact_phase(self):
        g=Grid(windows_um=(64.,),points=(128,),length_um=100.,samples=2)
        initial=gaussian_input(g,[0],[3])
        a=1e-8; k0=2*np.pi/g.wavelength_um; n=g.background_index
        r=propagate(g,[],initial,index_fn=lambda z,q: np.full(g.points,np.sqrt(n*n+a*z)-n))
        free=propagate(g,[],initial)
        exact=free['fields'][-1]*np.exp(1j*k0*a*g.length_um**2/(4*n))
        self.assertLess(np.max(abs(r['fields'][-1]-exact)),1e-12)

    def test_grin_centroid_matches_harmonic_oscillator(self):
        g=Grid(windows_um=(96.,),points=(192,),length_um=200.,step_um=.25,samples=2)
        omega=0.002; n=g.background_index
        r=propagate(g,[],gaussian_input(g,[2],[3]),index_fn=lambda z,q: np.sqrt(n*n*(1-omega**2*q[0]**2))-n)
        self.assertAlmostEqual(r['centroid_um'][-1,0],2*np.cos(omega*g.length_um),places=6)

    def test_general_1d_matches_existing_solver(self):
        from optics import Parameters, grid, index_increment, propagate as old
        p=Parameters(points=256,window_um=80.,length_um=200.,step_um=2.,separation_um=10.)
        x=grid(p); initial=np.exp(-((x+5)/3)**2); dn=index_increment(p,x)
        ref=old(p,initial=initial,dn=dn,sample_count=2)
        g=Grid(windows_um=(80.,),points=(256,),length_um=200.,step_um=2.,samples=2)
        r=propagate(g,[],initial,index_fn=lambda z,q:dn)
        self.assertLess(np.max(abs(ref['fields']-r['fields'])),1e-12)

    def test_dynamic_guides_refinement(self):
        spec=json.loads((SOURCE/'bpm_example.json').read_text(encoding='utf-8-sig'))
        g=Grid(**spec['grid'])
        v=verify(g,spec['guides'],lambda h:gaussian_input(h,**spec['input']))
        self.assertTrue(v['passed'],v)
        c,r,dn=guide_at(spec['guides'][0],250.)
        np.testing.assert_allclose(c,[-3.5,.75]); np.testing.assert_allclose(r,[3.,3.1])

    def test_boundary_failure_is_not_verified(self):
        spec=dict(grid=dict(windows_um=[32.],points=[128],length_um=1000.,step_um=10.,samples=2),guides=[],input=dict(center_um=[0],waists_um=[3]))
        result,_=run_study(spec)
        self.assertEqual(result['status'],'numerical_checks_failed')
        self.assertIsNone(result['best_verified_roi_case'])

    def test_scan_and_invalid_inputs(self):
        spec=dict(grid=dict(wavelength_um=.78),guides=[],input={},scan=dict(path='grid.wavelength_um',values=[.78,.8]))
        expanded=cases(spec)
        self.assertEqual(expanded[1][1]['grid']['wavelength_um'],.8)
        self.assertEqual(spec['grid']['wavelength_um'],.78)
        for bad in (dict(points=(True,128)),dict(points=(127,128)),dict(step_um=0),dict(samples=True)):
            with self.assertRaises(ValueError): Grid(**bad).validate()
        g=Grid()
        for field in (np.zeros(g.points),np.full(g.points,np.nan),np.ones(3)):
            with self.assertRaises(ValueError): propagate(g,[],field)
        with self.assertRaises(ValueError): propagate(g,[],np.ones(g.points),index_fn=lambda z,q:np.zeros(4))
        spec=json.loads((SOURCE/'bpm_example.json').read_text(encoding='utf-8-sig'))
        spec['guides'][0]['knots'][1]['z_um']=0
        with self.assertRaises(ValueError): validate_guides(g,spec['guides'])


if __name__=='__main__': unittest.main()
