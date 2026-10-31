from dataclasses import replace
from pathlib import Path
import sys
import uuid
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from waveguide_sim import Grid, axes, Waveguide, gaussian_beam, simulate, check_convergence


class RK4FrameworkChecks(unittest.TestCase):
    def grid(self, **kw):
        return replace(Grid(windows_um=(32.,),points=(32,),length_um=10.,step_um=.1),**kw)

    def test_plane_wave_fourth_order_and_amplitude_phase(self):
        g = self.grid(length_um=4.)
        x, = axes(g)
        initial = (2+1j)*np.exp(2j*np.pi*3*x/32)
        beta = 2*np.pi*g.background_index/g.wavelength_um
        exact = initial*np.exp(-1j*(2*np.pi*3/32)**2*g.length_um/(2*beta))
        # Uniform index introduces a larger frequency so truncation is above roundoff.
        n = 1.46
        exact *= np.exp(1j*(2*np.pi/g.wavelength_um)*(n*n-g.background_index**2)*g.length_um/(2*g.background_index))
        errors = []
        for h in (1.,.5,.25):
            r = simulate(replace(g,step_um=h),lambda z,q:n,initial)
            np.testing.assert_array_equal(r.field[0],initial)
            errors.append(np.linalg.norm(r.field[-1]-exact))
        self.assertTrue(14 < errors[0]/errors[1] < 18, errors)
        self.assertTrue(14 < errors[1]/errors[2] < 18, errors)

    def test_z_varying_index_four_stages(self):
        g = self.grid(length_um=4.)
        a = .0004
        n0 = g.background_index
        index = lambda z,q: np.sqrt(n0*n0+a*np.exp(z/2))
        length = g.length_um
        exact = np.exp(1j*(2*np.pi/g.wavelength_um)*a*2*(np.exp(length/2)-1)/(2*n0))
        errors=[]
        for h in (1.,.5,.25):
            r=simulate(replace(g,step_um=h),index,np.ones(g.points))
            errors.append(abs(r.field[-1,0]-exact))
        self.assertTrue(13 < errors[0]/errors[1] < 19,errors)
        self.assertTrue(13 < errors[1]/errors[2] < 19,errors)

    def test_2d_gaussian_diffraction_against_analytic_field(self):
        g = self.grid(windows_um=(48.,48.),points=(64,64),length_um=12.)
        launch=gaussian_beam(waists_um=(3.,4.),amplitude=2j)
        r=simulate(g,lambda z,q:g.background_index,launch,store_every=50)
        q=np.meshgrid(*axes(g),indexing='ij',sparse=True)
        beta=2*np.pi*g.background_index/g.wavelength_um
        exact=2j
        for c,w in zip(q,(3.,4.)):
            b=1+2j*g.length_um/(beta*w*w)
            exact=exact/np.sqrt(b)*np.exp(-c*c/(w*w*b))
        self.assertLess(np.linalg.norm(r.field[-1]-exact)/np.linalg.norm(exact),1e-9)
        self.assertLess(r.diagnostics['max_relative_power_drift'],1e-10)
        np.testing.assert_allclose(r.z_um,[0,5,10,12])

    def test_shape_callback_and_full_history_no_mutation(self):
        g=self.grid(length_um=.25,step_um=.1)
        guide=Waveguide(lambda z,q:np.exp(-((q[0]-z)/2)**2),1.453,1.45)
        initial=gaussian_beam(waists_um=(2.,))(tuple(np.meshgrid(*axes(g),indexing='ij',sparse=True)))
        before=initial.copy()
        r=simulate(g,guide,initial)
        self.assertEqual(r.field.shape,(4,32))
        self.assertAlmostEqual(r.z_um[-1],.25)
        np.testing.assert_array_equal(initial,before)
        np.testing.assert_array_equal(r.field[0],initial)
        self.assertGreater(r.power[0],1.)

    def test_invalid_input_index_and_unstable_step(self):
        g=self.grid()
        for n in (0.,1.6,np.nan,1.45+0j,np.zeros((2,3))):
            with self.subTest(n=n),self.assertRaises(ValueError):
                simulate(g,lambda z,q:n,np.ones(g.points))
        for initial in (np.zeros(g.points),np.ones(4),np.full(g.points,np.nan)):
            with self.assertRaises(ValueError): simulate(g,lambda z,q:1.45,initial)
        with self.assertRaisesRegex(ValueError,'stability'):
            simulate(self.grid(step_um=10.),lambda z,q:1.45,np.ones(g.points))
        with self.assertRaises(ValueError): Waveguide(lambda z,q:2.,1.453,1.45)(0,(np.zeros(3),))

    def test_convergence_in_bending_guide_and_failed_boundary(self):
        g=self.grid(windows_um=(48.,),points=(64,),length_um=10.)
        guide=Waveguide(lambda z,q:np.exp(-((q[0]-.5*np.sin(z/20))/3)**2),1.453,1.45)
        checks=check_convergence(g,guide,gaussian_beam(waists_um=(3.,)))
        self.assertTrue(checks['passed'],checks)
        failed=check_convergence(g,lambda z,q:1.45,gaussian_beam(waists_um=(3.,),center_um=(20.,)))
        self.assertFalse(failed['passed'])

    def test_npz_roundtrip_and_no_overwrite(self):
        r=simulate(self.grid(length_um=.2),lambda z,q:1.45,gaussian_beam(waists_um=(2.,)))
        # Use workspace temporary area; test leaves no changes to historical results.
        directory=Path(__file__).resolve().parents[1]/'artifacts'/'rk4-tests'/uuid.uuid4().hex
        directory.mkdir(parents=True)
        path=directory/'fields.npz'
        r.save(path)
        with np.load(path,allow_pickle=False) as saved:
            np.testing.assert_array_equal(saved['field'],r.field)
            self.assertIn('classical_RK4',str(saved['metadata_json']))
        with self.assertRaises(FileExistsError): r.save(path)


if __name__=='__main__': unittest.main()
