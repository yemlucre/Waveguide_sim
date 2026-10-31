"""Theoretical 1+1D scalar paraxial solver. All internal lengths are micrometres.

No device, UI, project-file or agent dependencies. Requires NumPy only.
"""
from dataclasses import asdict, dataclass, replace
import math
import numpy as np

MODEL_VERSION = "slab-ssfft-1"


@dataclass(frozen=True)
class Parameters:
    wavelength_um: float = 0.78
    background_index: float = 1.45
    delta_index: float = 0.003
    radius_um: float = 2.5  # 1/e radius of Gaussian INDEX increment, not mode size
    separation_um: float = 12.0  # centre-to-centre
    window_um: float = 120.0
    points: int = 512
    step_um: float = 2.0
    length_um: float = 20000.0

    def validate(self):
        for key, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive")
        if not isinstance(self.points, int) or not 128 <= self.points <= 2048 or self.points % 2:
            raise ValueError("points must be an even integer in [128, 2048]")
        if self.delta_index / self.background_index > 0.01:
            raise ValueError("This weak-guidance example requires delta_index/background_index <= 0.01")
        if self.separation_um < 2 * self.radius_um:
            raise ValueError("separation_um must be >= 2 * radius_um")
        if self.window_um < self.separation_um + 12 * self.radius_um:
            raise ValueError("window too small for the guides and boundary margins")
        if self.window_um / self.points > self.radius_um / 6:
            raise ValueError("resolve the index radius with at least 6 grid cells")
        if self.length_um / self.step_um > 100000:
            raise ValueError("maximum 100000 propagation steps")
        return self


def grid(p):
    p.validate()
    dx = p.window_um / p.points
    return (np.arange(p.points) + 0.5 - p.points / 2) * dx


def index_increment(p, x, single=False):
    left = np.exp(-((x + p.separation_um / 2) / p.radius_um) ** 2)
    right = 0 if single else np.exp(-((x - p.separation_um / 2) / p.radius_um) ** 2)
    return p.delta_index * (left + right)


def potential(p, dn):
    k0 = 2 * np.pi / p.wavelength_um
    return -k0 * ((p.background_index + dn) ** 2 - p.background_index ** 2) / (2 * p.background_index)


def eigensystem(p, single=False):
    """Fourier collocation Hamiltonian, same periodic transverse operator as BPM.

    Returns eigenvalues (1/um), orthonormal fields (integral |u|^2 dx = 1).
    Dense solve is intentional for this bounded educational problem.
    """
    x = grid(p)
    dx = p.window_um / p.points
    k = 2 * np.pi * np.fft.fftfreq(p.points, dx)
    kinetic = k * k / (2 * (2 * np.pi / p.wavelength_um) * p.background_index)
    matrix = np.fft.ifft(kinetic[:, None] * np.fft.fft(np.eye(p.points), axis=0), axis=0).real
    matrix[np.diag_indices(p.points)] += potential(p, index_increment(p, x, single))
    values, vectors = np.linalg.eigh(matrix)
    return values, vectors / np.sqrt(dx)


def launch_mode(p):
    values, vectors = eigensystem(p, single=True)
    if values[0] >= 0:
        raise ValueError("No bound input mode found")
    return vectors[:, 0].astype(complex)


def propagate(p, initial=None, dn=None, sample_count=401):
    """Strang split-step FFT: half potential / diffraction / half potential.

    Periodic boundaries; no absorber, physical loss, polarization or reflection.
    Input is normalized once. Never renormalize output to hide power errors.
    Return full complex sampled fields and diagnostics, including boundary power.
    Synchronous; exceptions propagate, no retries/timeouts/device side effects.
    """
    x = grid(p)
    dx = p.window_um / p.points
    field = launch_mode(p) if initial is None else np.array(initial, dtype=complex, copy=True)
    if field.shape != x.shape or not np.all(np.isfinite(field)):
        raise ValueError("initial must contain one finite complex amplitude per grid point")
    norm = np.sum(abs(field) ** 2) * dx
    if norm <= 0 or not np.isfinite(norm):
        raise ValueError("initial power must be finite and nonzero")
    field /= np.sqrt(norm)
    dn = index_increment(p, x) if dn is None else np.asarray(dn, dtype=float)
    if dn.shape != x.shape or not np.all(np.isfinite(dn)) or np.any(dn < 0) or np.max(dn) > 0.02 * p.background_index:
        raise ValueError("dn must be a finite nonnegative weak index profile on the grid")
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 2 or sample_count > 2001:
        raise ValueError("sample_count must be an integer in [2, 2001]")
    count = max(1, math.ceil(p.length_um / p.step_um))
    dz = p.length_um / count
    selected = set(np.linspace(0, count, min(count + 1, sample_count), dtype=int))
    k = 2 * np.pi * np.fft.fftfreq(p.points, dx)
    diffraction = np.exp(-1j * dz * k * k / (2 * (2 * np.pi / p.wavelength_um) * p.background_index))
    half = np.exp(-0.5j * dz * potential(p, dn))
    fields, zs = [field.copy()], [0.0]
    max_drift, max_edge = 0.0, 0.0
    edge = abs(x) >= p.window_um * 0.4
    max_edge = float(np.sum(abs(field[edge]) ** 2) * dx)
    for i in range(1, count + 1):
        field = half * np.fft.ifft(diffraction * np.fft.fft(half * field))
        power = abs(field) ** 2 * dx
        max_drift = max(max_drift, abs(float(power.sum()) - 1))
        max_edge = max(max_edge, float(power[edge].sum()))
        if i in selected:
            fields.append(field.copy())
            zs.append(i * dz)
    fields = np.array(fields)
    powers = abs(fields) ** 2 * dx
    return dict(x_um=x, z_um=np.array(zs), fields=fields,
                right_power=powers[:, x > 0].sum(axis=1),
                left_power=powers[:, x < 0].sum(axis=1),
                max_power_drift=max_drift, max_edge_power=max_edge, actual_step_um=dz)


def find_design(base, separations, target=0.5):
    """Bounded scan; choose earliest first crossing among supplied separations.

    Metric is right HALF-SPACE power / input power, not output-port efficiency.
    A target not crossed in the allowed length returns no candidate for that gap.
    """
    if not math.isfinite(target) or not 0 < target < 1:
        raise ValueError("target must be in (0, 1)")
    separations = list(separations)
    if not separations or len(separations) > 12:
        raise ValueError("provide 1..12 separation candidates")
    runs, rows = [], []
    for separation in separations:
        p = replace(base, separation_um=separation).validate()
        run = propagate(p)
        right = run["right_power"]
        crossing = np.flatnonzero((right[:-1] < target) & (right[1:] >= target))
        length = None
        if len(crossing):
            j = crossing[0]
            length = float(np.interp(target, right[j:j+2], run["z_um"][j:j+2]))
        rows.append(dict(separation_um=separation, first_target_length_um=length,
                         max_right_power=float(right.max()),
                         max_power_drift=run["max_power_drift"], max_edge_power=run["max_edge_power"]))
        runs.append(run)
    candidates = [(i, r) for i, r in enumerate(rows) if r["first_target_length_um"] is not None]
    if not candidates:
        return dict(status="target_not_reached", target=target, scan=rows, selected_index=None), runs
    i, best = min(candidates, key=lambda pair: pair[1]["first_target_length_um"])
    chosen = replace(base, separation_um=best["separation_um"], length_um=best["first_target_length_um"])
    final = propagate(chosen, sample_count=2)
    return dict(status="candidate_found", target=target, scan=rows, selected_index=i,
                selected_parameters=asdict(chosen),
                actual_right_power=float(final["right_power"][-1]),
                target_error=float(abs(final["right_power"][-1] - target))), runs
