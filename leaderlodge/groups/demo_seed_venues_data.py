"""Plain venue catalog for demo seeds (no Django imports).

Used by ``demo_seed_locations`` (runtime geo) and
``tools/generate_new_game_demo_seeds.py``. Keep about 75% US venues.
"""

from __future__ import annotations

# (name, lat, lon, city, state, country) — country is ISO 3166-1 alpha-2.
DEMO_SEED_VENUES: tuple[tuple[str, float, float, str, str, str], ...] = (
    # United States (12 of 16 = 75%)
    ("Freedom Park, Palm Desert, CA", 33.7222, -116.3745, "Palm Desert", "CA", "US"),
    ("Memorial Park, Los Angeles, CA", 34.0647, -118.2845, "Los Angeles", "CA", "US"),
    (
        "Golden Gate Park, San Francisco, CA",
        37.7694,
        -122.4862,
        "San Francisco",
        "CA",
        "US",
    ),
    ("Balboa Park, San Diego, CA", 32.7341, -117.1446, "San Diego", "CA", "US"),
    ("Green Lake, Seattle, WA", 47.6806, -122.3283, "Seattle", "WA", "US"),
    ("Cole Park, Dallas, TX", 32.8207, -96.7860, "Dallas", "TX", "US"),
    ("Pan American Park, Austin, TX", 30.2608, -97.7086, "Austin", "TX", "US"),
    ("Central Park, New York, NY", 40.7829, -73.9654, "New York", "NY", "US"),
    ("Millennium Park, Chicago, IL", 41.8826, -87.6226, "Chicago", "IL", "US"),
    ("Boston Common, Boston, MA", 42.3551, -71.0656, "Boston", "MA", "US"),
    ("Piedmont Park, Atlanta, GA", 33.7866, -84.3729, "Atlanta", "GA", "US"),
    (
        "Liberty State Park, Jersey City, NJ",
        40.7040,
        -74.0495,
        "Jersey City",
        "NJ",
        "US",
    ),
    # Outside the United States (4 of 16 = 25%)
    ("Hyde Park, London, UK", 51.5073, -0.1657, "London", "", "GB"),
    ("Parc du Champ de Mars, Paris, France", 48.8556, 2.2986, "Paris", "", "FR"),
    ("Stanley Park, Vancouver, Canada", 49.3017, -123.1417, "Vancouver", "BC", "CA"),
    ("Yoyogi Park, Tokyo, Japan", 35.6715, 139.6950, "Tokyo", "", "JP"),
)
