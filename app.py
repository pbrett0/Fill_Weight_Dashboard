# Run this app with `python app.py` and visit http://127.0.0.1:8050/ in your web browser.
import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output
from pandas import *
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine
import urllib

app = dash.Dash(__name__)

# Connection to the SQL Database
params = urllib.parse.quote_plus \
(r'Driver={ODBC Driver 13 for SQL Server};Server=tcp:datavisualisationserver.database.windows.net,1433;Database=data_visualisation_db;Uid=server_login;Pwd=DataVisual123;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;')
conn_str = 'mssql+pyodbc:///?odbc_connect={}'.format(params)
engine_azure = create_engine(conn_str, echo=True)

# Import the Excel File and assign to pd Dataframe
df = pd.read_sql('SELECT * FROM fill_weight_data', con = engine_azure)

# Sorting the Values by Date-Time
df['Measurement date-time'] = pd.to_datetime(df['Measurement date-time'])
df.sort_values('Measurement date-time', inplace = True)

# Extracting the Columns required and Grouping by Batch
df_slice = df[['Batch Number', 'Lower Alarm', 'Lower Warning', 'Upper Warning', 'Upper Alarm', 'Fill Weight (g)', 'Measurement date-time', 'Measurement ID', 'IPC Mode']]
## If taking a slice of the main Dataframe its important to create a copy of the main as to avoid errors 
limit_chart = df_slice.copy()
limit_chart['Batch Mean'] = ""
limit_chart['3sd Plus'] = ""
limit_chart['3sd Minus'] = ""

# Grouping the Rows by Batch and creating a Batch Stats df (Used to populate limit_chart df)
batch_group = df.groupby(['Batch Number'])
batch_stats = batch_group['Fill Weight (g)'].agg(['mean', 'median', 'std'])
batch_stats['std'] = batch_stats['std']*3
batch_stats['sdplus'] = batch_stats['mean'] + batch_stats['std']
batch_stats['sdminus'] = batch_stats['mean'] - batch_stats['std']

# Adding the Mean & Standard Deviations per Batch
# This x values index is collected while the for loop updates the limit_chart mean & std. deviation
x_values_index = []

for i in batch_stats.itertuples():
    batch_num = i[0]
    mean = i[1]
    sdplus = i[4]
    sdminus = i[5]
    for locat in range(len(limit_chart)):
        x_values_index.append(locat)
        batch_id = limit_chart.loc[locat,'Batch Number']
        if batch_num == batch_id:
            limit_chart.loc[locat,'Batch Mean'] = mean
            limit_chart.loc[locat,'3sd Plus'] = sdplus
            limit_chart.loc[locat,'3sd Minus'] = sdminus

# Batch Number Dropdown Options
dicts = []
for key in range(len(batch_stats)):
    batch_index = batch_stats.index.values
    dicts.append({'label': str(batch_index[key]), 'value': batch_index[key]})

# IPC Mode Dropdown (Note NaN will cause errors)
dicts_1 = []
unique_values = limit_chart['IPC Mode'].unique()
for key in range(len(unique_values))[:-1]:
    dicts_1.append({'label': str(unique_values[key]), 'value': unique_values[key]})

# Dashboard Layout
app.layout = html.Div([

    html.H1("Fill Weight Data Dashboard", style={'text-align': 'center'}),
    dcc.Dropdown(
        id = "select_batch",
        options = dicts,
        multi = False,
        value = dicts[0].get('value'),
        style = {'width': '40%'}
    ),
    dcc.Dropdown(
        id = "select_IPC_Mode",
        options = dicts_1,
        multi = False,
        value = dicts_1[1].get('value'),
        style = {'width': '40%'}
    ),
    html.Div(id = 'graph_div'),
    html.Br(),
    html.Label('Nelson Rules'),
        dcc.Checklist(id = 'nelson_checklist',
            options=[
                {'label': 'Nelson Rule 1', 'value': 'NR1'},
                {'label': 'Nelson Rule 2', 'value': 'NR2'},
                {'label': 'Nelson Rule 3', 'value': 'NR3'}
            ],
            value = ['NR1']
        ),
    html.Br(),
    dcc.Graph(id = "fill_weight_graph")
])

# Call Back to connect the Dataframe to the Components
@app.callback(
    [
        Output(component_id='graph_div', component_property='children'),
        Output(component_id='fill_weight_graph', component_property='figure')
    ],
    [
        Input(component_id='select_batch', component_property='value'),
        Input(component_id='select_IPC_Mode', component_property='value'),
        Input(component_id='nelson_checklist', component_property='value')
    ]
)

def update_graph(batch_selected, ipc_selected, nelson_selected):
    print(batch_selected)

    container = "Batch chosen: {}".format(batch_selected)

    dff = limit_chart.copy()
    dff = dff[dff["Batch Number"] == batch_selected]

    dff = dff[dff["IPC Mode"] == ipc_selected]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['Fill Weight (g)'], mode='lines+markers', name='Fill Weight'))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['Batch Mean'], mode='lines', name='Batch Mean', line = dict(color='grey', dash='dash')))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['3sd Plus'], mode='lines', name='3σ', line = dict(color='grey', dash='dash')))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['3sd Minus'], mode='lines', name='3σ', line = dict(color='grey', dash='dash')))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['Lower Alarm'], mode='lines', name='Lower Alarm', line = dict(color='red')))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['Lower Warning'], mode='lines', name='Lower Warning', line = dict(color='orange')))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['Upper Warning'], mode='lines', name='Upper Warning', line = dict(color='orange')))
    fig.add_trace(go.Scatter(x=dff.index.values, y=dff['Upper Alarm'], mode='lines', name='Upper Alarm', line = dict(color='red')))

    fig.update_layout(title='Fill Weight Graph', xaxis_title='Index Number', yaxis_title='Fill Weight')

    
    for i in nelson_selected:
        if nelson_selected == []:
            print('Markers are deleted')
        elif 'NR1' == i:
            x_list = []
            y_list = []
            for x, y in zip(dff.index.values, dff['Fill Weight (g)']):
                if y >= dff.loc[x,'3sd Plus'] or y <= dff.loc[x,'3sd Minus']:
                    x_list.append(x)
                    y_list.append(y)

            fig.add_trace(go.Scatter(mode='markers',x=x_list,y=y_list, marker=dict(color='red',size=3, line = dict(color='red', width = 4)),showlegend=False))
        elif 'NR2' == i:
            y_list = []
            mean_list = []
            x_list = []
            i = 0
            for x,y,mean in zip(dff.index.values, dff['Fill Weight (g)'], dff['Batch Mean']):
                x_list.append(x)
                y_list.append(y)
                mean_list.append(mean)
                i += 1
                if i >= 9: 
                    # Check the 9 Data Points in Sub Lists
                    for j in y_list:
                        # Check if all data points are above the Mean
                        if j < mean_list[0]: 
                            for m in y_list:
                                # Check if all data points are below the Mean
                                if m > mean_list[0]:
                                    x_list.pop(0)
                                    y_list.pop(0)
                                    mean_list.pop(0)
                                    break # Breaks to main loop
                            else:
                                # All Data points are below the Mean. Break cycle and reset lists
                                fig.add_trace(go.Scatter(mode='markers',x=x_list,y=y_list, marker=dict(color='orange',size=3, line = dict(color='orange', width = 4)),showlegend=False))
                                x_list.pop(0)
                                y_list.pop(0)
                                mean_list.pop(0)
                            break # breaks to main loop
                    else:        
                        # All Data points are above the mean. Break cycle and reset lists
                        fig.add_trace(go.Scatter(mode='markers',x=x_list,y=y_list, marker=dict(color='orange',size=3, line = dict(color='orange', width = 4)),showlegend=False))
                        x_list.pop(0)
                        y_list.pop(0)
                        mean_list.pop(0)
        elif 'NR3' == i:
            y_list = []
            x_list = []
            i = 0
            for x,y in zip(dff.index.values, dff['Fill Weight (g)']):
                x_list.append(x)
                y_list.append(y)
                i += 1
                if i >= 6: 
                    # Check the 6 Data Points in Sub Lists
                    for count_1, value_1 in enumerate(y_list):
                        # Check if all data points are increasing
                        if value_1 > y_list[count_1 + 1] or count_1 == 4: 
                            for count_2, value_2 in enumerate(y_list):
                                # Check if all data points are decreasing
                                if value_2 < y_list[count_2 + 1] or count_2 == 4:
                                    x_list.pop(0)
                                    y_list.pop(0)
                                    break # Breaks to main loop
                            else:
                                # All Data points are decreasing. Break cycle and reset lists
                                fig.add_trace(go.Scatter(mode='markers',x=x_list,y=y_list, marker=dict(color='yellow',size=3, line = dict(color='yellow', width = 4)),showlegend=False))
                                x_list.pop(0)
                                y_list.pop(0)
                            break # breaks to main loop
                    else:        
                        # All Data points are increasing. Break cycle and reset lists
                        fig.add_trace(go.Scatter(mode='markers',x=x_list,y=y_list, marker=dict(color='yellow',size=3, line = dict(color='yellow', width = 4)),showlegend=False))
                        x_list.pop(0)
                        y_list.pop(0)
        
    return container, fig


if __name__ == '__main__':
    app.run_server(debug=True)