#!/usr/bin/env python3
import os
import json
import hashlib
import yaml


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMODO_YAML = os.path.join(REPO_ROOT, "comodo.yaml")
DASHBOARDS_DIR = os.path.join(REPO_ROOT, "grafana", "dashboards")
OLD_DASHBOARD = os.path.join(DASHBOARDS_DIR, "Comodo State Testing-1750951675844.json")

DATASOURCE_UID = "bere8a3gzy800d"
BUCKET = "comodo"

FIRMWARE_GROUPS = {
    "carbolite_gero": "furnaces",
    "pfeiffer": "pressures",
    "bronkhorst": "mass_flow",
}

# Copied verbatim from existing dashboard panel 1
STATE_TIMELINE_QUERY = (
    'import "strings"\n\nfrom(bucket: "comodo")\n'
    '  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
    '  |> filter(fn: (r) => r._measurement == "mqtt_consumer")\n'
    '  |> filter(fn: (r) => r.topic =~ /^heartbeat\\/.*/)\n'
    '  |> filter(fn: (r) => r._field == "status")\n'
    '  |> map(fn: (r) => {\n'
    '      parts = strings.split(v: r.topic, t: "/")\n'
    '      lastIndex = length(arr: parts) - 1\n'
    '      return { r with topic_last: parts[lastIndex] }\n'
    '    })\n'
    '  |> keep(columns: ["_time","_value","topic_last"])\n'
    '  |> group(columns: ["topic_last"], mode: "by")\n'
    '  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)\n'
    '  |> yield(name: "last")\n'
)

SETPOINT_OVERRIDE = {
    "matcher": {"id": "byRegexp", "options": "/.*setpoint.*/"},
    "properties": [
        {"id": "custom.lineInterpolation", "value": "stepAfter"},
        {"id": "custom.showPoints", "value": "always"},
        {"id": "custom.lineStyle", "value": {"dash": [0, 10], "fill": "dot"}},
    ],
}


def make_uid(name):
    return hashlib.md5(name.encode()).hexdigest()[:16]


def load_instruments():
    with open(COMODO_YAML) as f:
        config = yaml.safe_load(f)
    return config.get("instruments", {})


def group_instruments(instruments):
    groups = {}
    for inst_id, inst_cfg in instruments.items():
        firmware = inst_cfg.get("firmware", "")
        prefix = firmware.split("/")[0]
        group = FIRMWARE_GROUPS.get(prefix, "other")
        groups.setdefault(group, []).append((inst_id, inst_cfg))
    return groups


def measurement_query(instrument_id, variable):
    label = f"{instrument_id} {variable}"
    return (
        f'from(bucket: "{BUCKET}")\n'
        f'  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")\n'
        f'  |> filter(fn: (r) => r["topic"] == "measurement/{instrument_id}/{variable}")\n'
        f'  |> filter(fn: (r) => r["_field"] == "value")\n'
        f'  |> map(fn: (r) => ({{r with _field: "{label}"}}))\n'
        f'  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)\n'
        f'  |> yield(name: "mean")\n'
    )


def setpoint_query(instrument_id):
    label = f"{instrument_id} setpoint"
    return (
        f'from(bucket: "{BUCKET}")\n'
        f'  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")\n'
        f'  |> filter(fn: (r) => r["topic"] == "heartbeat/instrument/{instrument_id}")\n'
        f'  |> filter(fn: (r) => r["_field"] == "setpoint")\n'
        f'  |> map(fn: (r) => ({{r with _field: "{label}"}}))\n'
        f'  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)\n'
        f'  |> yield(name: "setpoint")\n'
    )


def make_target(query, rid):
    return {"query": query, "refId": rid}


def ref_id(n):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n < 26:
        return alphabet[n]
    return alphabet[n // 26 - 1] + alphabet[n % 26]


def make_timeseries_panel(panel_id, title, targets, grid_pos, has_setpoints=False):
    overrides = [SETPOINT_OVERRIDE] if has_setpoints else []
    return {
        "datasource": {"type": "influxdb", "uid": DATASOURCE_UID},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisBorderShow": False,
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "barWidthFactor": 0.6,
                    "drawStyle": "line",
                    "fillOpacity": 0,
                    "gradientMode": "none",
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "insertNulls": False,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {"type": "linear"},
                    "showPoints": "auto",
                    "showValues": False,
                    "spanNulls": False,
                    "stacking": {"group": "A", "mode": "none"},
                    "thresholdsStyle": {"mode": "off"},
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": 0}, {"color": "red", "value": 80}],
                },
            },
            "overrides": overrides,
        },
        "gridPos": grid_pos,
        "id": panel_id,
        "options": {
            "legend": {"calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"hideZeros": False, "mode": "single", "sort": "none"},
        },
        "pluginVersion": "12.3.0",
        "targets": targets,
        "title": title,
        "type": "timeseries",
    }


def make_state_timeline_panel(panel_id, grid_pos):
    return {
        "datasource": {"uid": "Comodo"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "continuous-GrYlRd"},
                "custom": {
                    "axisPlacement": "auto",
                    "fillOpacity": 70,
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "insertNulls": False,
                    "lineWidth": 0,
                    "spanNulls": False,
                },
                "mappings": [
                    {
                        "options": {
                            "awaiting_instruments": {"color": "dark-orange", "index": 5, "text": "Awaiting Instruments"},
                            "end": {"color": "dark-purple", "index": 3, "text": "End"},
                            "idle": {"color": "dark-blue", "index": 1, "text": "Idle"},
                            "ready": {"color": "dark-yellow", "index": 2, "text": "Ready"},
                            "running": {"color": "dark-green", "index": 0, "text": "Running"},
                            "starting": {"color": "dark-red", "index": 4, "text": "Starting"},
                        },
                        "type": "value",
                    }
                ],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": 0}],
                },
            },
            "overrides": [],
        },
        "gridPos": grid_pos,
        "id": panel_id,
        "options": {
            "alignValue": "left",
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "mergeValues": True,
            "rowHeight": 0.9,
            "showValue": "auto",
            "tooltip": {"hideZeros": False, "mode": "single", "sort": "none"},
        },
        "pluginVersion": "12.3.0",
        "targets": [{"query": STATE_TIMELINE_QUERY, "refId": "A"}],
        "title": "Comodo Status",
        "type": "state-timeline",
    }


def make_row_panel(panel_id, title, grid_pos):
    return {
        "collapsed": False,
        "gridPos": grid_pos,
        "id": panel_id,
        "title": title,
        "type": "row",
    }


def make_text_panel(panel_id, title, content, grid_pos):
    return {
        "gridPos": grid_pos,
        "id": panel_id,
        "options": {"content": content, "mode": "markdown"},
        "title": title,
        "type": "text",
    }


def make_dashboard(title, uid, panels):
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 0,
        "id": None,
        "links": [],
        "panels": panels,
        "preload": False,
        "refresh": "auto",
        "schemaVersion": 42,
        "tags": [],
        "templating": {"list": []},
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
    }


def write_dashboard(path, dashboard):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"Written: {path}")


def generate_overview(groups):
    panels = []
    pid = 1

    panels.append(make_state_timeline_panel(pid, {"h": 8, "w": 24, "x": 0, "y": 0}))
    pid += 1

    y = 8
    for group_name, group_label in [("furnaces", "Furnaces"), ("pressures", "Pressures"), ("mass_flow", "Mass Flow")]:
        group_insts = groups.get(group_name, [])
        if not group_insts:
            continue

        panels.append(make_row_panel(pid, group_label, {"h": 1, "w": 24, "x": 0, "y": y}))
        pid += 1
        y += 1

        targets = []
        has_setpoints = False
        n = 0

        for inst_id, inst_cfg in group_insts:
            for var_name, var_cfg in inst_cfg.get("variables", {}).items():
                targets.append(make_target(measurement_query(inst_id, var_name), ref_id(n)))
                n += 1
                if "actuator" in var_cfg:
                    targets.append(make_target(setpoint_query(inst_id), ref_id(n)))
                    n += 1
                    has_setpoints = True

        panels.append(make_timeseries_panel(pid, group_label, targets, {"h": 8, "w": 24, "x": 0, "y": y}, has_setpoints))
        pid += 1
        y += 8

    write_dashboard(
        os.path.join(DASHBOARDS_DIR, "overview.json"),
        make_dashboard("Comodo Overview", make_uid("overview"), panels),
    )


def generate_instrument_dashboards(instruments):
    for inst_id, inst_cfg in instruments.items():
        variables = list(inst_cfg.get("variables", {}).items())
        n_vars = len(variables)
        panels = []
        pid = 1

        for i, (var_name, var_cfg) in enumerate(variables):
            if n_vars == 1:
                grid_pos = {"h": 10, "w": 24, "x": 0, "y": 0}
            else:
                grid_pos = {"h": 10, "w": 12, "x": (i % 2) * 12, "y": (i // 2) * 10}

            is_actuator = "actuator" in var_cfg
            targets = [make_target(measurement_query(inst_id, var_name), "A")]
            if is_actuator:
                targets.append(make_target(setpoint_query(inst_id), "B"))

            title = var_name.replace("_", " ").title()
            panels.append(make_timeseries_panel(pid, title, targets, grid_pos, has_setpoints=is_actuator))
            pid += 1

        inst_title = inst_id.replace("_", " ").title()
        write_dashboard(
            os.path.join(DASHBOARDS_DIR, "instruments", f"{inst_id}.json"),
            make_dashboard(inst_title, make_uid(f"instrument_{inst_id}"), panels),
        )


def generate_experiment_progress():
    panels = [
        make_state_timeline_panel(1, {"h": 8, "w": 24, "x": 0, "y": 0}),
        make_text_panel(
            2,
            "Experiment Steps",
            (
                "## Experiment Progress\n\n"
                "Experiment step annotations will appear here once step logging is implemented.\n\n"
                "Step data will be published to MQTT and stored in InfluxDB for display alongside the state timeline."
            ),
            {"h": 6, "w": 24, "x": 0, "y": 8},
        ),
    ]
    write_dashboard(
        os.path.join(DASHBOARDS_DIR, "experiment", "progress.json"),
        make_dashboard("Experiment Progress", make_uid("experiment_progress"), panels),
    )


def main():
    instruments = load_instruments()
    groups = group_instruments(instruments)

    generate_overview(groups)
    generate_instrument_dashboards(instruments)
    generate_experiment_progress()

    if os.path.exists(OLD_DASHBOARD):
        os.remove(OLD_DASHBOARD)
        print(f"Removed: {OLD_DASHBOARD}")


if __name__ == "__main__":
    main()
