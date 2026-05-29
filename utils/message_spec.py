import yaml


def load_spec(path='/app/asyncapi.yaml'):
    with open(path) as f:
        spec = yaml.safe_load(f)

    channels = spec.get("channels", {})

    topic_map = {}
    for ch_name, ch_def in channels.items():
        address = ch_def.get("address")
        if not address:
            continue
        messages = ch_def.get("messages", {})
        if not messages:
            continue
        first_msg = next(iter(messages.values()))
        topic_map[address] = {"name": ch_name, "schema": first_msg.get("payload", {})}
    return topic_map
