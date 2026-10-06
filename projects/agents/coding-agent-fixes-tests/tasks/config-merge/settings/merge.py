def deep_merge(base, override):
    result = base
    for key, value in override.items():
        if isinstance(value, dict) and key in result:
            deep_merge(result[key], value)
        else:
            result[key] = value
    return result
