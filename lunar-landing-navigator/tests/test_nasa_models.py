"""Physics checks for the real-data engine (no NASA download needed)."""
import numpy as np
import pytest

from lunar_nav import ephemeris, illumination, sunmodel
from lunar_nav.reference import NASA_ARTEMIS3_REGIONS, TOPSIS_TOP20, latlon_to_xy, match_radius_km
from lunar_nav.regions import pixel_to_latlon


@pytest.fixture(scope="module")
def year_vectors():
    t = ephemeris.time_grid("2027-01-01", 365, 6)
    return t, *ephemeris.sun_earth_vectors(t)


def test_ephemeris_matches_known_lunar_geometry(year_vectors):
    _, s, e = year_vectors
    slat, _ = ephemeris.subpoint_latlon(s)
    elat, elon = ephemeris.subpoint_latlon(e)
    elon = (elon + 180) % 360 - 180
    assert 1.45 < np.abs(slat).max() < 1.65          # lunar obliquity to the ecliptic, 1.54 deg
    assert 6.4 < np.abs(elat).max() < 7.0            # latitude libration ~6.7 deg
    assert 7.0 < np.abs(elon).max() < 8.2            # longitude libration ~7.9 deg
    d = np.linalg.norm(e, axis=1)
    assert 355_000 < d.min() < 360_000 and 404_000 < d.max() < 407_500  # perigee / apogee
    assert np.allclose(np.linalg.norm(s, axis=1), 1.496e8, rtol=0.03)


def test_numba_horizon_agrees_with_reference_implementation():
    rng = np.random.default_rng(1)
    from scipy import ndimage
    dem = ndimage.gaussian_filter(rng.standard_normal((90, 90)), 6) * 4000
    fast = sunmodel.horizon(dem, 100.0, slice(30, 60), slice(30, 60), 1, 16, 4000, 1.05)
    ref = illumination.horizon_map(dem.astype(np.float32), 100.0, 16, 4000)[:, 30:60, 30:60]
    # different sampling (bilinear vs nearest, step growth) -> agree to ~1 deg
    assert np.median(np.abs(fast - ref)) < 1.0


def test_flat_ground_at_pole_sees_sun_about_half_the_time(year_vectors):
    _, s, e = year_vectors
    hor = np.full((32, 1), -0.1)
    sun = sunmodel.mean_visibility(np.array([0.0]), np.array([0.0]), np.array([0.0]), hor, s, 0.53)
    earth = sunmodel.mean_visibility(np.array([0.0]), np.array([0.0]), np.array([0.0]), hor, e, 1.9)
    assert 0.4 < sun[0] < 0.6      # Sun +/-1.5 deg around the horizon
    assert 0.4 < earth[0] < 0.6    # Earth +/-6.7 deg around the horizon


def test_nearside_slope_sees_earth_more_than_farside(year_vectors):
    _, _, e = year_vectors
    hor = np.full((32, 2), -0.1)
    # 150 km from the pole toward lon 0 (near side) vs lon 180 (far side)
    x = np.array([0.0, 0.0])
    y = np.array([150_000.0, -150_000.0])
    v = sunmodel.mean_visibility(x, y, np.zeros(2), hor, e, 1.9)
    # 150 km = 4.95 deg colatitude: Earth sits at +/-4.95 deg, wobbling +/-6.8 deg
    assert v[0] > 0.65 and v[1] < 0.35 and v[0] - v[1] > 0.4


def test_stereographic_roundtrip():
    for lat, lon in [(-84.20156, 60.69989), (-89.67, 129.78), (-85.98, -1.67)]:
        x, y = latlon_to_xy(lat, lon)
        pole = (1000.0, 1000.0)
        lat2, lon2 = pixel_to_latlon(pole[0] - y / 80.0, pole[1] + x / 80.0, pole, 80.0)
        assert lat2 == pytest.approx(lat, abs=1e-6)
        d = (lon2 - lon) % 360
        assert min(d, 360 - d) == pytest.approx(0.0, abs=1e-6)


def test_reference_data_is_complete():
    assert len(NASA_ARTEMIS3_REGIONS) == 9
    assert len(TOPSIS_TOP20) == 20 and TOPSIS_TOP20[0][0] == 358
    assert all(20 <= match_radius_km(d) <= 50 for *_, d, _ in NASA_ARTEMIS3_REGIONS)
