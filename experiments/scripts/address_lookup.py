import json
import requests


def get_fips_from_address(address: str):
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return {"error": "No match found for that address."}

        match = matches[0]

        coords = match["coordinates"]
        geos = match["geographies"]["Census Tracts"][0]

        state_fips = geos["STATE"]
        county_fips = geos["COUNTY"]
        tract_fips = geos["TRACT"]
        full_geoid = geos["GEOID"]

        return {
            "state_fips": state_fips,
            "county_fips": county_fips,
            "tract_fips": tract_fips,
            "full_geoid": full_geoid,
            "lat": coords["y"],
            "lon": coords["x"],
        }

    except requests.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


if __name__ == "__main__":
    test_address = "420 w. 118th, ny, ny"
    print(f"Looking up FIPS info for: {test_address}\n")
    result = get_fips_from_address(test_address)
    print(json.dumps(result, indent=2))
