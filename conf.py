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


if 'output_data' not in st.session_state:
    st.session_state['output_data'] = None
    
with st.container(border=True):
    st.title("Experiment Status")
    col1, col2, col3 = st.columns(3)
    with col1:
        if 'connection_status' not in st.session_state:
            st.session_state['connection_status'] = st.metric("Control system status", "Not connected!")
    with col2:
        if 'experiment_status' not in st.session_state:
            st.session_state['experiment_status'] = st.metric("Experiment ID", "No data!")
    with col3:
        if 'control_status' not in st.session_state:
            st.session_state['control_status'] = st.metric("Adjusting", "No data!")
    if 'status_container' not in st.session_state:
        st.session_state['status_container'] = st.status("Messages will appear here",
                                                         expanded=False,
                                                         state="complete")

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

make_plot(edited_experiment_df)

# -----------------------------------------------------------------------------
# Create download button
    
experiment_json = edited_experiment_df.to_json(orient='records')
config_json = edited_config_df.to_json(orient='records')

output_data = input_file
output_data['experiment'] = json.loads(experiment_json)
output_data['config']['sensors'] = json.loads(config_json)

st.session_state['output_data'] = output_data
st.session_state['download_container'].download_button(
    label="Download config",
    data=json.dumps(output_data).encode('utf-8'),
    file_name='config.json',
    mime='application/json',
    use_container_width=True,
    type='primary',
)
# -----------------------------------------------------------------------------
# MQTT

def on_message(client, obj, msg):
    if (msg.topic == "controller/heartbeat"):
        payload = json.loads(msg.payload.decode('utf-8'))

        all_modes = ["Temperature", "Pressure", "Displacement 1", "Displacement 2"]
        current_modes = [key for key, value in payload["adjusting"].items() if value]
        adjusting_str = ', '.join(current_modes) if current_modes else "--"

        now = datetime.now().strftime("%H:%M:%S")
        st.session_state['connection_status'].metric(label="Control system status",
                                                     value=str(payload["status"]),
                                                     delta=now)
        st.session_state['experiment_status'].metric(label="Experiment ID",
                                                     value=payload["experiment"],
                                                     delta=now)
        st.session_state['control_status'].metric(label="Adjusting",
                                                  value=adjusting_str,
                                                  delta=now)
    elif (msg.topic == "controller/validator/passed"):
        payload = json.loads(msg.payload.decode('utf-8'))
        if (payload["uid"] == st.session_state['await_uuid']):
            st.session_state['status_container'].update(label="Setting complete!", state="complete", expanded=False)
    elif (msg.topic == "controller/validator/failed"):
        payload = json.loads(msg.payload.decode('utf-8'))
        if (payload["uid"] == st.session_state['await_uuid']):
            error_str = json.loads(msg.payload.decode('utf-8'))['error']
            st.session_state['status_container'].text(error_str)
    elif (msg.topic == "controller/error"):
        st.session_state['status_container'].text(msg.payload.decode('utf-8'))

if 'mqtt_client' not in st.session_state:
    client = mqtt.Client()    
    client.on_message = on_message
    client.connect("fase-rabbitmq", 1883, 60)

    st.session_state['mqtt_client'] = client
    st.session_state['mqtt_client'].subscribe("controller/#", 0)
        
st.session_state['mqtt_client'].loop_forever()
