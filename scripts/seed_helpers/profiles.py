"""Realistic device and referrer profiles for synthesized sessions."""

# DEVICE_PROFILES: list of dicts with $os, $os_version, $browser, $browser_version,
# $device_type, $screen_width, $screen_height (10-12 entries spanning
# Windows/Mac/iOS/Android, Chrome/Safari/Firefox/Edge/Mobile Safari)
DEVICE_PROFILES = []  # populated in Phase 2

# REFERRER_PROFILES: list of dicts with $referrer, $referring_domain,
# optional utm_source/medium/campaign (10-15 entries: Google organic, Twitter social,
# Product Hunt, $direct, etc.)
REFERRER_PROFILES = []  # populated in Phase 2

# USER_BEHAVIOR_COHORTS: dict mapping cohort name to weight,
# e.g. {"power": 0.05, "casual": 0.75, "churned": 0.15, "bouncer": 0.05}
USER_BEHAVIOR_COHORTS = {}  # populated in Phase 3
