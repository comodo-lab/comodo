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
    df.plot(x="time", y="temperature", ax=axes[0])
    df["pressure"].plot(x="time", secondary_y=True, ax=axes[0])
    axes[0].set_ylabel("temperature")
    axes[0].right_ax.set_ylabel("pressure")
    lines = axes[0].get_lines() + axes[0].right_ax.get_lines()
    axes[0].legend(lines, [line.get_label() for line in lines])

    # Subplot 2: displacement 1 on the main y-axis, displacement 2 on the secondary
    df.plot(x="time", y="displacement 1", ax=axes[1], color="red")
    df["displacement 2"].plot(x="time", secondary_y=True, ax=axes[1], color="green")
    axes[1].set_ylabel("displacement 1")
    axes[1].right_ax.set_ylabel("displacement 2")
    lines = axes[1].get_lines() + axes[1].right_ax.get_lines()
    axes[1].legend(lines, [line.get_label() for line in lines])

    plt.subplots_adjust(hspace=0)
    st.session_state["plot_container"].pyplot(fig)


def container_label_and_text(text):
    st.session_state["status_container"].update(
        label=text, expanded=False, state="running"
    )
    st.session_state["status_container"].text(text)


def send_config():
    ID = str(uuid.uuid4())[:8]
    st.session_state["await_uuid"] = ID

    send_data = st.session_state["output_data"]
    send_data["uid"] = ID

    st.session_state["mqtt_client"].publish(
        "ui/start", json.dumps(send_data).encode("utf-8")
    )
    container_label_and_text("Sending configuration...")


# -----------------------------------------------------------------------------
# Page config

st.set_page_config(
    page_title="Experiment Config",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None,
)

if "await_uuid" not in st.session_state:
    st.session_state["await_uuid"] = None

if "output_data" not in st.session_state:
    st.session_state["output_data"] = None

with st.container(border=True):
    st.title("Experiment Status")
    col1, col2, col3 = st.columns(3)
    with col1:
        if "connection_status" not in st.session_state:
            st.session_state["connection_status"] = st.metric(
                "Control system status", "Not connected!"
            )
    with col2:
        if "experiment_status" not in st.session_state:
            st.session_state["experiment_status"] = st.metric(
                "Experiment ID", "No data!"
            )
    with col3:
        if "control_status" not in st.session_state:
            st.session_state["control_status"] = st.metric("Adjusting", "No data!")
    if "status_container" not in st.session_state:
        st.session_state["status_container"] = st.status(
            "Messages will appear here", expanded=False, state="complete"
        )

# -----------------------------------------------------------------------------
# Site layout

col4, col5 = st.columns(2)
with st.container():
    with col4:
        with st.container(border=True):
            uploaded_file = st.file_uploader("Upload experiment configuration")
        with st.container(border=True):
            st.subheader("Experiment Editor", divider="grey")
            st.write("Experiment profile:")
            if "experiment_dataframe_container" not in st.session_state:
                st.session_state["experiment_dataframe_container"] = st.empty()
            st.write("Sensor configuration:")
            if "config_dataframe_container" not in st.session_state:
                st.session_state["config_dataframe_container"] = st.empty()
            if "setpoint_resolution" not in st.session_state:
                st.session_state["setpoint_resolution"] = st.number_input(
                    "Setpoint resolution [s]:", value=1, min_value=1
                )
            if "download_container" not in st.session_state:
                st.session_state["download_container"] = st.empty()
    with col5:
        with st.container(border=True):
            st.subheader("Start experiment", divider="grey")
            if "send_container" not in st.session_state:
                st.session_state["send_container"] = st.button(
                    "Send experiment configuration",
                    on_click=send_config,
                    use_container_width=True,
                    type="primary",
                    disabled=False,
                )
        with st.container(border=True):
            st.subheader("Experiment Profile Plot", divider="grey")
            if "plot_container" not in st.session_state:
                st.session_state["plot_container"] = st.empty()
        with st.container(border=True):
            st.subheader("Experiment controls", divider="grey")
            with st.form("Edit experiment"):
                uid = st.text_input("Enter experiment ID to edit experiment")
                submitted = st.form_submit_button(
                    "Send new configuration", use_container_width=True, type="primary"
                )
                if submitted:
                    payload = '{"uid":"' + uid + '"}'
                    st.session_state["mqtt_client"].publish(
                        f"ui/edit", payload.encode("utf-8")
                    )
            with st.form("Stop experiment"):
                uid = st.text_input("Enter experiment ID to stop experiment")
                submitted = st.form_submit_button(
                    "Stop", use_container_width=True, type="primary"
                )
                if submitted:
                    payload = '{"uid":"' + uid + '"}'
                    st.session_state["mqtt_client"].publish(
                        f"ui/stop", payload.encode("utf-8")
                    )

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

edited_experiment_df = st.session_state["experiment_dataframe_container"].data_editor(
    pd.DataFrame(input_file["experiment"]),
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True,
)

edited_config_df = st.session_state["config_dataframe_container"].data_editor(
    pd.DataFrame(input_file["config"]["sensors"]),
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True,
)
st.session_state["setpoint_resolution"] = input_file["config"]["resolution"]

# -----------------------------------------------------------------------------
# Create plots

make_plot(edited_experiment_df)

# -----------------------------------------------------------------------------
# Create download button

experiment_json = edited_experiment_df.to_json(orient="records")
config_json = edited_config_df.to_json(orient="records")
resolution = st.session_state["setpoint_resolution"]

output_data = input_file
output_data["experiment"] = json.loads(experiment_json)
output_data["config"]["sensors"] = json.loads(config_json)
output_data["config"]["resolution"] = resolution

st.session_state["output_data"] = output_data
st.session_state["download_container"].download_button(
    label="Download experiment configuration",
    data=json.dumps(output_data).encode("utf-8"),
    file_name="config.json",
    mime="application/json",
    use_container_width=True,
    type="primary",
)
# -----------------------------------------------------------------------------
# MQTT


def on_message(client, obj, msg):
    payload = json.loads(msg.payload.decode("utf-8"))
    if msg.topic == "heartbeat/controller":
        current_modes = [key for key, value in payload["adjusting"].items() if value]
        adjusting_str = ", ".join(current_modes) if current_modes else "--"

        now = datetime.now().strftime("%H:%M:%S")
        st.session_state["connection_status"].metric(
            label="Control system status", value=str(payload["status"]), delta=now
        )
        st.session_state["experiment_status"].metric(
            label="Experiment ID", value=payload["experiment"], delta=now
        )
        st.session_state["control_status"].metric(
            label="Adjusting", value=adjusting_str, delta=now
        )
    elif msg.topic == "controller/validate":
        if payload["uid"] == st.session_state["await_uuid"]:
            container_label_and_text("   Configuration received.")
            container_label_and_text("Validating configuration...")
    elif msg.topic == "validator/passed":
        if payload["uid"] == st.session_state["await_uuid"]:
            container_label_and_text("   Validation successful.")
            container_label_and_text("Waiting for sensors to be configured...")
    elif msg.topic == "controller/ready":
        if payload["uid"] == st.session_state["await_uuid"]:
            container_label_and_text("   Sensors configured successfully.")
            container_label_and_text("Starting experiment...")
    elif msg.topic == "controller/run":
        if (
            payload["uid"] == st.session_state["await_uuid"]
            and st.session_state["status_container"].state == "running"
        ):
            text = "Experiment started successfully!"
            container_label_and_text(text)
            st.session_state["status_container"].update(state="complete")
    elif msg.topic == "error/validator/failed":
        if payload["uid"] == st.session_state["await_uuid"]:
            st.session_state["status_container"].text(payload["error"])
            st.session_state["status_container"].update(
                label="Failed!", state="error", expanded=True
            )
    elif "error/" in msg.topic:
        st.session_state["status_container"].text(payload["error"])
        st.session_state["status_container"].update(
            label="Error!", state="error", expanded=True
        )


if "mqtt_client" not in st.session_state:
    client = mqtt.Client()
    client.on_message = on_message
    client.connect("fase-rabbitmq", 1883, 60)

    st.session_state["mqtt_client"] = client
    topics = [
        "heartbeat/controller",
        "controller/validate",
        "validator/passed",
        "controller/ready",
        "controller/run",
        "error/validator/#",
        "error/controller/#",
    ]
    for topic in topics:
        st.session_state["mqtt_client"].subscribe(topic, 0)

st.session_state["mqtt_client"].loop_forever()
