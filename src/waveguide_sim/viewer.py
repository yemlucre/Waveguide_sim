"""Browse saved (z, x, y) envelope data without running a simulation.

From Python: view_field(result.field, result.axes_um, result.z_um).
From a saved file: python -m waveguide_sim.viewer path/to/fields.npz.
Only saved grid nodes are shown; no interpolation or physical calibration.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider


class FieldViewer:
    """Retain the field, figure, and three discrete coordinate sliders."""

    def __init__(self, field, axes_um, z_um):
        self.field = np.asarray(field)
        if self.field.ndim != 3 or not np.issubdtype(self.field.dtype, np.number):
            raise ValueError('viewer requires numeric field shaped (Nz, Nx, Ny)')
        if len(axes_um) != 2:
            raise ValueError('viewer requires two transverse axes (x_um, y_um)')
        self.x_um, self.y_um = (np.asarray(a, dtype=float) for a in axes_um)
        self.z_um = np.asarray(z_um, dtype=float)
        for axis, size in zip((self.z_um, self.x_um, self.y_um), self.field.shape):
            if (axis.ndim != 1 or axis.size != size or size < 2
                    or not np.all(np.isfinite(axis)) or np.any(np.diff(axis) <= 0)):
                raise ValueError('axes must be finite, increasing, and match field; at least two nodes per axis')
        for axis in (self.x_um, self.y_um):
            if not np.allclose(np.diff(axis), axis[1] - axis[0], rtol=1e-9, atol=1e-12):
                raise ValueError('transverse axes must be uniformly spaced')
        if not np.all(np.isfinite(self.field)):
            raise ValueError('field must be finite')

        # Process one plane at a time; do not duplicate the entire intensity volume.
        self.xz = np.empty((len(self.z_um), len(self.x_um)))
        maximum = 0.0
        for iz, plane in enumerate(self.field):
            intensity = abs(plane)**2
            self.xz[iz] = intensity.sum(axis=1) * (self.y_um[1] - self.y_um[0])
            maximum = max(maximum, float(intensity.max()))

        self.figure, self.axes = plt.subplots(1, 3, figsize=(13, 6.5))
        self.figure.subplots_adjust(left=.06, right=.96, bottom=.34, top=.88, wspace=.55)
        image = self.axes[0].pcolormesh(
            self.z_um, self.x_um, self.xz.T, shading='auto', vmin=0,
        )
        self.axes[0].set(xlabel='z (um)', ylabel='x (um)', title='Intensity integrated over y')
        self.figure.colorbar(image, ax=self.axes[0])
        self.z_marker = self.axes[0].axvline(self.z_um[0], color='white', ls='--')

        plane = self.field[0]
        self.intensity_image = self.axes[1].pcolormesh(
            self.x_um, self.y_um, (abs(plane)**2).T, shading='auto',
            vmin=0, vmax=maximum if maximum > 0 else 1,
        )
        self.phase_image = self.axes[2].pcolormesh(
            self.x_um, self.y_um, np.angle(plane).T, shading='auto',
            cmap='twilight', vmin=-np.pi, vmax=np.pi,
        )
        self.figure.colorbar(self.intensity_image, ax=self.axes[1])
        self.figure.colorbar(self.phase_image, ax=self.axes[2], label='rad')
        self.crosshairs = []
        for ax, title in zip(self.axes[1:], ('Slice intensity', 'Envelope phase')):
            ax.set(xlabel='x (um)', ylabel='y (um)', title=title, aspect='equal')
            self.crosshairs.append((ax.axvline(0, color='white', ls='--'),
                                    ax.axhline(0, color='white', ls='--')))

        self.sliders = {}
        for name, values, height, initial in (
            ('z', self.z_um, .24, self.z_um[0]),
            ('x', self.x_um, .18, self.x_um[np.argmin(abs(self.x_um))]),
            ('y', self.y_um, .12, self.y_um[np.argmin(abs(self.y_um))]),
        ):
            ax = self.figure.add_axes((.13, height, .70, .028))
            self.sliders[name] = Slider(
                ax, name + ' (um)', values[0], values[-1],
                valinit=initial, valstep=values, valfmt='%.6g',
            )
        self.readout = self.figure.text(.06, .06, '', fontsize=10, family='monospace')
        self.figure.text(.06, .02, 'Saved nodes only. Phase is undefined at zero intensity.', fontsize=9)
        self._last_iz = None
        for slider in self.sliders.values():
            slider.on_changed(self._update)
        self._update()
        # Keep widgets alive even if a caller does not retain the returned viewer.
        self.figure._waveguide_field_viewer = self

    def _update(self, _value=None):
        iz = int(np.argmin(abs(self.z_um - self.sliders['z'].val)))
        ix = int(np.argmin(abs(self.x_um - self.sliders['x'].val)))
        iy = int(np.argmin(abs(self.y_um - self.sliders['y'].val)))
        self.indices = (iz, ix, iy)
        if iz != self._last_iz:
            plane = self.field[iz]
            self.intensity_image.set_array((abs(plane)**2).T.ravel())
            self.phase_image.set_array(np.angle(plane).T.ravel())
            self.z_marker.set_xdata([self.z_um[iz]] * 2)
            self.figure.suptitle(f'Field slice: z = {self.z_um[iz]:.6g} um ({iz + 1}/{len(self.z_um)})')
            self._last_iz = iz
        for vertical, horizontal in self.crosshairs:
            vertical.set_xdata([self.x_um[ix]] * 2)
            horizontal.set_ydata([self.y_um[iy]] * 2)
        value = self.selected_field
        phase = f'{np.angle(value):.6g}' if value != 0 else 'undefined'
        self.readout.set_text(
            f'(x,y,z) = ({self.x_um[ix]:.6g}, {self.y_um[iy]:.6g}, {self.z_um[iz]:.6g}) um    '
            f'psi = {value.real:.6g}{value.imag:+.6g}j\n'
            f'|psi|^2 = {abs(value)**2:.6g}    phase = {phase} rad'
        )
        self.figure.canvas.draw_idle()

    @property
    def selected_field(self):
        """Complex envelope at the selected saved (z, x, y) node."""
        return self.field[self.indices]

    def show(self):
        """Block until the interactive window is closed."""
        plt.show(block=True)


def view_field(field, axes_um, z_um, *, show=True):
    """Browse a 2D transverse field history already in memory.

    field has shape (Nz, Nx, Ny); axes_um is (x_um, y_um); lengths are um.
    Returns a FieldViewer. With show=False the caller manages display/closing.
    Intensity uses one fixed color scale across all z; phase stays in [-pi, pi].
    The field array is retained, not copied or recalculated. This view does not
    establish convergence or calibrate field/intensity units.
    """
    viewer = FieldViewer(field, axes_um, z_um)
    if show:
        viewer.show()
    return viewer


def view_npz(path, *, show=True):
    """Load field and coordinates once, close the NPZ, then browse in memory."""
    with np.load(path, allow_pickle=False) as data:
        if 'y_um' not in data:
            raise ValueError('viewer requires a 2D transverse NPZ containing y_um')
        field = data['field']
        axes_um = (data['x_um'], data['y_um'])
        z_um = data['z_um']
    return view_field(field, axes_um, z_um, show=show)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Browse saved field slices with x/y/z sliders (no simulation).')
    parser.add_argument('npz', help='Path to a saved 2D transverse fields.npz')
    args = parser.parse_args(argv)
    view_npz(args.npz)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
