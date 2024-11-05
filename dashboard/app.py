
# From shiny, import just reactive and render
from shiny import reactive, render

# From shiny.express, import just ui and inputs if needed
from shiny.express import ui, input

import random
from datetime import datetime
from collections import deque
import pandas as pd
import plotly.express as px
from shinywidgets import render_plotly
from scipy import stats
from faicons import icon_svg


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
    ui.input_select("time", "Historical Time Interval", ["1 Year", "5 years", "25 Years", "50 Years"], selected="5 Years"),
    ui.hr(),
    ui.h6("Links:"),
    ui.a("GitHub Source", href="https://github.com/denisecase/cintel-05-cintel", target="_blank",),
    ui.a("GitHub App", href="https://denisecase.github.io/cintel-05-cintel/", target="_blank")
    ui.a("PyShiny", href="https://shiny.posit.co/py/", target="_blank")
    ui.a("PyShiny Express", href="hhttps://shiny.posit.co/blog/posts/shiny-express/", target="_blank",)

# In Shiny Express, everything not in the sidebar is in the main panel

with ui.layout_columns():
    with ui.value_box(showcase=icon_svg("temperature-low"), theme="bg-gradient-blue-purple"):

        "Current Temperature"

        @render.text
        def display_temp():
            """Get the latest reading and return a temperature string"""
            deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()
            return f"{latest_dictionary_entry['temp']} C"

        "warmer than usual"

  

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
        deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()
        pd.set_option('display.width', None)        # Use maximum width
        return render.DataGrid( df,width="100%")

with ui.card():
    ui.card_header("Chart with Current Trend")

    @render_plotly
    def display_plot():
        # Fetch from the reactive calc function
        deque_snapshot, df, latest_dictionary_entry = reactive_calc_combined()

        # Ensure the DataFrame is not empty before plotting
        if not df.empty:
            # Convert the 'timestamp' column to datetime for better plotting
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Create scatter plot for readings
            # pass in the df, the name of the x column, the name of the y column,
            # and more
        
            fig = px.scatter(df,
            x="timestamp",
            y="temp",
            title="Temperature Readings with Regression Line",
            labels={"temp": "Temperature (°C)", "timestamp": "Time"},
            color_discrete_sequence=["blue"] )
            
            # Linear regression - we need to get a list of the
            # Independent variable x values (time) and the
            # Dependent variable y values (temp)
            # then, it's pretty easy using scipy.stats.linregress()

            # For x let's generate a sequence of integers from 0 to len(df)
            sequence = range(len(df))
            x_vals = list(sequence)
            y_vals = df["temp"]

            slope, intercept, r_value, p_value, std_err = stats.linregress(x_vals, y_vals)
            df['best_fit_line'] = [slope * x + intercept for x in x_vals]

            # Add the regression line to the figure
            fig.add_scatter(x=df["timestamp"], y=df['best_fit_line'], mode='lines', name='Regression Line')

            # Update layout as needed to customize further
            fig.update_layout(xaxis_title="Time", yaxis_title="Temperature (°C)")
            return fig

        return fig

with ui.card():
    ui.card_header("Chart with 50 Year Historical Trend")   

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
    


