"""Apply cost-amplifier patterns: pageleave spam, groupidentify spam, flag eval flood, identify spam, double-fire, anonymous profile creation."""

import random
from datetime import timedelta


def spam_pageleave(posthog_client, distinct_id, page, timestamp, session_props, count=3, groups=None):
    """Emit `count` $pageleave events for one page visit (the bug: app fires it on every click in addition to the autocapture)."""
    for i in range(count):
        posthog_client.capture(
            distinct_id=distinct_id,
            event="$pageleave",
            properties={**session_props, "$current_url": f"https://hogflix.net{page}", "$pathname": page, "$lib": "web"},
            timestamp=timestamp + timedelta(seconds=i * 5),
            groups=groups or {},
        )


def spam_groupidentify(posthog_client, distinct_id, group_type, group_key, group_props, timestamp):
    """Emit a $groupidentify event. The bug is that this fires on every page load - orchestrator calls this before every event in a session, not once per session."""
    posthog_client.group_identify(
        group_type=group_type,
        group_key=str(group_key),
        properties=group_props,
        distinct_id=distinct_id,
        timestamp=timestamp,
    )


def flag_eval_flood(posthog_client, distinct_id, flag_keys, timestamp, session_props, flood_count=8, groups=None):
    """Emit `flood_count` $feature_flag_called events per flag, simulating a re-evaluation loop."""
    for flag_key in flag_keys:
        for i in range(flood_count):
            posthog_client.capture(
                distinct_id=distinct_id,
                event="$feature_flag_called",
                properties={
                    **session_props,
                    "$feature_flag": flag_key,
                    "$feature_flag_response": "control" if i % 2 == 0 else "test",
                    "$lib": "web",
                },
                timestamp=timestamp + timedelta(seconds=i * 3),
                groups=groups or {},
            )


def identify_spam(posthog_client, distinct_id, timestamp, properties_to_set, count=5):
    """Emit `count` $identify events for the same user — bug: app calls identify() on every page load.

    PostHog Python SDK 7.x has no top-level identify(); $identify is sent as a
    regular capture() call with $set in properties.
    """
    for i in range(count):
        posthog_client.capture(
            distinct_id=distinct_id,
            event="$identify",
            properties={"$set": properties_to_set, "$lib": "web"},
            timestamp=timestamp + timedelta(seconds=i * 30),
        )


def double_fire_purchase(posthog_client, distinct_id, event_name, properties, timestamp, groups=None):
    """Emit the same purchase event twice within a few seconds."""
    posthog_client.capture(distinct_id=distinct_id, event=event_name, properties=properties, timestamp=timestamp, groups=groups or {})
    posthog_client.capture(distinct_id=distinct_id, event=event_name, properties=properties, timestamp=timestamp + timedelta(seconds=2), groups=groups or {})


def anonymous_profile_creation(posthog_client, distinct_id, timestamp, session_props):
    """Emit an $identify event for an anonymous distinct_id (no real user) so a person profile is created.
    Effect of person_profiles='always' on a real customer's instance: every anonymous browse session creates a billed person profile.

    PostHog Python SDK 7.x has no top-level identify(); $identify is sent as a
    regular capture() with $set in properties.
    """
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$identify",
        properties={
            "$set": {"session_started_at": timestamp.isoformat()},
            **session_props,
            "$lib": "web",
        },
        timestamp=timestamp,
    )
