import numpy as np
import pytest

from lunar_nav import illumination, terrain
from lunar_nav.config import Config
from lunar_nav.data import Scene, synthetic_south_pole
from lunar_nav.pipeline import run
from lunar_nav.regions import pixel_to_latlon
from lunar_nav.scoring import GREEN, RED


def test_slope_of_known_plane():
    px = 20.0
    rows, cols = np.indices((50, 50))
    dem = cols * px * np.tan(np.deg2rad(12.0))  # 12 deg tilted plane
    s = terrain.slope_deg(dem, px)
    assert np.allclose(s[5:-5, 5:-5], 12.0, atol=0.01)


def test_flat_terrain_has_no_horizon_and_is_lit_at_pole():
    dem = np.zeros((40, 40), np.float32)
    hor = illumination.horizon_map(dem, 100.0, n_azimuths=8, max_distance_m=2000)
    assert hor.max() <= 0.0  # curvature only pulls the horizon down
    sc = Scene(dem, 100.0, (20.0, 20.0))
    x, y = sc.xy_m()
    # Southern summer: declination >0 -> sun is up at the pole on flat ground.
    t = np.linspace(80, 90, 20)
    assert illumination.illumination_fraction(hor, x, y, t).min() > 0.9


def test_deep_pit_floor_is_permanently_shadowed():
    rows, cols = np.indices((80, 80))
    r = np.hypot(rows - 40, cols - 40)
    dem = np.where(r < 15, -2000.0, 0.0).astype(np.float32)
    hor = illumination.horizon_map(dem, 100.0, n_azimuths=16, max_distance_m=5000)
    sc = Scene(dem, 100.0, (40.0, 40.0))
    x, y = sc.xy_m()
    annual = illumination.illumination_fraction(hor, x, y, np.linspace(0, 346, 200))
    assert annual[40, 40] < 0.005
    assert annual[5, 5] > 0.3


def test_latlon_of_pole_is_minus_90():
    lat, _ = pixel_to_latlon(10, 10, (10, 10), 100.0)
    assert lat == pytest.approx(-90.0)
    lat, lon = pixel_to_latlon(0, 10, (10, 10), 1000.0)  # 10 km "up" = lon 0
    assert -90 < lat < -89.6 and lon == pytest.approx(0.0)


def test_mission_window_keeps_sun_and_earth_up():
    start = illumination.default_mission_start(6.5)
    t = np.arange(start, start + 6.5, 0.25)
    _, dec = illumination.sun_state(t)
    _, elat = illumination.earth_state(t)
    assert dec.mean() > 1.0
    assert (elat < 0).mean() > 0.6


@pytest.fixture(scope="module")
def demo_result():
    scene = synthetic_south_pole(200, pixel_size_m=150.0, seed=3)
    cfg = Config(n_azimuths=12, annual_samples=120, horizon_max_distance_m=15_000)
    cfg.constraints.region_size_m = 6_000
    cfg.constraints.edge_margin_m = 1_500
    return run(scene, cfg, log=lambda *_: None)


def test_pipeline_end_to_end(demo_result):
    res = demo_result
    assert res.score.shape == res.scene.shape
    assert 0 < len(res.regions) <= 9
    scores = [r.score for r in res.regions]
    assert scores == sorted(scores, reverse=True)
    for r in res.regions:
        assert res.cls[r.best_row, r.best_col] != RED
        assert res.layers.slope[r.best_row, r.best_col] <= 10.0


def test_steep_areas_are_red(demo_result):
    res = demo_result
    assert np.all(res.cls[res.layers.slope > 10.0] == RED)
    assert np.all(res.cls[res.layers.psr] == RED)
    assert (res.cls == GREEN).any()


def test_html_export(tmp_path, demo_result):
    from lunar_nav.viz import write_html
    p = write_html(demo_result, tmp_path / "map.html")
    html = p.read_text(encoding="utf-8")
    assert "L.map(" in html and "data:image/png;base64" in html
    assert "cdnjs" not in html  # leaflet is inlined, works offline
