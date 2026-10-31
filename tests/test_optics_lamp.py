"""Physical, gradient and correlation benchmarks for the modal LAMP demo."""
from dataclasses import replace
from pathlib import Path
import sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'/'Agamemnon.Optics'))
from lamp import (LampParameters,centres,step_operator,build_network,transfer,
                  row_loss_gradient,train_kernel,evaluate_image,patches,snapshot_transfers)


class LampChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=LampParameters()
        cls.network=build_network(cls.p)
        cls.kernel=np.array([[-1.,0,1],[-2,0,2],[-1,0,1]])
        cls.fit=train_kernel(cls.network['mixers'],cls.kernel)

    def test_two_mode_matches_analytic_power_exchange(self):
        coupling=.117;length=3.7
        matrix=step_operator(np.array([[0.,-coupling],[-coupling,0.]]),length)
        self.assertAlmostEqual(abs(matrix[1,0])**2,np.sin(coupling*length)**2,places=13)

    def test_geometry_is_three_dimensional_and_returns_to_ports(self):
        np.testing.assert_allclose(centres(self.p,0),centres(self.p,90))
        expanded=centres(self.p,17)
        self.assertAlmostEqual(expanded[:,0].ptp() if hasattr(expanded[:,0],'ptp') else np.ptp(expanded[:,0]),1400)
        self.assertAlmostEqual(np.ptp(expanded[:,1]),1400)
        self.assertEqual(len(self.network['mixers']),4)

    def test_empirical_reference_units(self):
        value=6.1688*np.exp(-.2641*10)
        self.assertAlmostEqual(value,.439758,delta=.001)

    def test_analytic_gradient_matches_central_difference(self):
        rng=np.random.default_rng(9);phases=rng.normal(size=(3,9));target=self.kernel.ravel()/np.linalg.norm(self.kernel)
        _,gradient=row_loss_gradient(self.network['mixers'],phases,target)
        for index in [(0,0),(1,4),(2,8)]:
            plus=phases.copy();minus=phases.copy();plus[index]+=1e-6;minus[index]-=1e-6
            fp=row_loss_gradient(self.network['mixers'],plus,target)[0];fm=row_loss_gradient(self.network['mixers'],minus,target)[0]
            self.assertAlmostEqual(gradient[index],(fp-fm)/2e-6,places=6)

    def test_programmed_kernel_generalizes_to_random_inputs(self):
        matrix=self.fit['matrix'];target=self.kernel.ravel()
        rng=np.random.default_rng(900);values=rng.normal(size=(9,100))+1j*rng.normal(size=(9,100))
        actual=np.linalg.norm(self.kernel)*(matrix@values)[4]
        self.assertLess(np.linalg.norm(actual-target@values)/np.linalg.norm(target@values),.00001)
        self.assertLess(np.linalg.norm(matrix.conj().T@matrix-np.eye(9)),1e-10)

    def test_valid_correlation_alignment_and_no_patch_normalization(self):
        image=np.arange(25.).reshape(5,5)/25
        result=evaluate_image(image,self.kernel,self.fit['matrix'])
        expected=np.array([[np.sum(image[r:r+3,c:c+3]*self.kernel) for c in range(3)] for r in range(3)])
        np.testing.assert_allclose(result['reference'],expected,atol=1e-12)
        doubled=evaluate_image(2*image,self.kernel,self.fit['matrix'])
        np.testing.assert_allclose(doubled['field'],2*result['field'],atol=1e-12)
        np.testing.assert_allclose(doubled['intensity'],4*result['intensity'],atol=1e-12)

    def test_direct_intensity_loses_sign(self):
        image=np.arange(25.).reshape(5,5)/25
        a=evaluate_image(image,self.kernel,self.fit['matrix']);b=evaluate_image(-image,self.kernel,self.fit['matrix'])
        np.testing.assert_allclose(a['intensity'],b['intensity'])
        np.testing.assert_allclose(a['field'],-b['field'])

    def test_snapshot_transfer_matches_complete_network(self):
        z,matrices=snapshot_transfers(self.network,self.fit['phases'])
        np.testing.assert_allclose(matrices[-1],self.fit['matrix'],atol=2e-12)
        self.assertEqual(z[-1],90)
        self.assertTrue(np.all(np.diff(z)>=0))

    def test_invalid_units_geometry_and_images_rejected(self):
        for changes in ({'wavelength_nm':780},{'step_mm':0},{'pitch_um':1},{'starts_mm':(5,6,7)},{'length_mm':10},{'step_mm':float('nan')}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(self.p,**changes).validate()
        with self.assertRaises(ValueError):patches(np.ones((2,2)))
        with self.assertRaises(ValueError):train_kernel(self.network['mixers'],np.zeros((3,3)))


if __name__=='__main__':unittest.main(verbosity=2)
