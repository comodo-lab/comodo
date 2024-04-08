import os
import json
from datetime import datetime, timedelta
import influxdb_client
import csv
import pytest
from influxdb_client.client.write_api import SYNCHRONOUS

from controller_helper import data_path


def test_influxdb_data_files_exist():
    assert not os.path.exists("data/tmp/influx_test/heartbeat.csv")
    assert not os.path.exists("data/tmp/influx_test/logs.csv")
    assert not os.path.exists("data/tmp/influx_test/measurement.csv")

    t0 = datetime.now() - timedelta(hours=4)
    tf = datetime.now() - timedelta(hours=1)

    config = json.load(open("config.json"))
    buckets = config["influxdb"]["buckets"]
    secret = json.load(open(".secret_influxdb_token.json"))

    client = influxdb_client.InfluxDBClient(
        url=config["influxdb"]["url"],
        token=secret["influxdb_token"],
        org=config["influxdb"]["org"],
    )

    query_api = client.query_api()
    exp_dir_path = f"{data_path}/tmp/influx_test"
    if not os.path.exists(exp_dir_path):
        os.makedirs(exp_dir_path)

    for bucket in buckets:
        query = f'from(bucket: "{bucket}") |> range(start: {t0.isoformat()}Z, stop: {tf.isoformat()}Z)'
        data = query_api.query_csv(org=config["influxdb"]["org"], query=query)
        values = data.to_values()
        with open(f"{exp_dir_path}/{bucket}.csv", "w", newline="") as myfile:
            wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
            wr.writerows(values)

    expected_files = ["heartbeat.csv", "logs.csv", "measurement.csv"]
    for file in expected_files:
        assert os.path.exists(f"{exp_dir_path}/{file}")

    # Clean up: delete the files and the folder
    for bucket in buckets:
        file_path = f"{exp_dir_path}/{bucket}.csv"
        if os.path.exists(file_path):
            os.remove(file_path)
    os.rmdir(exp_dir_path)
