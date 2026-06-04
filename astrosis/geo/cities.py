# city name -> (lat, lon)  ~85 cities across all continents

CITIES: dict[str, tuple[float, float]] = {
    # India
    "mumbai": (19.076, 72.8777),
    "delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    # US
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970),
    "san jose": (37.3382, -121.8863),
    "austin": (30.2672, -97.7431),
    "jacksonville": (30.3322, -81.6557),
    "san francisco": (37.7749, -122.4194),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "washington dc": (38.9072, -77.0369),
    "boston": (42.3601, -71.0588),
    "nashville": (36.1627, -86.7816),
    "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398),
    # Canada
    "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207),
    "montreal": (45.5017, -73.5673),
    # Europe
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050),
    "madrid": (40.4168, -3.7038),
    "rome": (41.9028, 12.4964),
    "moscow": (55.7558, 37.6173),
    "amsterdam": (52.3676, 4.9041),
    "brussels": (50.8503, 4.3517),
    "vienna": (48.2082, 16.3738),
    "stockholm": (59.3293, 18.0686),
    "oslo": (59.9139, 10.7522),
    "copenhagen": (55.6761, 12.5683),
    "dublin": (53.3498, -6.2603),
    "lisbon": (38.7223, -9.1393),
    "athens": (37.9838, 23.7275),
    "prague": (50.0755, 14.4378),
    "budapest": (47.4979, 19.0402),
    "warsaw": (52.2297, 21.0122),
    "helsinki": (60.1699, 24.9384),
    "zurich": (47.3769, 8.5417),
    "munich": (48.1351, 11.5820),
    "barcelona": (41.3874, 2.1686),
    "milan": (45.4642, 9.1900),
    "istanbul": (41.0082, 28.9784),
    # East Asia
    "tokyo": (35.6762, 139.6503),
    "osaka": (34.6937, 135.5023),
    "seoul": (37.5665, 126.9780),
    "beijing": (39.9042, 116.4074),
    "shanghai": (31.2304, 121.4737),
    "hong kong": (22.3193, 114.1694),
    "taipei": (25.0330, 121.5654),
    "bangkok": (13.7563, 100.5018),
    "singapore": (1.3521, 103.8198),
    "kuala lumpur": (3.1390, 101.6869),
    "manila": (14.5995, 120.9842),
    "jakarta": (-6.2088, 106.8456),
    "hanoi": (21.0278, 105.8342),
    "ho chi minh city": (10.8231, 106.6297),
    # South America
    "são paulo": (-23.5505, -46.6333),
    "sao paulo": (-23.5505, -46.6333),
    "rio de janeiro": (-22.9068, -43.1729),
    "buenos aires": (-34.6037, -58.3816),
    "lima": (-12.0464, -77.0428),
    "santiago": (-33.4489, -70.6693),
    "brasília": (-15.7975, -47.8919),
    "brasilia": (-15.7975, -47.8919),
    "bogotá": (4.7110, -74.0721),
    "bogota": (4.7110, -74.0721),
    "caracas": (10.4806, -66.9036),
    "quito": (-0.1807, -78.4678),
    # Africa
    "cairo": (30.0444, 31.2357),
    "lagos": (6.5244, 3.3792),
    "johannesburg": (-26.2041, 28.0473),
    "nairobi": (-1.2921, 36.8219),
    "accra": (5.6037, -0.1870),
    "cape town": (-33.9249, 18.4241),
    "casablanca": (33.5731, -7.5898),
    "addis ababa": (9.0320, 38.7469),
    "algiers": (36.7538, 3.0588),
    "dakar": (14.7167, -17.4677),
    # Australia / Oceania
    "sydney": (-33.8688, 151.2093),
    "melbourne": (-37.8136, 144.9631),
    "brisbane": (-27.4698, 153.0251),
    "perth": (-31.9505, 115.8605),
    "auckland": (-36.8485, 174.7633),
    # Middle East
    "dubai": (25.2048, 55.2708),
    "riyadh": (24.7136, 46.6753),
    "tehran": (35.6892, 51.3890),
    "baghdad": (33.3152, 44.3661),
    "tel aviv": (32.0853, 34.7818),
    "doha": (25.2854, 51.5310),
    # Mexico / Central America
    "mexico city": (19.4326, -99.1332),
}


def resolve_location(city_or_lat, lon=None):
    if isinstance(city_or_lat, str):
        key = city_or_lat.strip().lower()
        if key in CITIES:
            lat, lng = CITIES[key]
            return lat, lng, key
        from difflib import get_close_matches

        matches = get_close_matches(key, CITIES.keys(), n=5, cutoff=0.3)
        suggestion = ""
        if matches:
            suggestion = (
                "\nDid you mean: " + ", ".join(m.title() for m in matches) + "?"
            )
        raise ValueError(
            f"City '{city_or_lat}' not found in database.{suggestion}\n"
            f"Use --lat/--lon directly for custom coordinates."
        )

    if lon is None:
        raise ValueError("--lon is required when --lat is provided.")

    return float(city_or_lat), float(lon), "custom"
