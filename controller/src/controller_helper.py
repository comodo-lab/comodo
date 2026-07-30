import json
import numpy as np
import influxdb_client
import os
import csv
from datetime import datetime

import src.publish_error as pe


def get_env_or_secret(env_var, secret=None, default=None):
    """
    Get the value of an environment variable or from a secret file.
    If both are set, the environment variable takes precedence.
    If neither is set, return the default value.
    """
    value = os.getenv(env_var, None)
    if value is not None:
        return value
    secret_path = os.getenv(secret, None)
    if secret_path is None:
        return default
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


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
    influx_buckets = os.getenv("INFLUX_BUCKET", "comodo").split(",")
    influx_url = f"http://{os.getenv("INFLUX_HOST", "localhost")}:8086"
    influx_org = os.getenv("INFLUX_ORG", "comodo")
    influx_token = get_env_or_secret("INFLUX_TOKEN", "INFLUX_TOKEN_FILE", None)
    if influx_token is None:
        pe.database_error(f"Cannot dump influx database. INFLUX_TOKEN not set.")
        return

    t0 = obj.experiment_start_time
    tf = datetime.now()

    try:
        # get everything from influx database
        client = influxdb_client.InfluxDBClient(
            url=influx_url,
            token=influx_token,
            org=influx_org,
        )
        query_api = client.query_api()
        exp_dir_path = obj.exp_file.replace(".json", "")

        if not os.path.exists(exp_dir_path):
            os.makedirs(exp_dir_path)
        for bucket in influx_buckets:
            query = f'from(bucket: "{bucket}") |> range(start: {t0.isoformat()}Z, stop: {tf.isoformat()}Z)'
            data = query_api.query_csv(org=influx_org, query=query)
            values = data.to_values()
            with open(f"{exp_dir_path}/{bucket}.csv", "w", newline="") as myfile:
                wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
                wr.writerows(values)
        print(
            f"  Influx database for experiment {obj.experiment_uid} saved at {exp_dir_path}."
        )
    except Exception as e:
        pe.database_error(f"Could not dump influx database: {e}")
