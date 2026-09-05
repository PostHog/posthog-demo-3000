"""Identity instability patterns."""

import random
from datetime import timedelta


def _user_id_int(user):
    """Stable positive int seed from a user dict (uses 'email' field)."""
    return abs(hash(user.get('email', ''))) & 0x7FFFFFFF


def maybe_identify_user(posthog_client, user, distinct_id, timestamp, session_props, probability=0.10, groups=None):
    """For ~10% of users, emit a $identify-shaped event so they become identified.
    Returns True if identified.

    PostHog Python SDK 7.x: identify is sent as capture('$identify', ..., $set=...).
    """
    rng = random.Random(_user_id_int(user))
    if rng.random() < probability:
        posthog_client.capture(
            distinct_id=distinct_id,
            event="$identify",
            properties={
                "$set": {
                    'email': user.get('email'),
                    'plan': user.get('plan'),
                    'is_adult': user.get('is_adult'),
                },
                **session_props,
                "$lib": "web",
            },
            timestamp=timestamp,
            groups=groups or {},
        )
        return True
    return False


def unstable_distinct_ids(user, base_distinct_id):
    """For ~5% of users, simulate distinct_id instability: their session uses one ID,
    then unexpectedly switches to a different ID without an alias call.

    Returns a list of distinct_ids; caller picks one randomly per event so the same
    user appears under 2-3 different IDs across their events. For the other 95%, returns [base_distinct_id].
    """
    rng = random.Random(_user_id_int(user) * 17)
    if rng.random() >= 0.05:
        return [base_distinct_id]
    n_alts = rng.randint(1, 2)
    return [base_distinct_id] + [f"{base_distinct_id}-alt-{i}" for i in range(n_alts)]


def flag_flip_pattern(posthog_client, user, distinct_id, timestamp, session_props, flag_name="action_mode_on", groups=None):
    """For ~5% of users, emit events with conflicting `$feature/<flag>` values pre and post identify.

    Pre-identify: anonymous, flag = "control".
    Post-identify: identified, flag = "test".
    """
    rng = random.Random(_user_id_int(user) * 31)
    if rng.random() >= 0.05:
        return

    # Pre-identify event
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$pageview",
        properties={
            **session_props,
            f"$feature/{flag_name}": "control",
            "$active_feature_flags": [flag_name],
            "$lib": "web",
        },
        timestamp=timestamp,
        groups=groups or {},
    )

    # Identify call (via capture)
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$identify",
        properties={
            "$set": {
                'email': user.get('email'),
                'plan': user.get('plan'),
            },
            **session_props,
            "$lib": "web",
        },
        timestamp=timestamp + timedelta(minutes=2),
        groups=groups or {},
    )

    # Post-identify event with flipped flag
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$pageview",
        properties={
            **session_props,
            f"$feature/{flag_name}": "test",
            "$active_feature_flags": [flag_name],
            "$lib": "web",
        },
        timestamp=timestamp + timedelta(minutes=3),
        groups=groups or {},
    )
