import json
import textwrap

from validation import validate_experiment_soft


def on_ui_message(client, msg, obj):
    experiment = msg.payload.decode("utf-8")
    try:
        experiment = json.loads(experiment)
        uid = experiment["uid"]
    except json.JSONDecodeError as e:
        client.publish(
            "/controller/error",
            f"Error decoding ui message, wrong JSON: \n{textwrap.indent(str(e), '   ')}",
        )
        return
    except KeyError as e:
        client.publish(
            "/controller/error",
            f"Error decoding ui message, missing: \n{textwrap.indent(str(e), '   ')}",
        )
        return

    if obj.status == "idle":
        if msg.topic == "/ui/start":
            obj.experiment_uid = uid
            exp_file = f"data/experiment_{obj.experiment_uid}.json"
            with open(exp_file, "w") as f:
                json.dump(experiment, f)
            obj.status = "validating"
            exp_config, err = validate_experiment_soft(exp_file, obj.schema_path)
            if err == None:
                m = {
                    "uid": obj.experiment_uid,
                    "valid": True,
                }
                client.publish("/controller/validator/passed", json.dumps(m))
                obj.exp_config = exp_config
                obj.status = "starting"
            else:
                m = {
                    "uid": obj.experiment_uid,
                    "valid": False,
                    "error": err,
                }
                client.publish("/controller/validator/failed", json.dumps(m))
                obj.experiment_uid = None
                obj.status = "idle"
        else:
            client.publish(
                "/controller/error",
                f"Status is {obj.status}. Cannot act on {msg.topic}",
            )
    else:
        if msg.topic == "/ui/stop":
            if uid == obj.experiment_uid:
                obj.status = "stopping"
                client.publish(
                    "/controller/stop",
                    f"Received stop command for experiment {obj.experiment_uid}",
                )
            else:
                client.publish(
                    "/controller/error",
                    f"Experiment {obj.experiment_uid} is {obj.status}. Cannot act on {msg.topic} for experiment {experiment['uid']}",
                )
        else:
            client.publish(
                "/controller/error",
                f"Experiment {obj.experiment_uid} is {obj.status}. Cannot act on {msg.topic}",
            )
