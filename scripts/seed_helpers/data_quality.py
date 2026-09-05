"""Intentional data quality variants: typos, JSON-stringified values, format drift."""
import json
import random

EVENT_TYPO_MAP = {
    "subscription_purchased": "suscription_purchased",  # 'b' missing
    "movie_buy_complete": "movei_buy_complete",  # transposed letters
    "user_logged_in": "user_loged_in",  # 'g' missing
}


def apply_event_typo(event_name: str, user_id: int) -> str:
    """For ~1-2% of events deterministically, return a typo'd variant. Otherwise return the original."""
    rng = random.Random(f"{event_name}:{user_id}")
    if event_name in EVENT_TYPO_MAP and rng.random() < 0.015:
        return EVENT_TYPO_MAP[event_name]
    return event_name


def apply_property_typo(props: dict, user_id: int) -> dict:
    """Inconsistent property naming for the same concept across events.
    Examples: user_id vs userId vs userID, family_id vs familyId.
    For 1-2% of events, swap the canonical key with a variant.
    """
    typo_map = {"user_id": ["userId", "userID", "userid"]}
    new_props = dict(props)
    rng = random.Random(f"props:{user_id}")
    for canonical, variants in typo_map.items():
        if canonical in new_props and rng.random() < 0.015:
            variant = rng.choice(variants)
            new_props[variant] = new_props.pop(canonical)
    return new_props


def maybe_jsonify_property(props: dict, key: str, user_id: int, probability=0.05) -> dict:
    """For ~5% of events with the given key, replace the value with a JSON-stringified version (the bug: customer is sending an object as a JSON string instead of a structured property)."""
    rng = random.Random(f"json:{key}:{user_id}")
    if key in props and rng.random() < probability:
        new_props = dict(props)
        if isinstance(props[key], (dict, list)):
            new_props[key] = json.dumps(props[key])
        else:
            new_props[key] = json.dumps({"value": props[key], "type": type(props[key]).__name__})
        return new_props
    return props


def date_format_drift(date_value, user_id: int):
    """Sometimes return ISO Date, sometimes ISO DateTime, for the same field across events."""
    rng = random.Random(f"date:{user_id}")
    if rng.random() < 0.4:
        return date_value.date().isoformat()
    return date_value.isoformat()


def plan_name_drift(plan_name: str, user_id: int) -> str:
    """For 5-10% of plan-related events, use 'Maximal' (no hyphen) or 'Maxi-Mal' (alternate hyphenation) instead of 'Max-imal'."""
    if plan_name != "Max-imal":
        return plan_name
    rng = random.Random(f"plan:{user_id}")
    r = rng.random()
    if r < 0.07:
        return "Maximal"
    if r < 0.10:
        return "Maxi-Mal"
    return "Max-imal"
