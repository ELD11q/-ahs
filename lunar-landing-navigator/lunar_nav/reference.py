"""Independent reference data used to validate the navigator.

1. NASA's nine Artemis III candidate regions (NASA, Oct 2024; NTRS 20250011660).
   NASA does not publish region polygons, so each is located by the IAU
   feature it is named after (IAU Gazetteer of Planetary Nomenclature). The
   regions sit on the rim/peak *near* that feature, so expect offsets of a few
   km to tens of km.
2. Top-20 landing points from Peña-Asensio, Neira-Acosta & Sánchez-Lozano
   (2024), "Evaluating potential landing sites for the Artemis III mission
   using a multi-criteria decision making approach", arXiv:2406.19863,
   Table 3 (GIS + TOPSIS over NASA's 13 regions).
"""

# name, lat, lon(E), IAU feature used, feature diameter (km, IAU), note
NASA_ARTEMIS3_REGIONS = [
    ("Peak near Cabeus B", -82.26, -54.58, "Cabeus B (crater)", 59.62, "region is a peak near this crater"),
    ("Haworth", -87.45, -5.17, "Haworth (crater)", 51.42, "region is on/near the crater"),
    ("Malapert Massif", -85.98, -1.67, "Mons Malapert", 67.0, ""),
    ("Mons Mouton Plateau", -84.60, 31.00, "Mons Mouton", 130.0, "plateau on the massif"),
    ("Mons Mouton", -84.60, 31.00, "Mons Mouton", 130.0, ""),
    ("Nobile Rim 1", -85.28, 53.27, "Nobile (crater)", 79.27, "region is on the rim"),
    ("Nobile Rim 2", -85.28, 53.27, "Nobile (crater)", 79.27, "region is on the rim"),
    ("de Gerlache Rim 2", -88.48, -88.34, "de Gerlache (crater)", 32.71, "region is on the rim"),
    ("Slater Plain", -88.08, 111.29, "Slater (crater)", 25.12, "plain next to the crater"),
]


def match_radius_km(diameter_km: float) -> float:
    """How far from the feature centre a region named after it can lie:
    the feature radius + 10 km, between 20 and 50 km."""
    return float(min(50.0, max(20.0, diameter_km / 2 + 10.0)))

# Other south-polar landmarks (IAU Gazetteer), for map context.
LANDMARKS = [
    ("Shackleton", -89.67, 129.78), ("Shoemaker", -88.14, 45.91), ("Faustini", -87.18, 84.31),
    ("Sverdrup", -88.32, -153.39), ("de Gerlache", -88.48, -88.34), ("Haworth", -87.45, -5.17),
    ("Nobile", -85.28, 53.27), ("Malapert", -85.00, 11.40), ("Mons Malapert", -85.98, -1.67),
    ("Mons Mouton", -84.60, 31.00), ("Amundsen", -84.44, 83.07), ("Cabeus", -85.33, -42.13),
    ("Slater", -88.08, 111.29), ("Kocher", -84.47, -134.02), ("Mons Kocher", -85.46, -118.06),
    ("Mons Cabeus", -83.67, -36.16),
]

# (point id, region code, TOPSIS R_i, lat, lon E) — arXiv:2406.19863 Table 3
TOPSIS_TOP20 = [
    (358, "DM2", 0.6916, -84.20156, 60.69989),
    (356, "DM2", 0.6869, -84.20075, 60.68570),
    (357, "DM2", 0.6711, -84.19932, 60.69366),
    (354, "DM2", 0.6684, -84.19995, 60.67151),
    (350, "DM2", 0.6610, -84.19914, 60.65732),
    (355, "DM2", 0.6487, -84.19851, 60.67947),
    (352, "DM2", 0.6455, -84.19627, 60.67326),
    (351, "DM2", 0.6408, -84.19771, 60.66529),
    (353, "DM2", 0.6220, -84.19484, 60.68122),
    (1121, "DM1", 0.5653, -84.19184, 67.22904),
    (1122, "DM1", 0.5649, -84.19188, 67.21955),
    (995, "DM2", 0.5353, -84.08411, 55.55430),
    (661, "Site04", 0.5294, -89.95919, 135.81846),
    (998, "DM2", 0.4916, -84.03792, 56.84740),
    (1223, "Site07", 0.4689, -89.00506, 125.30930),
    (744, "LM7", 0.4567, -88.08695, 98.35549),
    (1043, "DM2", 0.4373, -83.76770, 56.65906),
    (657, "Site04", 0.4179, -89.92191, 78.73752),
    (726, "SL2", 0.3907, -88.51566, -61.16732),
    (1005, "Site07", 0.3714, -89.01176, 131.27902),
]

TOPSIS_REGION_NAMES = {
    "DM1": "Amundsen Rim", "DM2": "Nobile Rim 2", "Haworth": "Haworth", "LM7": "Faustini Rim A",
    "Site01": "Connecting Ridge", "Site04": "Site 004 (near the pole)", "Site06": "Nobile Rim 1",
    "Site07": "Peak Near Shackleton", "Site11": "de Gerlache Rim 1", "Site20": "Leibnitz Beta Plateau",
    "Site23": "Malapert Massif", "Site42": "de Gerlache-Kocher Massif", "SL2": "de Gerlache Rim 2",
    "SL3": "Connecting Ridge Extension",
}


def latlon_to_xy(lat, lon, radius_m=1_737_400.0):
    """South polar stereographic (true scale at the pole), lon 0 up."""
    import math
    c = math.radians(90.0 + lat)  # colatitude from the S pole
    rho = 2 * radius_m * math.tan(c / 2)
    return rho * math.sin(math.radians(lon)), rho * math.cos(math.radians(lon))
