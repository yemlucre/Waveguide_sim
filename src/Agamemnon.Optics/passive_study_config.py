"""All optical-material choices are assumed_not_measured, no active heaters.

Edit this file for repeated design studies. Distances are centre-to-centre.
Reported geometry: SI Fig.3 / Table 1; half-cosine interpolation and row order
are a mathematical reconstruction, not the authors' exact CAD or chip matrix.
"""
from passive_lantern import Geometry, Material

GEOMETRY=Geometry()  # 8x8, 100 mm; 9 + 0.5 + 9 mm, row stagger 9.5 mm
PITCHES_UM=[12.,15.,18.]
MATERIAL_CASES=[
    ('基准',Material(radius_um=3.,delta_index=.003)),
    ('较窄波导',Material(radius_um=2.5,delta_index=.003)),
    ('较宽波导',Material(radius_um=3.5,delta_index=.003)),
    ('较低折射率增量',Material(radius_um=3.,delta_index=.002)),
    ('较高折射率增量',Material(radius_um=3.,delta_index=.004)),
]
INPUT_CHANNEL=27  # zero based, row 4 / column 4 in the 8x8 array
LOCAL_CHECK_PITCH_UM=15.
LOCAL_CHECK_LENGTH_UM=1000.
