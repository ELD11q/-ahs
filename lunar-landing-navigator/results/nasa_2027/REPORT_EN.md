# Landing-site report: lunar south pole (official NASA data, 2027 launch windows)

## Data

| Layer | Product | Source |
|---|---|---|
| dem | `LDEM_80S_80MPP_ADJ.TIF`: LOLA elevation, 80-90S, 80 m/px (m above 1737.4 km sphere) | Barker et al. 2023 |
| slope | `LDSM_80S_80MPP_ADJ.TIF`: LOLA slope, 80-90S, 80 m/px (deg) | Barker et al. 2023 |
| roughness | `LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF`: LOLA roughness at 100 m baseline, 50 m/px (m) | Barker et al. 2023 |
| sun | `AVGVISIB_75S_120M_201608.TIF`: Average solar visibility over 18.6 yr, 75-90S, 120 m/px (0-1) | Mazarico et al. 2011 |
| earth | `AVGVISIB_75S_120M_201608_EARTH.TIF`: Average Earth visibility over 18.6 yr, 75-90S, 120 m/px (0-1) | Mazarico et al. 2011 |
| psr | `LPSR_75S_120M_201608.TIF`: Permanently shadowed regions, 75-90S, 120 m/px (1 = PSR) | Mazarico et al. 2011 |

Analysis grid: 6000×6000 pixels at 80 m (±240 km around the pole), inside the Artemis Exploration Zone (6° from the pole).

Classes: 🟩 safe 8.2% · 🟨 marginal 5.0% · 🟥 unsafe / outside the zone 86.8% · 🟦 permanent shadow 7.5% · craters detected: 20,564

## Top 9 regions

| # | Final score | Terrain score | Fully-lit windows 2027 | Best window (UTC) | Slope | Sunlight (NASA) | Earth visibility (NASA) | Nearest permanent shadow | Coordinates | Nearby NASA region |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.992 | 0.915 | 36% | 2027-01-09 06:00 | 0.47° | 50% | 81% | 2.33 km | 85.083°S, 37.20°E | Mons Mouton / Mons Mouton Plateau / Nobile Rim 1 / Nobile Rim 2 |
| 2 | 0.894 | 0.901 | 28% | 2027-03-10 00:00 | 0.65° | 49% | 33% | 1.62 km | 85.009°S, 142.99°E | — |
| 3 | 0.882 | 0.922 | 26% | 2027-01-13 06:00 | 0.24° | 49% | 83% | 1.19 km | 84.112°S, 32.66°E | Mons Mouton / Mons Mouton Plateau |
| 4 | 0.876 | 0.918 | 25% | 2027-03-09 18:00 | 0.18° | 48% | 33% | 1.66 km | 85.343°S, 127.64°E | — |
| 5 | 0.866 | 0.928 | 24% | 2027-01-13 06:00 | 0.58° | 48% | 87% | 2.17 km | 84.578°S, 27.00°E | Mons Mouton / Mons Mouton Plateau |
| 6 | 0.857 | 0.907 | 24% | 2027-01-12 00:00 | 0.29° | 52% | 80% | 0.62 km | 84.377°S, 39.22°E | Mons Mouton / Mons Mouton Plateau / Nobile Rim 1 / Nobile Rim 2 |
| 7 | 0.852 | 0.900 | 24% | 2027-02-10 12:00 | 0.29° | 46% | 34% | 2.15 km | 84.227°S, 109.10°E | — |
| 8 | 0.843 | 0.912 | 23% | 2027-03-09 12:00 | 0.32° | 46% | 33% | 0.56 km | 84.763°S, 134.47°E | — |
| 9 | 0.838 | 0.899 | 23% | 2027-06-22 18:00 | 0.57° | 51% | 56% | 0.64 km | 86.012°S, 290.05°E | — |

## Validation

### 1) Our illumination model vs NASA's maps

We computed the 18.6-year average ourselves (horizon ray-tracing on LOLA + real Sun and Earth positions) for 111,556 points × 13,588 epochs and compared it with Mazarico et al. (2011):

| | Correlation r | Mean error | Bias | Error < 5 points | Error < 10 points |
|---|---|---|---|---|---|
| Sun | 0.909 | 3.7 points | -0.6 points | 78% | 91% |
| Earth | 0.941 | 5.8 points | -2.3 points | 63% | 84% |

### 2) Independent study (arXiv:2406.19863, TOPSIS)

- 70% of their top 20 points fall in our top 10% (median: above 93% of the area).
- Their best point (#358, Nobile Rim 2) scores 0.763 in our map, above 94% of the area, classified safe.

| Point | Region | R (TOPSIS) | Our score | Our percentile | Slope |
|---|---|---|---|---|---|
| 358 | Nobile Rim 2 | 0.6916 | 0.763 | 94% | 2.64° |
| 356 | Nobile Rim 2 | 0.6869 | 0.752 | 93% | 2.68° |
| 357 | Nobile Rim 2 | 0.6711 | 0.752 | 93% | 2.68° |
| 354 | Nobile Rim 2 | 0.6684 | 0.752 | 93% | 2.68° |
| 350 | Nobile Rim 2 | 0.661 | 0.745 | 92% | 2.61° |
| 355 | Nobile Rim 2 | 0.6487 | 0.752 | 93% | 2.68° |
| 352 | Nobile Rim 2 | 0.6455 | 0.785 | 96% | 1.54° |
| 351 | Nobile Rim 2 | 0.6408 | 0.745 | 92% | 2.61° |
| 353 | Nobile Rim 2 | 0.622 | 0.8 | 97% | 1.33° |
| 1121 | Amundsen Rim | 0.5653 | 0.866 | 100% | 0.42° |
| 1122 | Amundsen Rim | 0.5649 | 0.824 | 98% | 1.8° |
| 995 | Nobile Rim 2 | 0.5353 | 0.11 | 12% | 17.32° |
| 661 | Site 004 (near the pole) | 0.5294 | 0.099 | 7% | 30.28° |
| 998 | Nobile Rim 2 | 0.4916 | 0.866 | 100% | 1.57° |
| 1223 | Peak Near Shackleton | 0.4689 | 0.884 | 100% | 0.94° |
| 744 | Faustini Rim A | 0.4567 | 0.728 | 90% | 1.58° |
| 1043 | Nobile Rim 2 | 0.4373 | 0.263 | 68% | 1.16° |
| 657 | Site 004 (near the pole) | 0.4179 | 0.096 | 6% | 28.93° |
| 726 | de Gerlache Rim 2 | 0.3907 | 0.152 | 42% | 20.07° |
| 1005 | Peak Near Shackleton | 0.3714 | 0.221 | 67% | 0.67° |

### 3) NASA's nine Artemis III regions (October 2024)

- 4/9 NASA regions have one of our nine regions nearby; 5/9 have one of our 13 candidates.
- NASA does not publish region boundaries, so each region is placed at the centre of the feature it is named after (IAU gazetteer), with a match radius of the feature radius + 10 km (20–50 km).

| NASA region | Feature | Match radius | Nearest of ours | Ours inside | Best nearby (percentile) |
|---|---|---|---|---|---|
| Peak near Cabeus B | Cabeus B (crater) | 40 km | 122.7 km | — | 68% |
| Haworth | Haworth (crater) | 36 km | 105.8 km | — | 100% |
| Malapert Massif | Mons Malapert | 44 km | 82.0 km | — | 100% |
| Mons Mouton Plateau | Mons Mouton | 50 km | 11.5 km | #1, #3, #5, #6 | 100% |
| Mons Mouton | Mons Mouton | 50 km | 11.5 km | #1, #3, #5, #6 | 100% |
| Nobile Rim 1 | Nobile (crater) | 50 km | 41.3 km | #1, #6 | 100% |
| Nobile Rim 2 | Nobile (crater) | 50 km | 41.3 km | #1, #6 | 100% |
| de Gerlache Rim 2 | de Gerlache (crater) | 26 km | 78.6 km | — | 100% |
| Slater Plain | Slater (crater) | 23 km | 87.0 km | — | 100% |

## Notes and limits

- NASA's 18.6-year averages include polar winters, so they are lower than a summer mission window; this is why we compute the real 2027 windows for every candidate and give them 40% of the final ranking.
- A fully-lit window = 6.5 consecutive days with more than half of the Sun's disc above the horizon every hour, for an observer 2 m above the ground.
- NASA's regions also depend on constraints we do not model: the NRHO orbit, launch trajectories, the SpaceX HLS design, and high-resolution LROC NAC images of boulders. Differences in some regions are expected.
- Roughness comes from LOLA (100 m baseline); smaller boulders need NAC images + YOLO.

## References

- Barker, M.K. et al. (2023). A New View of the Lunar South Pole from LOLA. PGDA product 90.
- Mazarico, E. et al. (2011). Illumination conditions of the lunar polar regions using LOLA topography. Icarus 211.
- Peña-Asensio, E., Neira-Acosta, Á.-S., Sánchez-Lozano, J.M. (2024). arXiv:2406.19863.
- NASA (2025). Artemis III Site Selection Update: Downselection From Thirteen to Nine Candidate Regions. NTRS 20250011660.
- Archinal, B.A. et al. (2011). Report of the IAU WGCCRE: 2009. Celest. Mech. Dyn. Astr. 109.
- IAU/USGS Gazetteer of Planetary Nomenclature.
