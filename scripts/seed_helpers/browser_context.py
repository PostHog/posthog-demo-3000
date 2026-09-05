"""Generate browser-context properties for a synthesized session."""


def make_session_properties(user_seed: int) -> dict:
    """Returns dict of $os/$browser/$referrer/UTM/$current_url-style properties for one session."""
    raise NotImplementedError  # populated in Phase 2
