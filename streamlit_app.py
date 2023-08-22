import base64
from io import BytesIO
import streamlit as st
import logging
from streamlit_folium import folium_static
import folium
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from math import radians, cos, sin, asin, sqrt, atan2, degrees
from PIL import Image
import csv
import random


log = logging.getLogger("streamlit")
log.setLevel(logging.DEBUG)

WHITE = (255, 255, 255)


@st.experimental_memo
def get_rotated_arrow(degrees: float) -> str:
    img = Image.open("./arrow.png").convert("RGB").resize((50, 50))
    result = img.rotate(-degrees, fillcolor=WHITE)
    buffered = BytesIO()
    result.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str


def haversine(
    lat1: float, lon1: float, lat2: float, lon2: float, units: str = "km"
) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)

    src: https://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points/4913653#4913653
    """
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # haversine formula
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371 if units == "km" else 3956  # Radius of earth in kilometers vs miles
    return c * r


def helper_haversine(row: pd.Series, target_lat: float, target_lon: float) -> float:
    row_lat, row_lon = row.centroid.y, row.centroid.x
    return haversine(row_lat, row_lon, target_lat, target_lon)


def get_flat_earth_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Flat-earther bearing

    For globe projected initial or final bearing: https://www.movable-type.co.uk/scripts/latlong.html
    # y = sin(lon2 - lon1) * cos(lat2)
    # x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(lon2 - lon1)
    # angle = atan2(x, y)
    # bearing = (degrees(angle) + 360) % 360  # in degrees
    """
    relative_lat = lat2 - lat1
    relative_lon = lon2 - lon1

    # Correct for crossing between negative and positive lon
    if relative_lon > 180:
        relative_lon = 180 - relative_lon
    if relative_lon < -180:
        relative_lon = -180 - relative_lon

    angle = atan2(relative_lon, relative_lat)

    return degrees(angle)


def helper_bearing(row: pd.Series, target_lat: float, target_lon: float) -> float:
    row_lat, row_lon = row.centroid.y, row.centroid.x
    return get_flat_earth_bearing(row_lat, row_lon, target_lat, target_lon)


MAX_DISTANCE = haversine(0, 0, 180, 0, "km")


def get_random_location() -> dict:
    with open('countries.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        chosen_row = random.choice(list(reader))
        # chosen_row = list(reader)[123]

    return chosen_row


@st.experimental_singleton
def get_all_locations() -> list:
    result = []

    with open('countries.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            result.append(row)

    return result


def get_distances(target: dict) -> list:
    locations = get_all_locations()

    for loc in locations:
        loc['distance'] = haversine(float(target["latitude"]), float(target["longitude"]), float(loc["latitude"]), float(loc["longitude"]))
        loc['direction'] = get_flat_earth_bearing(float(loc["latitude"]), float(loc["longitude"]), float(target["latitude"]), float(target["longitude"]))

    return locations


@st.experimental_memo
def get_country_names(all_locations: pd.DataFrame, locale_col: str = "name_en") -> list:
    names = all_locations[locale_col]
    return names.to_list()


def on_reset():
    st.session_state.pop(RANDOM_LOCATION)


def update_params():
    query_params = {LOCALE: st.session_state.get(LOCALE)}
    st.experimental_set_query_params(**query_params)


RANDOM_LOCATION = "random_location"
ALL_LOCATIONS = "all_locations"
NAMES = "names"
GUESSES = "guesses"
LOCALE = "locale"
DEFAULT_LOCALE = 'en'

def main():
    st.set_page_config(
        page_title="Alphabetical Worldle",
        page_icon="🌍",
        initial_sidebar_state="collapsed",
        
    )
    st.title("Guess the Country 'Worldle' Edition! 🌍")
    st.markdown(
        "Heavily inspired by [Worldle](https://worldle.teuteuf.fr/) guessing game. Worldle is heavily inspired by [Wordle](https://www.nytimes.com/games/wordle/index.html)."
    )
    query_params = st.experimental_get_query_params()
    locale_index = 3
    try:
        query_locales = query_params.get(LOCALE)
        locale_list = list(LOCALES.keys())
        locale_index = locale_list.index(query_locales[0])
    except (ValueError, TypeError):
        pass

    selected_locale = st.sidebar.selectbox("Locale", LOCALES, locale_index, key=LOCALE, on_change=update_params)
    update_params()
    locale_col = LOCALES.get(selected_locale, "en")
    if RANDOM_LOCATION not in st.session_state:
        random_location = get_random_location()
        all_locations = get_distances(random_location)
        guesses = []
        st.session_state[RANDOM_LOCATION] = random_location
        st.session_state[ALL_LOCATIONS] = all_locations
        st.session_state[GUESSES] = guesses
    else:
        random_location = st.session_state.get(RANDOM_LOCATION)
        all_locations = st.session_state.get(ALL_LOCATIONS)
        guesses = st.session_state.get(GUESSES)

    already_won = random_location["name"] in map(lambda loc: loc['name'], guesses)
    target_lat, target_lon = [random_location["latitude"], random_location["longitude"]]

    if already_won:
        st.balloons()
        st.success("You Guessed Correctly! 🥳")
        st.header(random_location["name"])
        # target_gdf = all_locations.loc[guesses, "geom"]
        m = folium.Map(
            location=[target_lat, target_lon],
            zoom_start=3,
        )
        # target_gdf.explore(m=m)
        folium_static(m, width=725)
        st.button("Play Again!", on_click=on_reset)

        st.stop()

    with st.expander("What is This?"):
        st.write(
            """\
### Streamlit Worldle
A geography guessing game with the following rules:

- You are trying to guess a randomly chosen mystery Country🌏
- If you guess the correct Country then you win 🥳
- If you guess incorrectly 6 times then you lose 😔
- Each incorrect guess will reveal information that might help you locate the mystery Country:
    - 📏 The `distance` that the center of the guess Country is away from the mystery Country
    - 🧭 The `direction` that points from the guess Country to the mystery Country (on a 2D map)
    - 🥈 The `proximity` percentage of how correct the guess was. A guess on the opposite side of the globe will be `0%` and the correct guess will be `100%`.
    - The `alphabetical direction`, whether the mystery country's name is earlier or later alphabetically than the one you guessed

### Data Sources and Caveats

- Just pulled [Google's countries.csv](https://developers.google.com/public-data/docs/canonical/countries_csv) and removed everything that isn't an actual country (possible there were some errors in this process).
- 📏 `distance` is the [Haversine Distance](https://en.wikipedia.org/wiki/Haversine_formula) calculated based on the [centroids](http://wiki.gis.com/wiki/index.php/Centroid) of the Countries calculated using GeoPandas
    - Countries that share a border will **NOT** have 0 km `distance`
    - The maximum `distance` possible is roughly `20000 km` (two points on opposite sides of the globe)
    - The `proximity` percentage is based on the maximum `distance`
"""
        )

    for display_guess in guesses:
        # display_guess_country = all_locations.loc[display_guess]
        display_guess_name = display_guess['name']
        distance = display_guess["distance"]
        distance_percentage = (1 - (distance / MAX_DISTANCE)) * 100
        direction = display_guess["direction"]

        alph_direction = 180
        if display_guess_name > random_location['name']:
            alph_direction = 0

        arrow_image = get_rotated_arrow(direction)
        alph_arrow_image = get_rotated_arrow(alph_direction)
        if int(distance_percentage) == 100:
            prox_icon = "🥇"
        elif int(distance_percentage) > 50:
            prox_icon = "🥈"
        else:
            prox_icon = "🥉"
        st.info(
            f"🌏 **{display_guess_name}** | 📏 **{distance:.0f}** km away | ![Direction {direction}](data:image/png;base64,{arrow_image}) | {prox_icon} **{distance_percentage:.2f}%** | Alphabet Direction: ![AlphDirection {alph_direction}](data:image/png;base64,{alph_arrow_image})"
        )

    if len(guesses) == 6:
        st.error("You Guessed Incorrectly 6 Times 😔")
        st.write("The correct answer was: " + random_location['name'])
        st.button("Try Again!", on_click=on_reset)
        st.stop()

    with st.form("guess", True):
        guess = st.selectbox(
            "Guess the country (Click the drop down then type to filter)",
            map(lambda location: location['name'], all_locations),
        )
        has_guessed = st.form_submit_button("Submit Guess!")

    st.button("Get new Random Country", on_click=on_reset)
    guess_dict = {}
    for loc in all_locations:
        if loc['name'] == guess:
            guess_dict = loc
            break

    if not has_guessed or guess_dict in guesses:
        st.warning("Submit a new Guess to continue!")
        st.stop()

    guesses.append(guess_dict)
    st.experimental_rerun()


LOCALES = {
    "ar": "name_ar",
    "bn": "name_bn",
    "de": "name_de",
    "en": "name_en",
    "es": "name_es",
    "fr": "name_fr",
    "el": "name_el",
    "hi": "name_hi",
    "hu": "name_hu",
    "id": "name_id",
    "it": "name_it",
    "ja": "name_ja",
    "ko": "name_ko",
    "nl": "name_nl",
    "pl": "name_pl",
    "pt": "name_pt",
    "ru": "name_ru",
    "sv": "name_sv",
    "tr": "name_tr",
    "vi": "name_vi",
    "zh": "name_zh",
}

if __name__ == "__main__":
    main()
