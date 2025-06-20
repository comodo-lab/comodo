import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import collections
from datetime import datetime
import uuid


def rescale_for_filling(df, y1, y2):
    # Rescale y2 to y1 scale, so that filling does not break separate scales
    ratio = (df[y1].max() - df[y1].min()) / (df[y2].max() - df[y2].min())
    y2_trans = df[y2] * ratio
    y2_trans = y2_trans - y2_trans.min() + df[y1].min()
    return y2_trans


def make_plot(df):
    fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True)

    # Subplot 1:
    ## Temperature on the main y-axis
    T_col = "red"
    P_col = "blue"
    df.plot(
        x="time",
        y="temperature",
        ax=axes[0],
        color=T_col,
        legend=False,
    )
    axes[0].set_ylabel("temperature", color=T_col)
    axes[0].fill_between(df["time"], df["temperature"], color=T_col, alpha=0.1)
    ## Pressure on the secondary y-axis
    df.plot(
        x="time",
        y="pressure",
        secondary_y=True,
        ax=axes[0],
        color=P_col,
        linestyle="dotted",
        legend=False,
    )
    axes[0].right_ax.set_ylabel("pressure", color=P_col)
    p_trans = rescale_for_filling(df, "temperature", "pressure")
    axes[0].fill_between(df["time"], p_trans, color=P_col, alpha=0.1)

    # Subplot 2:
    ## Displacement 1 on the main y-axis
    D1_col = "purple"
    D2_col = "green"
    df.plot(
        x="time",
        y="displacement 1",
        ax=axes[1],
        color=D1_col,
        legend=False,
    )
    axes[1].fill_between(df["time"], df["displacement 1"], color=D1_col, alpha=0.1)
    axes[1].set_ylabel("displacement 1", color=D1_col)
    ## Displacement 2 on the secondary y-axis
    df.plot(
        x="time",
        y="displacement 2",
        secondary_y=True,
        ax=axes[1],
        color=D2_col,
        linestyle="dotted",
        legend=False,
    )
    axes[1].right_ax.set_ylabel("displacement 2", color=D2_col)
    D2_trans = rescale_for_filling(df, "displacement 1", "displacement 2")
    axes[1].fill_between(df["time"], D2_trans, color=D2_col, alpha=0.1)

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


def ChangeButtonColour(label, background, font="black", border="transparent"):
    htmlstr = f"""
        <script>
            var elements = window.parent.document.querySelectorAll('button');
            for (var i = 0; i < elements.length; ++i) {{
                if (elements[i].innerText == '{label}') {{
                    elements[i].style.color ='{font}';
                    elements[i].style.background = '{background}';
                    elements[i].style.border = '1px solid {border}';
                }}
            }}
        </script>
        """
    components.html(f"{htmlstr}", height=0, width=0)


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
        st.session_state["first_controller_run"] = False
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
# Change button colours
ChangeButtonColour("Download experiment configuration", background="blue", font="white")
ChangeButtonColour("Send experiment configuration", background="green", font="white")
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
        st.session_state["first_controller_run"] = True
        if payload["uid"] == st.session_state["await_uuid"]:
            container_label_and_text("   Sensors configured successfully.")
            container_label_and_text("Starting experiment...")
    elif msg.topic == "controller/run":
        if st.session_state["first_controller_run"]:
            text = "Experiment started successfully!"
            container_label_and_text(text)
            st.session_state["status_container"].update(state="complete")
            st.session_state["first_controller_run"] = False
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
        st.session_state["first_controller_run"] = False


if "mqtt_client" not in st.session_state:
    mqtt_config = json.load(open("/etc/ui/config.json"))
    client = mqtt.Client(client_id="ui",
                         callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         protocol=mqtt.MQTTv311)
    client.on_message = on_message
    client.username_pw_set(
        username=mqtt_config["user"],
        password=mqtt_config["password"],
    )
    client.connect(mqtt_config["broker_address"], 1883, 60)

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
