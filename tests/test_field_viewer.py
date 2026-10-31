from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waveguide_sim.viewer import view_field, view_npz


class FieldViewerChecks(unittest.TestCase):
    def setUp(self):
        # Synthetic non-square field with distinct amplitude and phase at each node.
        self.x = np.arange(4.) - 1.5
        self.y = np.arange(6.) - 2.5
        self.z = np.array([0., .7, 1.])  # shortened final interval, as with store_every
        z, x, y = np.meshgrid(self.z, self.x, self.y, indexing='ij')
        self.field = (1 + z + x*x + y*y) * np.exp(1j * (z + x + y))

    def tearDown(self):
        plt.close('all')

    def test_slices_complex_point_and_fixed_color_scale(self):
        original = self.field.copy()
        viewer = view_field(self.field, (self.x, self.y), self.z, show=False)
        self.assertTrue(np.shares_memory(viewer.field, self.field))
        intensity_limits = viewer.intensity_image.get_clim()
        for iz, z in enumerate(self.z):
            viewer.sliders['z'].set_val(z)
            viewer.sliders['x'].set_val(self.x[-1])
            viewer.sliders['y'].set_val(self.y[1])
            self.assertEqual(viewer.indices, (iz, 3, 1))
            self.assertEqual(viewer.selected_field, self.field[iz, 3, 1])
            np.testing.assert_allclose(
                viewer.intensity_image.get_array().reshape(6, 4),
                (abs(self.field[iz])**2).T,
            )
            np.testing.assert_allclose(
                viewer.phase_image.get_array().reshape(6, 4), np.angle(self.field[iz]).T,
            )
            self.assertEqual(viewer.intensity_image.get_clim(), intensity_limits)
            self.assertEqual(viewer.phase_image.get_clim(), (-np.pi, np.pi))
            np.testing.assert_allclose(viewer.z_marker.get_xdata(), [z, z])
        np.testing.assert_allclose(viewer.xz, (abs(self.field)**2).sum(axis=2))
        np.testing.assert_array_equal(self.field, original)

    def test_npz_load_once_then_browse_without_file_or_simulation_access(self):
        directory = Path(__file__).resolve().parents[1] / 'artifacts' / 'viewer-tests' / uuid.uuid4().hex
        directory.mkdir(parents=True)
        path = directory / 'fields.npz'
        np.savez_compressed(path, field=self.field, x_um=self.x, y_um=self.y, z_um=self.z)
        original_bytes = path.read_bytes()
        with patch('waveguide_sim.viewer.np.load', wraps=np.load) as loader:
            viewer = view_npz(path, show=False)
            self.assertEqual(loader.call_count, 1)
            self.assertEqual(loader.call_args.kwargs, {'allow_pickle': False})
        with patch('waveguide_sim.viewer.np.load', side_effect=AssertionError('unexpected reread')), \
                patch('waveguide_sim.solver.simulate', side_effect=AssertionError('unexpected propagation')):
            viewer.sliders['z'].set_val(self.z[-1])
            viewer.sliders['x'].set_val(self.x[0])
            viewer.sliders['y'].set_val(self.y[-1])
        self.assertEqual(viewer.selected_field, self.field[-1, 0, -1])
        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(list(directory.iterdir()), [path])

    def test_invalid_axes_and_nonfinite_field_rejected_without_window(self):
        invalid = (
            (self.field[:, :, 0], (self.x,), self.z),
            (self.field, (self.x[:-1], self.y), self.z),
            (self.field, (self.x[::-1], self.y), self.z),
            (self.field, (self.x, self.y), np.array([0., .7, .7])),
            (self.field, (np.array([-1.5, -.5, .5, 2.]), self.y), self.z),
            (np.full(self.field.shape, np.nan), (self.x, self.y), self.z),
        )
        for field, axes, z in invalid:
            with self.subTest(shape=field.shape), self.assertRaises(ValueError):
                view_field(field, axes, z, show=False)
        self.assertFalse(plt.get_fignums())

    def test_zero_field_reports_undefined_phase(self):
        viewer = view_field(np.zeros_like(self.field), (self.x, self.y), self.z, show=False)
        self.assertEqual(viewer.selected_field, 0)
        self.assertIn('phase = undefined', viewer.readout.get_text())
        self.assertEqual(viewer.intensity_image.get_clim(), (0., 1.))


if __name__ == '__main__':
    unittest.main()
