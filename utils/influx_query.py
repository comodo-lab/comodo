import influxdb_client
import os


URL = os.environ['INFLUX_ADDR']
TOKEN = os.environ['INFLUX_TOKEN']
ORG = os.environ['INFLUX_ORG']
BUCKET = os.environ['INFLUX_BUCKET']


def query_influxdb(query):
    """
    Queries the InfluxDB with the given query string.

    Args:
        query (str): The InfluxDB query string.

    Returns:
        list: The results of the query.
    """
    client = influxdb_client.InfluxDBClient(url=URL, token=TOKEN, org=ORG)
    query_api = client.query_api()

    try:
        result = query_api.query(query, org=ORG)
        return [record for table in result for record in table.records]
    finally:
        client.close()


def query_influxdb_params(fields=[], topics=[], start=None, stop=None, aggregate="last"):
    """
    Queries the InfluxDB for specific parameters within a time range.

    Args:
        fields (list): List of field names to query.
        topics (list): List of topic names to filter by.
        start (str): Start time in ISO format.
        stop (str): Stop time in ISO format.

    Returns:
        list: The results of the query.
    """
    aggregate_allowed = ["last", "mean", "min", "max", "sum"]
    if aggregate not in aggregate_allowed:
        raise ValueError(f"Aggregate function must be one of {aggregate_allowed}, got '{aggregate}'.")
    if not fields:
        raise ValueError("No parameters specified for query.")
    if not start:
        raise ValueError("Start time must be specified for query.")

    if stop is None:
        time_filter = f"|> range(start: {start})"
    else:
        time_filter = f"|> range(start: {start}, stop: {stop})"

    if len(fields) > 0:
        field_filter = '|> filter(fn: (r) => ' + ' or '.join([f'r["_field"] == "{field}"' for field in fields]) + ')'
    else:
        field_filter = ''
    if len(topics) > 0:
        topic_filter = '|> filter(fn: (r) => ' + ' or '.join([f'r["topic"] == "{topic}"' for topic in topics]) + ')'
    else:
        topic_filter = ''

    query = f"""
    from(bucket: "{BUCKET}")
      {time_filter}
      {field_filter}
      {topic_filter}
      |> yield(name: "{aggregate}")
    """

    return query_influxdb(query)
