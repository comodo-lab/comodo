import yaml

def resolve_refs(schema, spec):
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"].lstrip("#/")
            parts = ref_path.split("/")
            resolved = spec
            for part in parts:
                resolved = resolved[part]
            return resolve_refs(resolved, spec)
        return {k: resolve_refs(v, spec) for k, v in schema.items()}
    if isinstance(schema, list):
        return [resolve_refs(item, spec) for item in schema]
    return schema


def load_spec():
    with open('/app/asyncapi.yaml') as f:
        spec = yaml.safe_load(f)

    # Get channels object
    channels = spec.get("channels", {})

    # Iterate over channels to get addresses and messages
    topic_map = {}
    for ch_name, ch_def in channels.items():
        address = ch_def.get("address")
        if not address:
            continue
        messages = ch_def.get("messages", {})
        if not messages:
            continue
        first_msg = next(iter(messages.values()))
        payload_ref = first_msg.get("payload", {})
        schema = resolve_refs(payload_ref, spec)
        topic_map[address] = {"name": ch_name, "schema": schema}
    return topic_map
