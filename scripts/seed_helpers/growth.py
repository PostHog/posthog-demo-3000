"""Growth curve and behavioral cohort distribution."""

from datetime import datetime, timedelta
import random

SEED = 42


def daily_user_count(days_ago: int, total_days: int = 120) -> int:
    """Number of active users (with at least one event) on the day N days ago.

    Growth curve from 50 active users at the start of the data window (days_ago=120)
    to 250 at the end (days_ago=0). Weekday baseline; weekends bumped 1.4x.
    """
    progress = (total_days - days_ago) / total_days
    base = 50 + (200 * progress)
    weekday = (datetime.now() - timedelta(days=days_ago)).weekday()
    weekend_factor = 1.4 if weekday >= 5 else 1.0
    return int(base * weekend_factor)


def behavioral_profile(user_id: int) -> str:
    """Deterministic mapping of user_id to one of: power, casual, churned, bouncer."""
    rng = random.Random(user_id)
    r = rng.random()
    if r < 0.05:
        return "power"
    if r < 0.80:
        return "casual"  # 0.05 + 0.75
    if r < 0.95:
        return "churned"  # +0.15
    return "bouncer"  # remaining 0.05


def events_per_session(profile: str) -> int:
    """How many events one session produces, by behavior cohort."""
    return {
        "power": random.randint(20, 50),
        "casual": random.randint(3, 15),
        "churned": random.randint(2, 10),
        "bouncer": random.randint(1, 3),
    }[profile]


def is_user_active_on_day(user_id: int, days_ago: int, signup_days_ago: int) -> bool:
    """Determines whether a user is active on a given day based on profile + tenure.

    - power: active most days after signup
    - casual: active on ~30% of days after signup
    - churned: active for first 60 days after signup, then never
    - bouncer: active for first 1-3 days after signup, then never
    """
    if days_ago > signup_days_ago:
        return False  # hasn't signed up yet
    days_since_signup = signup_days_ago - days_ago
    profile = behavioral_profile(user_id)
    rng = random.Random(user_id * 1000 + days_ago)
    if profile == "power":
        return rng.random() < 0.7
    if profile == "casual":
        return rng.random() < 0.3
    if profile == "churned":
        return days_since_signup <= 60 and rng.random() < 0.4
    if profile == "bouncer":
        return days_since_signup <= rng.randint(1, 3)
    return False
