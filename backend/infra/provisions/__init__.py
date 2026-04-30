from . import headlamp, free5gc

REGISTRY = {
    "headlamp": headlamp,
    "free5gc": free5gc,
}


def get(provision_type: str):
    if provision_type not in REGISTRY:
        raise ValueError(f"Unknown provision type '{provision_type}'")
    return REGISTRY[provision_type]


def has(provision_type: str) -> bool:
    return provision_type in REGISTRY
