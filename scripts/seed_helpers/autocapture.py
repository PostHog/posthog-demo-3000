"""Synthesize $autocapture, $rageclick, and $dead_click events.

These mimic the element chains PostHog's web SDK would emit on real Hogflix
pages so the seed data has realistic click signal for autocapture-driven
insights, heatmaps, and rageclick/dead-click detection.
"""

import random


# Realistic-looking element chains per Hogflix page. Each entry is a list of
# possible click targets; each target is itself a chain of elements (innermost
# first), modeled after PostHog's real $elements payloads.
#
# Pages covered match what scripts/seed_demo_data.py actually emits pageviews
# for: /, /plans, /signup, /movie/<id>. /movies, /checkout, /account are added
# for forward compatibility with future seed flows.
_PAGE_ELEMENT_CHAINS = {
    "/": [
        # Hero "Sign up free" CTA
        [
            {"tag_name": "button", "text": "Sign up free", "attr__class": "btn btn-primary hero__cta", "attr__data-attr": "hero-signup-cta", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "div", "attr__class": "hero__actions", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "hero hero--home", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--home", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # "Browse movies" link
        [
            {"tag_name": "a", "text": "Browse movies", "attr__class": "btn btn-secondary", "attr__href": "/movies", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "div", "attr__class": "hero__actions", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "hero hero--home", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--home", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Top-nav "Plans" link
        [
            {"tag_name": "a", "text": "Plans", "attr__class": "nav__link", "attr__href": "/plans", "nth_child": 3, "nth_of_type": 3},
            {"tag_name": "ul", "attr__class": "nav__list", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "nav", "attr__class": "site-nav", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "header", "attr__class": "site-header", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
    "/movies": [
        # Movie tile click
        [
            {"tag_name": "a", "text": "Hogfather", "attr__class": "movie-tile movie-tile--featured", "attr__href": "/movie/1", "attr__data-movie-id": "1", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "li", "attr__class": "movie-grid__item", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "ul", "attr__class": "movie-grid", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--movies", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Genre filter dropdown
        [
            {"tag_name": "button", "text": "Genre: All", "attr__class": "filter-dropdown__trigger", "attr__data-attr": "filter-genre", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "div", "attr__class": "filter-dropdown filter-dropdown--genre", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "movies__filters", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--movies", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # "Upgrade plan" upsell banner
        [
            {"tag_name": "button", "text": "Upgrade to watch", "attr__class": "btn btn-upgrade upsell__cta", "attr__data-attr": "movies-upsell", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "div", "attr__class": "upsell upsell--inline", "nth_child": 3, "nth_of_type": 2},
            {"tag_name": "main", "attr__class": "page page--movies", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
    "/movie": [
        # Watch now (primary action)
        [
            {"tag_name": "button", "text": "Watch now", "attr__class": "btn btn-primary movie__watch", "attr__data-attr": "movie-watch-now", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "div", "attr__class": "movie__actions", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "movie__hero", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--movie", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Add to family list
        [
            {"tag_name": "button", "text": "Add to family list", "attr__class": "btn btn-secondary movie__add-family", "attr__data-attr": "movie-add-family", "nth_child": 2, "nth_of_type": 2},
            {"tag_name": "div", "attr__class": "movie__actions", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "movie__hero", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--movie", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Rent
        [
            {"tag_name": "button", "text": "Rent $4.99", "attr__class": "btn btn-tertiary movie__rent", "attr__data-attr": "movie-rent", "nth_child": 3, "nth_of_type": 3},
            {"tag_name": "div", "attr__class": "movie__actions", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "movie__hero", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--movie", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Buy
        [
            {"tag_name": "button", "text": "Buy $14.99", "attr__class": "btn btn-tertiary movie__buy", "attr__data-attr": "movie-buy", "nth_child": 4, "nth_of_type": 4},
            {"tag_name": "div", "attr__class": "movie__actions", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "movie__hero", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--movie", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
    "/checkout": [
        # Confirm purchase
        [
            {"tag_name": "button", "text": "Confirm purchase", "attr__class": "btn btn-primary checkout__confirm", "attr__data-attr": "checkout-confirm", "attr__type": "submit", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "form", "attr__class": "checkout__form", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "checkout", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--checkout", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Plan radio (Premium)
        [
            {"tag_name": "input", "attr__class": "plan-radio plan-radio--premium", "attr__type": "radio", "attr__name": "plan", "attr__value": "premium", "nth_child": 2, "nth_of_type": 2},
            {"tag_name": "label", "text": "Premium $14.99/mo", "attr__class": "plan-radio__label", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "fieldset", "attr__class": "checkout__plans", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "form", "attr__class": "checkout__form", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--checkout", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
    "/account": [
        # Cancel subscription
        [
            {"tag_name": "button", "text": "Cancel subscription", "attr__class": "btn btn-danger account__cancel", "attr__data-attr": "account-cancel", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "div", "attr__class": "account__danger-zone", "nth_child": 4, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "account__settings", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--account", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Save settings
        [
            {"tag_name": "button", "text": "Save changes", "attr__class": "btn btn-primary account__save", "attr__type": "submit", "nth_child": 3, "nth_of_type": 1},
            {"tag_name": "form", "attr__class": "account__form", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "account__settings", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--account", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
    "/plans": [
        # Standard plan card -> Subscribe
        [
            {"tag_name": "button", "text": "Subscribe", "attr__class": "btn btn-primary plan-card__cta", "attr__data-plan": "standard", "nth_child": 4, "nth_of_type": 1},
            {"tag_name": "article", "attr__class": "plan-card plan-card--standard", "nth_child": 2, "nth_of_type": 2},
            {"tag_name": "div", "attr__class": "plans__grid", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--plans", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Premium plan card -> Subscribe
        [
            {"tag_name": "button", "text": "Subscribe", "attr__class": "btn btn-primary plan-card__cta", "attr__data-plan": "premium", "nth_child": 4, "nth_of_type": 1},
            {"tag_name": "article", "attr__class": "plan-card plan-card--premium plan-card--featured", "nth_child": 3, "nth_of_type": 3},
            {"tag_name": "div", "attr__class": "plans__grid", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--plans", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Compare plans toggle
        [
            {"tag_name": "button", "text": "Compare plans", "attr__class": "btn btn-link plans__compare-toggle", "attr__data-attr": "plans-compare", "nth_child": 3, "nth_of_type": 1},
            {"tag_name": "section", "attr__class": "plans__intro", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--plans", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
    "/signup": [
        # Email input
        [
            {"tag_name": "input", "attr__class": "form-input form-input--email", "attr__type": "email", "attr__name": "email", "attr__placeholder": "you@example.com", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "label", "text": "Email address", "attr__class": "form-field__label", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "form", "attr__class": "signup__form", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--signup", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Continue button
        [
            {"tag_name": "button", "text": "Continue", "attr__class": "btn btn-primary signup__continue", "attr__type": "submit", "attr__data-attr": "signup-continue", "nth_child": 3, "nth_of_type": 1},
            {"tag_name": "form", "attr__class": "signup__form", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--signup", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
        # Sign in link (already have an account)
        [
            {"tag_name": "a", "text": "Sign in", "attr__class": "signup__signin-link", "attr__href": "/login", "nth_child": 1, "nth_of_type": 1},
            {"tag_name": "p", "attr__class": "signup__footer", "nth_child": 4, "nth_of_type": 1},
            {"tag_name": "main", "attr__class": "page page--signup", "nth_child": 2, "nth_of_type": 1},
            {"tag_name": "body", "attr__class": "theme-dark", "nth_child": 2, "nth_of_type": 1},
        ],
    ],
}


def _resolve_page_key(page: str) -> str:
    """Map a real pathname to a key in _PAGE_ELEMENT_CHAINS.

    Handles dynamic segments like /movie/<id> and /movie/<id>/watch by matching
    on prefix. Falls back to homepage chains for unknown pages so we never
    crash mid-seed.
    """
    if not page or page == "/":
        return "/"
    # Match longest known prefix first. Order matters: /movies before /movie.
    for prefix in ("/checkout", "/account", "/plans", "/signup", "/movies", "/movie"):
        if page == prefix or page.startswith(prefix + "/"):
            return prefix
    return "/"


def _make_element_chain(page: str) -> list:
    """Generate a realistic element chain for a click on a typical Hogflix page.

    Returns a list of 3-5 element dicts ordered innermost-first (the clicked
    element comes first, body comes last). One of several plausible chains for
    the page is picked at random, so the seed produces varied $elements payloads
    instead of a single repeated pattern.
    """
    key = _resolve_page_key(page)
    chains = _PAGE_ELEMENT_CHAINS.get(key) or _PAGE_ELEMENT_CHAINS["/"]
    # Shallow copy so callers can mutate without poisoning the catalog.
    return [dict(el) for el in random.choice(chains)]


def synthesize_autocapture(posthog_client, distinct_id, page, timestamp, session_props, groups=None):
    """Emit a $autocapture event for a click on a typical Hogflix page element."""
    elements = _make_element_chain(page)
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$autocapture",
        properties={
            **session_props,
            "$current_url": f"https://hogflix.net{page}",
            "$pathname": page,
            "$event_type": "click",
            "$elements": elements,
            "$lib": "web",
        },
        timestamp=timestamp,
        groups=groups or {},
    )


def synthesize_rageclick(posthog_client, distinct_id, page, timestamp, session_props, groups=None):
    """Emit a $rageclick event (3+ rapid clicks on same element)."""
    elements = _make_element_chain(page)
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$rageclick",
        properties={
            **session_props,
            "$current_url": f"https://hogflix.net{page}",
            "$pathname": page,
            "$event_type": "click",
            "$elements": elements,
            "$click_count": random.randint(4, 6),
            "$lib": "web",
        },
        timestamp=timestamp,
        groups=groups or {},
    )


def synthesize_dead_click(posthog_client, distinct_id, page, timestamp, session_props, groups=None):
    """Emit a $dead_click event (click with no DOM change)."""
    elements = _make_element_chain(page)
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$dead_click",
        properties={
            **session_props,
            "$current_url": f"https://hogflix.net{page}",
            "$pathname": page,
            "$event_type": "click",
            "$elements": elements,
            "$lib": "web",
        },
        timestamp=timestamp,
        groups=groups or {},
    )
