"""Synthesize $exception events."""

import random

EXCEPTION_TEMPLATES = [
    {
        "$exception_type": "TypeError",
        "$exception_message": "Cannot read property 'price' of undefined",
        "$exception_list": [
            {
                "type": "TypeError",
                "value": "Cannot read property 'price' of undefined",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/checkout.js",
                            "lineno": 142,
                            "colno": 18,
                            "function": "computePrice",
                        },
                        {
                            "filename": "https://hogflix.net/static/js/checkout.js",
                            "lineno": 88,
                            "colno": 5,
                            "function": "renderCheckout",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "TypeError",
        "$exception_message": "Cannot read property 'plan' of null",
        "$exception_list": [
            {
                "type": "TypeError",
                "value": "Cannot read property 'plan' of null",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/account.js",
                            "lineno": 88,
                            "colno": 12,
                            "function": "renderAccountPlan",
                        },
                        {
                            "filename": "https://hogflix.net/static/js/account.js",
                            "lineno": 21,
                            "colno": 3,
                            "function": "initAccount",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "ReferenceError",
        "$exception_message": "posthog is not defined",
        "$exception_list": [
            {
                "type": "ReferenceError",
                "value": "posthog is not defined",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/analytics.js",
                            "lineno": 5,
                            "colno": 1,
                            "function": "trackPageview",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "SyntaxError",
        "$exception_message": "Unexpected token < in JSON at position 0",
        "$exception_list": [
            {
                "type": "SyntaxError",
                "value": "Unexpected token < in JSON at position 0",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/api.js",
                            "lineno": 201,
                            "colno": 22,
                            "function": "parseResponse",
                        },
                        {
                            "filename": "https://hogflix.net/static/js/api.js",
                            "lineno": 174,
                            "colno": 9,
                            "function": "fetchJson",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "TypeError",
        "$exception_message": "Failed to fetch",
        "$exception_list": [
            {
                "type": "TypeError",
                "value": "Failed to fetch",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/movie-detail.js",
                            "lineno": 67,
                            "colno": 14,
                            "function": "loadMovieDetail",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "RangeError",
        "$exception_message": "Maximum call stack size exceeded",
        "$exception_list": [
            {
                "type": "RangeError",
                "value": "Maximum call stack size exceeded",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/recursive-render.js",
                            "lineno": 23,
                            "colno": 7,
                            "function": "renderTree",
                        },
                        {
                            "filename": "https://hogflix.net/static/js/recursive-render.js",
                            "lineno": 23,
                            "colno": 7,
                            "function": "renderTree",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "Error",
        "$exception_message": "Network request failed",
        "$exception_list": [
            {
                "type": "Error",
                "value": "Network request failed",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/checkout.js",
                            "lineno": 189,
                            "colno": 11,
                            "function": "submitOrder",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "TypeError",
        "$exception_message": "Cannot set property 'innerHTML' of null",
        "$exception_list": [
            {
                "type": "TypeError",
                "value": "Cannot set property 'innerHTML' of null",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/homepage.js",
                            "lineno": 42,
                            "colno": 9,
                            "function": "renderHero",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "TypeError",
        "$exception_message": "video.play is not a function",
        "$exception_list": [
            {
                "type": "TypeError",
                "value": "video.play is not a function",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/player.js",
                            "lineno": 117,
                            "colno": 16,
                            "function": "startPlayback",
                        },
                        {
                            "filename": "https://hogflix.net/static/js/player.js",
                            "lineno": 54,
                            "colno": 4,
                            "function": "initPlayer",
                        },
                    ],
                },
            }
        ],
    },
    {
        "$exception_type": "Error",
        "$exception_message": "Unauthorized",
        "$exception_list": [
            {
                "type": "Error",
                "value": "Unauthorized",
                "stacktrace": {
                    "type": "raw",
                    "frames": [
                        {
                            "filename": "https://hogflix.net/static/js/auth.js",
                            "lineno": 55,
                            "colno": 13,
                            "function": "refreshToken",
                        },
                    ],
                },
            }
        ],
    },
]


def synthesize_exception(posthog_client, distinct_id, timestamp, session_props, groups=None, template_idx=None):
    """Emit a single $exception event using one of the predefined templates.

    Args:
        posthog_client: A PostHog client with a `.capture(...)` method.
        distinct_id: The distinct_id to attribute the event to.
        timestamp: The event timestamp (datetime).
        session_props: Base session properties merged into the event (e.g. $current_url, $session_id).
        groups: Optional groups dict passed through to capture().
        template_idx: Optional index into EXCEPTION_TEMPLATES; random if None.
    """
    idx = template_idx if template_idx is not None else random.randint(0, len(EXCEPTION_TEMPLATES) - 1)
    template = EXCEPTION_TEMPLATES[idx]
    posthog_client.capture(
        distinct_id=distinct_id,
        event="$exception",
        properties={
            **session_props,
            **template,
            "$lib": "web",
        },
        timestamp=timestamp,
        groups=groups or {},
    )
