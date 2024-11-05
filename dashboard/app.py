from shiny import reactive, render
from shiny.express import ui, input
import random
from datetime import datetime
from collections import deque
import pandas as pd
import plotly.express as px
from shinywidgets import render_plotly
from scipy import stats
from faicons import icon_svg
import openmeteo_requests
import requests_cache
from retry_requests import retry

UPDATE_INTERVAL_SECS: int = 3

# --------------------------------------------
# Initialize a REACTIVE VALUE with a common data structure
# The reactive value is used to store state (information)
# Used by all the display components that show this live data.
# This reactive value is a wrapper around a DEQUE of readings
# --------------------------------------------

DEQUE_SIZE: int = 50
reactive_value_wrapper = reactive.value(deque(maxlen=DEQUE_SIZE))

# Load the historical data from data folder
historical_data_path = "data/PalmerStation_Monthly_Weather_Clean.csv"
historical_df = pd.read_csv(historical_data_path)
historical_df['Date'] = pd.to_datetime(historical_df['Date'])

# Collect the Live Data

# Set update interval for live weather data
WEATHER_UPDATE_INTERVAL_SECS: int = 900  # 15 minutes in seconds

@reactive.effect
def update_weather():
    # Invalidate this effect every WEATHER_UPDATE_INTERVAL_SECS
    reactive.invalidate_later(WEATHER_UPDATE_INTERVAL_SECS)

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": -77.846,
    "longitude": 166.676,
    "minutely_15": "temperature_2m",
    "current": "temperature_2m",
    "timezone": "GMT",
    "past_minutely_15": 24,
    "forecast_days": 1
}
responses = openmeteo.weather_api(url, params=params)

# Process first location. Add a for-loop for multiple locations or weather models
response = responses[0]


# Current values. The order of variables needs to be the same as requested.
current = response.Current()
current_temperature_2m = current.Variables(0).Value()

# Process minutely_15 data. The order of variables needs to be the same as requested.
minutely_15 = response.Minutely15()
minutely_15_temperature_2m = minutely_15.Variables(0).ValuesAsNumpy()

minutely_15_data = {"date": pd.date_range(
	start = pd.to_datetime(minutely_15.Time(), unit = "s", utc = True),
	end = pd.to_datetime(minutely_15.TimeEnd(), unit = "s", utc = True),
	freq = pd.Timedelta(seconds = minutely_15.Interval()),
	inclusive = "left"
)}
minutely_15_data["temperature_2m"] = minutely_15_temperature_2m

minutely_15_dataframe = pd.DataFrame(data = minutely_15_data)


# Define the reactive calculation
@reactive.calc()
def reactive_calc_combined():
    # Invalidate this calculation every UPDATE_INTERVAL_SECS to trigger updates
    reactive.invalidate_later(UPDATE_INTERVAL_SECS)

    # Data generation logic
    temp = round(random.uniform(-18, 1), 1)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_dictionary_entry = {"temp":temp, "timestamp":timestamp}

    # get the deque and append the new entry
    reactive_value_wrapper.get().append(new_dictionary_entry)

    # Get a snapshot of the current deque for any further processing
    deque_snapshot = reactive_value_wrapper.get()

    # For Display: Convert deque to DataFrame for display
    df = pd.DataFrame(deque_snapshot)

    # For Display: Get the latest dictionary entry
    latest_dictionary_entry = new_dictionary_entry

    # Return a tuple with everything we need
    # Every time we call this function, we'll get all these values
    return deque_snapshot, df, latest_dictionary_entry

@reactive.calc()
def filtered_historical_df():
    # Get the selected time interval from the input
    selected_interval = input.time()
    # Parse the current date to get year and month
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Filter the historical_df based on the selected interval
    if selected_interval == "1 Year":
        filtered_df = historical_df[
            ((historical_df["Year"] == current_year - 1) & (historical_df["Month"] >= current_month)) |
            (historical_df["Year"] == current_year)
        ]
    elif selected_interval == "5 years":
        filtered_df = historical_df[historical_df["Year"] >= current_year - 5]
    elif selected_interval == "25 Years":
        filtered_df = historical_df[historical_df["Year"] >= current_year - 25]
    elif selected_interval == "50 Years":
        filtered_df = historical_df[historical_df["Year"] >= current_year - 50]
    else:
        filtered_df = historical_df

    return filtered_df




# Define the Shiny UI Page layout
# Call the ui.page_opts() function
# Set title to a string in quotes that will appear at the top
# Set fillable to True to use the whole page width for the UI
ui.page_opts(title="Palmer Station Antarctica Temperatures", fillable=True)

# Sidebar is typically used for user interaction/information
# Note the with statement to create the sidebar followed by a colon
# Everything in the sidebar is indented consistently
with ui.sidebar(open="open"):

    ui.h2("Antarctic Explorer", class_="text-center"),
    ui.p("A demonstration of real-time temperature readings in Antarctica.", class_="text-center",),
    ui.input_select("source", "Live Data Source", ["OpenMeteo API", "Random"], selected="OpenMeteo API"),
    ui.input_select("data", "Data Table Source", ["OpenMeteo API", "Random", "Historical Data"], selected="OpenMeteo API"),
    ui.input_select("time", "Historical Time Interval", ["1 Year", "5 years", "25 Years", "50 Years"], selected="25 Years"),
    ui.hr(),
    ui.h6("Links:"),
    ui.a("GitHub Source", href="https://github.com/drpafowler/cintel-05-cintel/tree/main", target="_blank",),
    ui.a("GitHub App", href="https://drpafowler.github.io/cintel-05-cintel/", target="_blank")
    ui.a("OpenMeteo API", href="https://open-meteo.com/", target="_blank")
    ui.a("Palmer Station Historical Data", href="https://portal.edirepository.org/nis/mapbrowse?scope=knb-lter-pal&identifier=189", target="_blank",)

# In Shiny Express, everything not in the sidebar is in the main panel

with ui.layout_columns():
    with ui.value_box(showcase=icon_svg("temperature-low"), theme="bg-gradient-blue-purple"):

        "Current Temperature"

        @render.text
        def display_temp():
            """Get the latest reading and return a temperature string"""
            if input.source() == "OpenMeteo API":
                return f"{current_temperature_2m:.1f} C"

            else:
                deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()
                return f"{latest_dictionary_entry['temp']} C"

        @render.text
        def display_temp_status():
            """Get the latest reading and return a status string"""
            if input.source() == "OpenMeteo API":
                temp = current_temperature_2m
            else:
                deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()
                temp = latest_dictionary_entry['temp']
            
            if temp > 0:
                return "Warmer than Usual"
            elif temp > -15:
                return "Average Temperatures"
            else:
                return "Colder than Usual"

  

    with ui.value_box(showcase=icon_svg("clock"), theme="bg-gradient-blue-purple"):

        "Current Date and Time at Palmer Station"
        @render.text
        def display_time():
            """Get the latest reading and return a timestamp string in Palmer Station time (UTC-3)"""
            deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()
            # Convert the timestamp string to datetime
            utc_time = datetime.strptime(latest_dictionary_entry['timestamp'], "%Y-%m-%d %H:%M:%S")
            # Adjust for Palmer Station timezone (UTC-3)
            palmer_time = utc_time.replace(hour=(utc_time.hour - 3) % 24)
            return palmer_time.strftime("%Y-%m-%d %H:%M:%S")


with ui.card(full_screen=True):
    ui.card_header("Data Table")

    @render.data_frame
    def display_df():
        """Get the latest reading and return a dataframe with current readings"""
        if input.data() == "OpenMeteo API":
            return render.DataGrid(minutely_15_dataframe, width="100%")
        elif input.data() == "Random":
            deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()
            pd.set_option('display.width', None)
            return render.DataGrid(df, width="100%")
        else:  # Historical Data
            return render.DataGrid(filtered_historical_df(), width="100%")

with ui.card():
    ui.card_header("Live Data")

    @render_plotly
    def display_plot():
        if input.source() == "OpenMeteo API":
            # Create scatter plot for OpenMeteo data
            fig = px.scatter(minutely_15_dataframe,
                x="date", 
                y="temperature_2m",
                title="OpenMeteo Temperature Readings",
                labels={"temperature_2m": "Temperature (°C)", "date": "Time"},
                color_discrete_sequence=["blue"])
            return fig
        else:
            # Fetch from the reactive calc function for random data
            deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()

            # Ensure the DataFrame is not empty before plotting
            if not df.empty:
                # Convert the 'timestamp' column to datetime for better plotting
                df["timestamp"] = pd.to_datetime(df["timestamp"])

                # Create scatter plot for readings
                fig = px.scatter(df,
                    x="timestamp",
                    y="temp",
                    title="Temperature Readings with Regression Line",
                    labels={"temp": "Temperature (°C)", "timestamp": "Time"},
                    color_discrete_sequence=["blue"])
                
                # Linear regression
                sequence = range(len(df))
                x_vals = list(sequence)
                y_vals = df["temp"]

                slope, intercept, r_value, p_value, std_err = stats.linregress(x_vals, y_vals)
                df['best_fit_line'] = [slope * x + intercept for x in x_vals]

                # Add the regression line to the figure
                fig.add_scatter(x=df["timestamp"], y=df['best_fit_line'], mode='lines', name='Regression Line')

                # Update layout
                fig.update_layout(xaxis_title="Time", yaxis_title="Temperature (°C)")
                return fig

            return px.scatter()  # Return empty plot if df is empty

with ui.card():
    ui.card_header("Historical Data")   

    @render_plotly
    def display_historical_plot():
        # Fetch the filtered historical data
        filtered_df = filtered_historical_df()
        fig = px.scatter(filtered_df,
            x="Date",
            y="Mean Temperature (C)",
            title="Historical Temperature Readings",
            labels={"Temperature": "Temperature (°C)", "Date": "Time"},
            color_discrete_sequence=["blue"] )

        # Calculate and add a 12-month running average (since we have monthly data)
        filtered_df['Running_Avg'] = filtered_df['Mean Temperature (C)'].rolling(window=12, center=True).mean()

        # Add the running average as a red line
        fig.add_scatter(
            x=filtered_df["Date"], 
            y=filtered_df["Running_Avg"], 
            mode='lines', 
            line=dict(color='red', width=2), 
            name='12-Month Running Average'
        )

        return fig
    


