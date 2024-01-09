import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt

def make_plot(df):
    fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True)

    # Subplot 1: temperature on the main y-axis, pressure on the secondary
    df.plot(x='time', y='temperature', ax=axes[0])
    df['pressure'].plot(secondary_y=True, ax=axes[0])
    axes[0].set_ylabel('temperature')
    axes[0].right_ax.set_ylabel('pressure')
    lines = axes[0].get_lines() + axes[0].right_ax.get_lines()
    axes[0].legend(lines, [line.get_label() for line in lines])
    
    # Subplot 2: displacement 1 on the main y-axis, displacement 2 on the secondary
    df.plot(x='time', y='displacement 1', ax=axes[1], color='red')
    df['displacement 2'].plot(secondary_y=True, ax=axes[1], color='green')
    axes[1].set_ylabel('displacement 1')
    axes[1].right_ax.set_ylabel('displacement 2')
    lines = axes[1].get_lines() + axes[1].right_ax.get_lines()
    axes[1].legend(lines, [line.get_label() for line in lines])

    plt.subplots_adjust(hspace=0)  
    st.session_state['plot_container'].pyplot(fig)

# -----------------------------------------------------------------------------
# Page config

st.set_page_config(page_title=None,
                   page_icon=None,
                   layout="wide",
                   initial_sidebar_state="auto",
                   menu_items=None)

# -----------------------------------------------------------------------------
# Site layout

st.header("Welecome to the config panel")

col1, col2 = st.columns(2)

with col1:
    uploaded_file = st.file_uploader("Choose a file")
    
    if 'dataframe_container' not in st.session_state:
        st.session_state['dataframe_container'] = st.empty()

    if 'download_container' not in st.session_state:
        st.session_state['download_container'] = st.empty()

with col2:
    if 'plot_container' not in st.session_state:
        st.session_state['plot_container'] = st.empty()

# -----------------------------------------------------------------------------
# Site logic

if uploaded_file is not None:
    input_file = json.load(uploaded_file)

    edited_df = \
        st.session_state['dataframe_container'].data_editor(
            pd.DataFrame(input_file["experiment"]),
            hide_index=True,
            num_rows="dynamic"
        )
    make_plot(edited_df)
    
    output_data = input_file
    experiment_json = edited_df.transpose().to_json()
    output_data['experiment'] = json.loads(experiment_json)
    st.session_state['download_container'].download_button(
        label="Download config",
        data=json.dumps(output_data).encode('utf-8'),
        file_name='config.json',
        mime='application/json',
    )
