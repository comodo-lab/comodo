import json
import numpy as np
import influxdb_client
import os
import csv
from datetime import datetime

from utils.mqtt_clients import *
from error_helper import *


config = json.load(open("config/config.json"))

INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]


class internal_stop_msg:
    """
    Internal message to be passed to c_stopping, and stop the controller.
    It emulates the message components of a stop message from the UI.
    """

    def __init__(self, uid):
        self.topic = "controller/stop"
        p = {"uid": uid}
        self.payload = json.dumps(p).encode("utf-8")


data_path = "data"


def assign_serial_id(obj):
    """
    Assigns a serial id to the experiment, using the format: DYY-XXX,
    where YY is the last two digits of the current year, and XXX is a three digit serial.
    It then moves and renames the experiment file from tmp to to the data folder,
    and updates the cstate object accordingly.
    """
    temp_path = obj.exp_file
    current_year = str(datetime.now().year)[-2:]
    all_json = [f for f in os.listdir(data_path) if f.endswith(".json")]
    current_year_files = [f for f in all_json if f.startswith(f"D{current_year}-")]
    if len(current_year_files) == 0:
        serial = 1
    else:
        serials = [int(f.split("-")[1].split(".")[0]) for f in current_year_files]
        serials.sort()
        serial = serials[-1] + 1
    serial = str(serial).zfill(3)
    new_path = f"{data_path}/D{current_year}-{serial}.json"
    os.rename(temp_path, new_path)
    obj.experiment_uid = f"D{current_year}-{serial}"
    obj.exp_file = new_path


def dump_database_for_experiment(obj):
    """
    Dumps the influx databases for the experiment elapsed time.
    """
    t0 = obj.experiment_start_time
    tf = datetime.now()
    # get everything from influx database
    buckets = config["influxdb"]["buckets"]
    client = influxdb_client.InfluxDBClient(
        url="http://comodo-influx:8086",
        token=INFLUX_TOKEN,
        org=config["influxdb"]["org"],
    )
    query_api = client.query_api()
    exp_dir_path = obj.exp_file.replace(".json", "")
    if not os.path.exists(exp_dir_path):
        os.makedirs(exp_dir_path)
    # for bucket in buckets:
    #     query = f'from(bucket: "{bucket}") |> range(start: {t0.isoformat()}Z, stop: {tf.isoformat()}Z)'
    #     data = query_api.query_csv(org=config["influxdb"]["org"], query=query)
    #     values = data.to_values()
    #     with open(f"{exp_dir_path}/{bucket}.csv", "w", newline="") as myfile:
    #         wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
    #         wr.writerows(values)
