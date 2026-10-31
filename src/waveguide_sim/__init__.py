"""Waveguide geometry + complex launch -> sampled paraxial field via RK4."""
from .grid import Grid, axes
from .geometry import Waveguide, gaussian_beam
from .solver import Result, simulate, check_convergence

__version__ = "0.2.0"
__all__ = ["Grid", "axes", "Waveguide", "gaussian_beam", "Result", "simulate", "check_convergence"]
