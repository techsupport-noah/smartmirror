import streamlit as st
import pandas as pd
import urllib.request
import json
import numpy as np
import openmeteo_requests
from datetime import datetime
import requests_cache
import pandas as pd
from retry_requests import retry
import altair as alt

def getMeals(mensa_id):
  return json.loads(urllib.request.urlopen("https://sls.api.stw-on.de/v1/locations/" + mensa_id + "/menu/" + datetime.today().strftime('%Y-%m-%d')).read())["meals"]

st.set_page_config(layout="wide")

columns = st.columns(2)

with columns[0]:
  st.title("Essenspläne TU Braunschweig")

list_of_mensas = [["Mensa 1 TU Braunschweig","101"], ["Mensa 2 TU Braunschweig","105"], ["Mensa 360 Grad","111"]]
# get menus of each mensa
for mensa in list_of_mensas:
  # get all meal offers as json
  print(mensa)
  offers_as_json = getMeals(mensa[1])
  print(offers_as_json)
  data = []

  # parse all offers
  for offer in offers_as_json:
    data.append([offer["name"], offer["price"]["student"]])

  df = pd.DataFrame(data, columns = ['Name', 'Price'])

  with columns[0]:
    st.header(mensa[0], divider="green")
    st.dataframe(df, 
                column_config={
                    "Price": st.column_config.NumberColumn(
                      "Price",
                      format="%.2f €",
                      width= "small"
                    ),
                    "Name": st.column_config.TextColumn(
                      "Name",
                      width= "large"
                    )
                },
                use_container_width=False,
                hide_index=True)
    


# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"
params_daily = {
  "latitude": 52.2659,
  "longitude": 10.5267,
  "daily": ["temperature_2m_max", "temperature_2m_min"],
  "timezone": "Europe/Berlin"
}
params_hourly = {
  "latitude": 52.2659,
  "longitude": 10.5267,
  "hourly": ["temperature_2m", "precipitation_probability", "precipitation", "rain", "snowfall", "uv_index"],
  "timezone": "Europe/Berlin",
  	"forecast_days": 1
}

# Process first location
responses_daily = openmeteo.weather_api(url, params=params_daily)[0]
responses_hourly = openmeteo.weather_api(url, params=params_hourly)[0]

print(f"Coordinates {responses_daily.Latitude()}°E {responses_daily.Longitude()}°N")
print(f"Elevation {responses_daily.Elevation()} m asl")
print(f"Timezone {responses_daily.Timezone()} {responses_daily.TimezoneAbbreviation()}")
print(f"Timezone difference to GMT+0 {responses_daily.UtcOffsetSeconds()} s")

# Process hourly data. The order of variables needs to be the same as requested.
hourly = responses_hourly.Hourly()
hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
hourly_precipitation_probability = hourly.Variables(1).ValuesAsNumpy()
hourly_precipitation = hourly.Variables(2).ValuesAsNumpy()
hourly_rain = hourly.Variables(3).ValuesAsNumpy()
hourly_snowfall = hourly.Variables(4).ValuesAsNumpy()
hourly_uv_index = hourly.Variables(5).ValuesAsNumpy()

hourly_data = {"date": pd.date_range(
  start = pd.to_datetime(hourly.Time(), unit = "s"),
  end = pd.to_datetime(hourly.TimeEnd(), unit = "s"),
  freq = pd.Timedelta(seconds = hourly.Interval()),
  inclusive = "left"
)}
hourly_data["temperature_2m"] = hourly_temperature_2m
hourly_data["precipitation_probability"] = hourly_precipitation_probability
hourly_data["precipitation"] = hourly_precipitation
hourly_data["rain"] = hourly_rain
hourly_data["snowfall"] = hourly_snowfall
hourly_data["uv_index"] = hourly_uv_index

hourly_dataframe = pd.DataFrame(data = hourly_data)
print(hourly_dataframe)

# Process daily data. The order of variables needs to be the same as requested.
daily = responses_daily.Daily()
daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()

daily_data = {"date": pd.date_range(
  start = pd.to_datetime(daily.Time(), unit = "s").floor("d"),
  end = pd.to_datetime(daily.TimeEnd(), unit = "s").floor("d"),
  freq = pd.Timedelta(seconds = daily.Interval()).floor("d"),
  inclusive = "left"
)}
daily_data["temperature_2m_max"] = daily_temperature_2m_max
daily_data["temperature_2m_min"] = daily_temperature_2m_min

daily_dataframe = pd.DataFrame(data = daily_data)
print(daily_dataframe)

with columns[1]:
  st.title("Wettervorhersage Braunschweig")

  st.header("24h Wetterverlauf", divider="green")
  layers = []
  for key in hourly_dataframe.keys():
    # if not date or temperature_2m
    if key != "date" and key != "temperature_2m" and key != "uv_index":
      layers.append(
        alt.Chart(hourly_dataframe)
        .transform_calculate(Legende="'"+key+"'")
        .mark_line(point=alt.OverlayMarkDef(filled=False, fill='white'))
        .encode(
          # encode in a way that x is scaled to show a date only one time
          alt.X('date:T', axis=alt.Axis(title='Uhrzeit', format='%H Uhr')),
          alt.Y(key, axis=alt.Axis(title="")),
          alt.Color('Legende:N', legend=alt.Legend(orient="bottom"), scale=alt.Scale(scheme='set1'))
        ).interactive()
      )

  c = alt.layer(*layers)
  st.altair_chart(c, use_container_width=True)

  st.header("24h Temperaturverlauf", divider="green")
  layers = []
  for key in hourly_dataframe.keys():
    if key != "date" and key == "temperature_2m" or key == "uv_index":
      layers.append(
        alt.Chart(hourly_dataframe)
        .transform_calculate(Legende="'"+key+"'")
        .mark_line(point=alt.OverlayMarkDef(filled=False, fill='white'))
        .encode(
          # encode in a way that x is scaled to show a date only one time
          alt.X('date:T', axis=alt.Axis(title='Uhrzeit', format='%H Uhr')),
          alt.Y(key, axis=alt.Axis(title="")),
          alt.Color('Legende:N', legend=alt.Legend(orient="bottom"), scale=alt.Scale(scheme='set1'))
        ).interactive()
      )

  c = alt.layer(*layers)
  st.altair_chart(c, use_container_width=True)

  
  # st.line_chart(hourly_dataframe,
  #               x="date",
  #               y=["temperature_2m", "precipitation_probability", "precipitation", "rain", "snowfall", "uv_index"],)
  
  st.header("7 Tage Temperaturverlauf", divider="green")
  layers = []
  for key in daily_dataframe.keys():
    if key != "date":
      layers.append(
        alt.Chart(daily_dataframe)
        .transform_calculate(Legende="'"+key+"'")
        .mark_line()
        .encode(
          # encode in a way that x is scaled to show a date only one time
          alt.X('date:T', axis=alt.Axis(title='Datum', format='%d.%m', tickCount=daily_dataframe.shape[0])),
          alt.Y(key, axis=alt.Axis(title="")),
          alt.Color('Legende:N', legend=alt.Legend(orient="right"), scale=alt.Scale(scheme='set1'))
        ).interactive()
      )

  c = alt.layer(*layers)
  st.altair_chart(c, use_container_width=True)

