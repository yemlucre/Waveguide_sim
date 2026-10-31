"""Physical transverse grid and fixed RK4 refinement protocol; lengths in um."""
from dataclasses import dataclass, replace
import math
import numpy as np


@dataclass(frozen=True)
class Grid:
    wavelength_um: float = 0.78
    background_index: float = 1.45
    windows_um: tuple = (64., 64.)
    points: tuple = (128, 128)
    length_um: float = 500.
    step_um: float = 2.

    def validate(self):
        for name in ('wavelength_um', 'background_index', 'length_um', 'step_um'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if len(self.points) not in (1,2) or len(self.windows_um) != len(self.points):
            raise ValueError('one or two transverse axes required')
        for n,w in zip(self.points,self.windows_um):
            if type(n) is not int or not 32 <= n <= 1024 or n % 4:
                raise ValueError('points per axis must be multiples of 4 in [32,1024]')
            if isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or w <= 0:
                raise ValueError('window_um must be finite and positive')
        if math.ceil(self.length_um/self.step_um) > 100000:
            raise ValueError('maximum 100000 steps')
        return self


def axes(grid):
    grid.validate()
    return tuple((np.arange(n)-n//2)*w/n for n,w in zip(grid.points,grid.windows_um))


def refinement_grids(grid):
    """Base, half longitudinal step, half transverse spacing, larger window."""
    return [grid, replace(grid,step_um=grid.step_um/2),
            replace(grid,points=tuple(2*n for n in grid.points)),
            replace(grid,points=tuple(3*n//2 for n in grid.points),
                    windows_um=tuple(1.5*w for w in grid.windows_um))]
