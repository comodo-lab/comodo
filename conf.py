import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import collections
from datetime import datetime
import uuid

def make_plot(df):
    fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True)

    # Subplot 1: temperature on the main y-axis, pressure on the secondary
    df.plot(x='time', y='temperature', ax=axes[0])
    df['pressure'].plot(x='time', secondary_y=True, ax=axes[0])
    axes[0].set_ylabel('temperature')
    axes[0].right_ax.set_ylabel('pressure')
    lines = axes[0].get_lines() + axes[0].right_ax.get_lines()
    axes[0].legend(lines, [line.get_label() for line in lines])
    
    # Subplot 2: displacement 1 on the main y-axis, displacement 2 on the secondary
    df.plot(x='time', y='displacement 1', ax=axes[1], color='red')
    df['displacement 2'].plot(x='time', secondary_y=True, ax=axes[1], color='green')
    axes[1].set_ylabel('displacement 1')
    axes[1].right_ax.set_ylabel('displacement 2')
    lines = axes[1].get_lines() + axes[1].right_ax.get_lines()
    axes[1].legend(lines, [line.get_label() for line in lines])

    plt.subplots_adjust(hspace=0)  
    st.session_state['plot_container'].pyplot(fig)

def send_config():
    ID = str(uuid.uuid4())[:8]
    st.session_state['await_uuid'] = ID
    st.session_state['mqtt_client'].publish(f"/experiment/config/{ID}/upload", json.dumps(output_data).encode('utf-8'))
    st.session_state['status_container'].update(label="Sending config", expanded=True, state="running")

# -----------------------------------------------------------------------------
# Page config

st.set_page_config(page_title="Experiment Config",
                   page_icon=None,
                   layout="wide",
                   initial_sidebar_state="expanded",
                   menu_items=None)


col1, col2, col3 = st.columns(3)
with st.container():
    with col1:
        if '/status/connection' not in st.session_state:
            st.session_state['/status/connection'] = st.metric("Connection Status", "Not connected!")
    with col2:
        if '/status/experiment' not in st.session_state:
            st.session_state['/status/experiment'] = st.metric("Experiment Status", "No data!")
    with col3:
        if '/status/control' not in st.session_state:
            st.session_state['/status/control'] = st.metric("Control mode", "No data!")

# -----------------------------------------------------------------------------
# Site layout


col4, col5 = st.columns(2)
with st.container():
    with col4:
        uploaded_file = st.file_uploader("Choose a file")
        if 'dataframe_container' not in st.session_state:
            st.session_state['dataframe_container'] = st.empty()
        if 'download_container' not in st.session_state:
            st.session_state['download_container'] = st.empty()
        if 'send_container' not in st.session_state:
            st.session_state['send_container'] = st.button("Send config", on_click=send_config)
    with col5:
        if 'plot_container' not in st.session_state:
            st.session_state['plot_container'] = st.empty()
        if 'status_container' not in st.session_state:
            st.session_state['status_container'] = st.status("Awaiting config", expanded=False, state="complete")

# -----------------------------------------------------------------------------
# Read appropriate input file

input_file = None
if uploaded_file is not None:
    input_file = json.load(uploaded_file)
else:
    with open("./template.json") as template:
        input_file = json.load(template) 

# -----------------------------------------------------------------------------
# Create dataframes

edited_experiment_df = \
    st.session_state['experiment_dataframe_container'].data_editor(
        pd.DataFrame(input_file["experiment"]),
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True
    )

edited_config_df = \
    st.session_state['config_dataframe_container'].data_editor(
        pd.DataFrame(input_file["config"]["sensors"]),
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# Create plots

make_plot(edited_df)

# -----------------------------------------------------------------------------
# Create download button
    
output_data = input_file
experiment_json = edited_df.transpose().to_json()
output_data['experiment'] = json.loads(experiment_json)

st.session_state['download_container'].download_button(
    label="Download config",
    data=json.dumps(output_data).encode('utf-8'),
    file_name='config.json',
    mime='application/json',
)
    
# -----------------------------------------------------------------------------
# MQTT

def on_message(client, obj, msg):
    if (len(msg.topic.split("/")) == 4):
        if (msg.topic.split("/")[3] == st.session_state['await_uuid']):
            if (msg.topic.split("/")[4] == "status") and (msg.payload.decode('utf-8') == "success"):
                st.session_state['status_container'].update(label="Setting complete!", state="complete", expanded=False)
            else:
                st.session_state['status_container'].write(f"{msg.topic}: {msg.payload.decode('utf-8')}")
    else:
        if (msg.topic in st.session_state):
            st.session_state[msg.topic].metric(label=msg.topic,
                                               value=msg.payload.decode('utf-8'),
                                               delta=datetime.now().strftime("%H:%M:%S"))

if 'mqtt_client' not in st.session_state:
    client = mqtt.Client()    
    client.on_message = on_message
    client.connect("localhost", 1883, 60)

    st.session_state['mqtt_client'] = client
    st.session_state['mqtt_client'].subscribe("/#", 0)
        
st.session_state['mqtt_client'].loop_forever()
