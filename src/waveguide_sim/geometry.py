"""Physical-coordinate geometry and launch helpers. All lengths are micrometres."""
from dataclasses import dataclass
from typing import Callable
import numpy as np


@dataclass(frozen=True)
class Waveguide:
    """A core mask/weight in [0,1], including arbitrary z-dependent shapes.

    shape(z_um, coordinates) returns a broadcastable mask or graded weight.
    Multiple cores/materials can instead be described by an absolute-index callback.
    Indices supplied here are assumed unless independently calibrated.
    """
    shape: Callable
    core_index: float
    cladding_index: float

    def __post_init__(self):
        if not callable(self.shape):
            raise ValueError('shape must be callable')
        if any(isinstance(n, bool) or not np.isreal(n) or not np.isfinite(n) or n <= 0
               for n in (self.core_index, self.cladding_index)):
            raise ValueError('indices must be positive finite real numbers')

    def __call__(self, z_um, coordinates):
        weight = np.asarray(self.shape(z_um, coordinates))
        if not np.isrealobj(weight) or not np.all(np.isfinite(weight)) or np.any((weight < 0) | (weight > 1)):
            raise ValueError('shape weights must be finite real values in [0,1]')
        return self.cladding_index + (self.core_index-self.cladding_index)*weight


def gaussian_beam(*, waists_um, center_um=None, transverse_k_per_um=None, amplitude=1.0):
    """Return launch(coordinates); waists are field 1/e radii. No normalization.

    transverse_k_per_um sets the phase gradient directly, in radians / micrometre.
    """
    waist = np.asarray(waists_um, dtype=float)
    center = np.zeros_like(waist) if center_um is None else np.asarray(center_um, dtype=float)
    k = np.zeros_like(waist) if transverse_k_per_um is None else np.asarray(transverse_k_per_um, dtype=float)
    if (waist.ndim != 1 or len(waist) not in (1,2) or center.shape != waist.shape or k.shape != waist.shape
            or not all(np.all(np.isfinite(a)) for a in (waist,center,k)) or np.any(waist <= 0)
            or not np.isscalar(amplitude) or not np.isfinite(amplitude) or amplitude == 0):
        raise ValueError('invalid Gaussian launch parameters')

    def launch(coordinates):
        if len(coordinates) != len(waist):
            raise ValueError('launch dimension mismatch')
        return amplitude*np.exp(-sum(((q-c)/w)**2 for q,c,w in zip(coordinates,center,waist))
                                + 1j*sum(q*t for q,t in zip(coordinates,k)))
    return launch
