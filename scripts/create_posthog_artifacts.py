import requests
import sys
from argparse import ArgumentParser
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import quote

REQUIRED_SCOPES = [
    "action:write",
    "cohort:write",
    "dashboard:write",
    "experiment:write",
    "feature_flag:write",
    "insight:write",
    "query:read",
    "survey:write",
]


def precheck_scopes(api_key):
    """Verify the Personal API key has all required scopes before doing any work.

    Strategy:
    1. Hit GET /api/users/@me/ and look for an explicit scopes list on the user
       or the key. PostHog versions vary in where this surfaces (top-level,
       under `team`, under `organization`, or as a `scoped_*` field), so we
       search broadly.
    2. If no scopes can be discovered that way, fall back to a cheap probe:
       POST /api/projects/<project_id>/cohorts/ with an empty body. A 403 on
       a scope check returns a `detail` like "API key missing required scope
       'cohort:write'.". We parse that and surface the missing scopes.

    On any missing scopes, print a clear, actionable error and exit 1.
    """
    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    base_host = host.replace(".i.posthog.com", ".posthog.com")
    discovered_scopes = None

    # Step 1: try /api/users/@me/
    try:
        me_resp = requests.get(f"{base_host}/api/users/@me/", headers=auth_headers, timeout=15)
        if me_resp.status_code == 401:
            print("ERROR: Personal API key is invalid or expired (HTTP 401 on /api/users/@me/).")
            print("Update at: https://us.posthog.com/settings/user-api-keys")
            sys.exit(1)
        if me_resp.status_code == 200:
            payload = me_resp.json() if me_resp.content else {}
            # Search common locations for a scopes list.
            candidates = []
            if isinstance(payload, dict):
                for key in ("scopes", "scoped_scopes", "key_scopes"):
                    val = payload.get(key)
                    if isinstance(val, list):
                        candidates.extend(val)
                # Some versions nest the key info under `personal_api_key` or similar.
                for nest_key in ("personal_api_key", "api_key", "current_key"):
                    nested = payload.get(nest_key)
                    if isinstance(nested, dict):
                        nv = nested.get("scopes")
                        if isinstance(nv, list):
                            candidates.extend(nv)
            if candidates:
                discovered_scopes = set(candidates)
    except requests.RequestException as e:
        print(f"ERROR: could not reach PostHog at {base_host} during scope precheck: {e}")
        sys.exit(1)

    missing = []

    if discovered_scopes is not None:
        # Wildcard "*" grants everything in PostHog scope conventions.
        if "*" in discovered_scopes:
            missing = []
        else:
            missing = [s for s in REQUIRED_SCOPES if s not in discovered_scopes]
    else:
        # Step 2: fall back to a cheap probe. POST an empty cohort body and
        # parse the 403 detail message for missing-scope hints.
        probe_url = f"{base_host}/api/projects/{project_id}/cohorts/"
        try:
            probe = requests.post(probe_url, headers=auth_headers, json={}, timeout=15)
        except requests.RequestException as e:
            print(f"ERROR: could not reach PostHog at {base_host} during scope precheck: {e}")
            sys.exit(1)

        if probe.status_code == 403:
            try:
                detail = probe.json().get("detail", "") or ""
            except ValueError:
                detail = probe.text or ""
            # Probe only tests cohort:write. If THAT scope is missing, surface it.
            # Otherwise we cannot infer the rest from one probe — assume key is
            # too narrow and warn the user to grant all required scopes.
            if "cohort:write" in detail or "scope" in detail.lower():
                # Could be exactly cohort:write, or could be a generic "missing scope" reply.
                # Be conservative: report all required scopes as unverifiable.
                if "cohort:write" in detail:
                    missing = ["cohort:write"]
                else:
                    missing = list(REQUIRED_SCOPES)
            else:
                # 403 for a non-scope reason (e.g., project access). Treat as fatal.
                print("ERROR: Personal API key is forbidden from accessing this project (HTTP 403).")
                print(f"  detail: {detail}")
                print("Update at: https://us.posthog.com/settings/user-api-keys")
                sys.exit(1)
        elif probe.status_code in (400, 422):
            # Empty body rejected on validation grounds — auth + scope are fine for cohort:write.
            # We still cannot verify the other scopes; warn the user we could not enumerate.
            print(
                "WARNING: could not enumerate Personal API key scopes via /api/users/@me/; "
                "cohort:write probe succeeded but other scopes are unverified. "
                "If a later request 403s, re-check scopes at "
                "https://us.posthog.com/settings/user-api-keys"
            )
            missing = []
        elif probe.status_code in (200, 201):
            # Unexpectedly created something — try to clean up but don't block on it.
            missing = []
            try:
                created = probe.json()
                cid = created.get("id") if isinstance(created, dict) else None
                if cid:
                    requests.delete(f"{probe_url}{cid}/", headers=auth_headers, timeout=15)
            except Exception:
                pass
        else:
            print(
                f"ERROR: unexpected response during scope precheck (HTTP {probe.status_code}). "
                f"Body: {probe.text[:300]}"
            )
            sys.exit(1)

    if missing:
        print("ERROR: Personal API key is missing required scope(s):")
        for s in missing:
            print(f"  - {s}")
        print("Update at: https://us.posthog.com/settings/user-api-keys")
        sys.exit(1)


parser = ArgumentParser()
parser.add_argument("-k", "--personal_api_key",
                    help="PostHog Personal API Key", required=False)
parser.add_argument("-p", "--posthog_api_base_url",
                    help="PostHog API Host", required=False)
parser.add_argument("--project_id", help="PostHog Project Id", required=False)
args = parser.parse_args()

# Load env from project root
project_root_env = Path(__file__).resolve().parents[1] / '.env'
if project_root_env.exists():
    load_dotenv(dotenv_path=project_root_env)

personal_api_key = args.personal_api_key or os.getenv('PH_PERSONAL_API_KEY')
project_id = args.project_id or os.getenv('PH_PROJECT_ID')
host = os.getenv('PH_HOST')
if not personal_api_key:
    raise SystemExit('PH_PERSONAL_API_KEY must be set in env or passed via -k')
if not project_id:
    raise SystemExit('PH_PROJECT_ID must be set in env or passed via --project_id')
if not host:
    raise SystemExit('PH_HOST must be set in env')

# The URL to which you want to send the POST request
url = args.posthog_api_base_url or f"{host.replace('.i.posthog.com','.posthog.com')}/api/projects/{project_id}"

# The Bearer token for authentication
token = personal_api_key

# Headers including the Bearer token for authorization
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# The JSON payload to be sent in the POST request
actions_ids = {}
actions_endpoint = '/actions/'
actions_data = [
        {
            "name": "Subscription Cancelled",
            "tags": ['demo'],
            "steps": [
                {
                    "event": "plan_changed",
                    "properties": [
                        {
                            "key": "new_plan",
                            "type": "event",
                            "value": [
                                "Free"
                            ],
                            "operator": "exact"
                        }
                    ]
                }
            ]
        },
        {
            "name": "Paid Plan Purchase",
            "tags": ['demo'],
            "steps": [
                {
                    "event": "plan_changed",
                    "properties": [
                        {
                            "key": "new_plan",
                            "type": "event",
                            "value": [
                                "Premium",
                                "Max-imal"
                            ],
                            "operator": "exact"
                        }
                    ]
                }
            ]
        },
        {
            "name": "Watched a movie",
            "tags": ['demo'],
            "description": "Watched a movie",
            "steps": [
                {
                    "event": "$pageview",
                    "url": "movie/",
                    "url_matching": "contains"
                }
            ]
        },
        {
            "name": "Select Free Plan",
            "tags": ['demo'],
            "steps": [
                {
                    "event": "$autocapture",
                    "properties": None,
                    "selector": ".container .col-md-4:nth-child(1) > .text-decoration-none"
                }
            ]
        },
        {
            "name": "Select Premium Plan",
            "tags": ['demo'],
            "steps": [
                {
                    "event": "$autocapture",
                    "properties": None,
                    "selector": ".container .col-md-4:nth-child(2) > .text-decoration-none"
                }
            ]
        },
        {
            "name": "Select Maxi-Mal Plan",
            "tags": ['demo'],
            "steps": [
                {
                    "event": "$autocapture",
                    "properties": None,
                    "selector": ".container .col-md-4:nth-child(3) > .text-decoration-none"
                }
            ]
        }
    ]

cohorts_ids = {}
cohorts_endpoint = '/cohorts/'
cohorts_data = [
        {
            "name": "Adult Subscribers",
            "description": "All Subscribers who are adults and thus can watch action movies",
            "filters": {
                "properties": {
                    "type": "OR",
                    "values": [
                        {
                            "type": "OR",
                            "values": [
                                {
                                    "key": "is_adult",
                                    "type": "person",
                                    "value": [
                                        "Yes"
                                    ],
                                    "negation": False,
                                    "operator": "exact"
                                }
                            ]
                        }
                    ]
                }
            }
        },
        {
            "name": "Max-imal users who watched a movie in the last 30 days",
            "description": "",
            "filters": {
                "properties": {
                    "type": "AND",
                    "values": [
                        {
                            "type": "AND",
                            "values": [
                                {
                                    "type": "behavioral",
                                    "value": "performed_event",
                                    "negation": False,
                                    "event_type": "actions",
                                    "explicit_datetime": "-30d"
                                },
                                {
                                    "key": "plan",
                                    "type": "person",
                                    "value": [
                                        "Max-imal"
                                    ],
                                    "negation": False,
                                    "operator": "exact"
                                }
                            ]
                        }
                    ]
                }
            }
        },
        {
            "name": "People who watched 5 movies recently",
            "filters": {
                "properties": {
                    "type": "OR",
                    "values": [
                        {
                            "type": "OR",
                            "values": [
                                {
                                    "type": "behavioral",
                                    "value": "performed_event_multiple",
                                    "negation": False,
                                    "operator": "gte",
                                    "event_type": "actions",
                                    "operator_value": 5,
                                    "explicit_datetime": "-30d"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    ]

insights_endpoint = '/insights/'

movie_views_trend_data = {
    "name":"Movie Views by Plan Type",
     "query": {
  "kind": "InsightVizNode",
  "source": {
    "kind": "TrendsQuery",
    "properties": {
      "type": "AND",
      "values": [
        {
          "type": "AND",
          "values": [
            {
              "key": "plan",
              "type": "person",
              "value": "is_set",
              "operator": "is_set"
            }
          ]
        }
      ]
    },
    "dateRange": {
      "date_to": None,
      "date_from": "-30d"
    },
    "series": [
      {
        "kind": "ActionsNode",
        "math": "total"
      }
    ],
    "interval": "week",
    "breakdownFilter": {
      "breakdowns": [
        {
          "type": "person",
          "property": "plan"
        }
      ]
    },
    "trendsFilter": {
      "display": "ActionsLineGraph"
    }
  },
  "full": True
},
 "saved": True,
 "tags": ["demo"]
}

purchase_funnel_data = {
    "name": "Paid plan purchase funnel",
    "query": {
  "kind": "InsightVizNode",
  "source": {
    "kind": "FunnelsQuery",
    "dateRange": {
      "date_from": "-30d"
    },
    "series": [
      {
        "kind": "EventsNode",
        "event": "$pageview",
        "name": "$pageview",
        "custom_name": "Home Page",
        "properties": [
          {
            "key": "$pathname",
            "type": "event",
            "value": [
              "/"
            ],
            "operator": "exact"
          }
        ]
      },
      {
        "kind": "EventsNode",
        "event": "$pageview",
        "name": "$pageview",
        "custom_name": "Plans Page",
        "properties": [
          {
            "key": "$pathname",
            "type": "event",
            "value": [
              "/plans"
            ],
            "operator": "exact"
          }
        ]
      },
      {
        "kind": "EventsNode",
        "event": "$pageview",
        "name": "$pageview",
        "custom_name": "Signup Page",
        "properties": [
          {
            "key": "$pathname",
            "type": "event",
            "value": [
              "/signup"
            ],
            "operator": "exact"
          }
        ]
      },
      {
        "kind": "ActionsNode",
        "name": "Paid Plan Purchase"
      }
    ],
    "funnelsFilter": {
      "funnelVizType": "steps"
    }
  },
  "full": True
},
"saved": True,
 "tags": ["demo"]
}

movie_retention_data = {
    "name": "Weekly Movie Watch Retention",
    "query":{
  "kind": "InsightVizNode",
  "source": {
    "kind": "RetentionQuery",
    "retentionFilter": {
      "retentionType": "retention_first_time",
      "totalIntervals": 5,
      "returningEntity": {
        "id": 42493,
        "name": "Watched a movie (Test)",
        "type": "actions",
        "order": 0,
        "uuid": "fafa227f-4eed-4dd6-b007-63f748129444"
      },
      "targetEntity": {
        "id": 42493,
        "name": "Watched a movie (Test)",
        "type": "actions",
        "order": 0,
        "uuid": "7a9325b9-85df-44d7-a06e-b62cec8e7bb9"
      },
      "period": "Week"
    }
  },
  "full": True
},
"saved": True,
 "tags": ["demo"]
}

path_data = {
    "name": "Where do people go after visiting the homepage",
    "query": {
  "kind": "InsightVizNode",
  "source": {
    "kind": "PathsQuery",
    "pathsFilter": {
      "includeEventTypes": [
        "$pageview"
      ],
      "pathGroupings": [
        "/movie/*"
      ]
    }
  },
  "full": True
},
"saved": True,
 "tags": ["demo"]
}

feature_flag_endpoint = '/feature_flags/'
feature_flag_data = {
            "name": "Turns Hogflix from family friendly to action movies.",
            "key": "action_mode_on",
            "tags": ["demo"],
            "filters": {
                "groups": [
                    {
                        "variant": None,
                        "properties": [
                            {
                                "key": "id",
                                "type": "cohort",
                            }
                        ],
                        "rollout_percentage": 100
                    }
                ],
                "payloads": {},
                "multivariate": None
            }
        }

class PostHogForbiddenError(Exception):
    """Raised when PostHog returns 403 on an artifact-creation call.

    Carries the endpoint and response body so the caller can hint at the
    likely missing scope.
    """

    def __init__(self, endpoint, status_code, body):
        self.endpoint = endpoint
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code} on {endpoint}: {body[:300]}")


def make_posthog_api_request(endpoint, data):
    response = requests.post(url + endpoint, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    if response.status_code == 403:
        raise PostHogForbiddenError(endpoint, response.status_code, response.text or "")
    print(f"Request failed with status code {response.status_code}")
    print("Response:", response.text)
    try:
        return response.json()
    except Exception:
        return None


# Map of endpoint -> the scope most likely required to write to it.
ENDPOINT_SCOPE_HINTS = {
    '/actions/': 'action:write',
    '/cohorts/': 'cohort:write',
    '/insights/': 'insight:write',
    '/feature_flags/': 'feature_flag:write',
    '/dashboards/': 'dashboard:write',
    '/experiments/': 'experiment:write',
    '/surveys/': 'survey:write',
}


def report_403_and_reraise(err, action_label):
    """Print a clear scope hint for a 403 and re-raise the original exception."""
    hint = ENDPOINT_SCOPE_HINTS.get(err.endpoint, 'unknown')
    print(f"ERROR: HTTP 403 while {action_label} (endpoint {err.endpoint}).")
    print(f"  scope '{hint}' is likely missing from the Personal API key.")
    print("  Update at: https://us.posthog.com/settings/user-api-keys")
    raise err


def get_existing_by(endpoint, match_key, match_value):
    try:
        resp = requests.get(url + endpoint + f"?search={quote(str(match_value))}", headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get('results', data if isinstance(data, list) else [])
        for item in items:
            if item.get(match_key) == match_value:
                return item
    except Exception:
        return None
    return None

# Verify the Personal API key has all required scopes BEFORE any artifact work.
precheck_scopes(personal_api_key)

# Making the POST request

# --- actions ---
try:
    for data in actions_data:
        # Try to find existing action by name
        existing = get_existing_by(actions_endpoint, 'name', data['name'])
        if existing:
            actions_ids[data['name']] = existing['id']
            continue
        response = make_posthog_api_request(actions_endpoint, data)
        if response and 'id' in response:
            actions_ids[data['name']] = response['id']
except PostHogForbiddenError as e:
    report_403_and_reraise(e, "creating actions")

cohorts_data[1]['filters']['properties']['values'][0]['values'][0]['key'] =  actions_ids.get('Watched a movie')
cohorts_data[2]['filters']['properties']['values'][0]['values'][0]['key'] =  actions_ids.get('Watched a movie')

# --- cohorts ---
try:
    for data in cohorts_data:
        existing = get_existing_by(cohorts_endpoint, 'name', data['name'])
        if existing:
            cohorts_ids[data['name']] = existing['id']
            continue
        response = make_posthog_api_request(cohorts_endpoint, data)
        if response and 'id' in response:
            cohorts_ids[data['name']] = response['id']
except PostHogForbiddenError as e:
    report_403_and_reraise(e, "creating cohorts")

# --- insights ---
try:
    movie_views_trend_data['query']['source']['series'][0]['id'] = actions_ids.get('Watched a movie')
    existing_mv = get_existing_by(insights_endpoint, 'name', movie_views_trend_data['name'])
    if not existing_mv:
        response = make_posthog_api_request(insights_endpoint, movie_views_trend_data)

    purchase_funnel_data['query']['source']['series'][3]['id'] = actions_ids.get('Paid Plan Purchase')
    existing_pf = get_existing_by(insights_endpoint, 'name', purchase_funnel_data['name'])
    if not existing_pf:
        response = make_posthog_api_request(insights_endpoint, purchase_funnel_data)

    movie_retention_data['query']['source']['retentionFilter']['targetEntity']['id'] = actions_ids.get('Watched a movie')
    movie_retention_data['query']['source']['retentionFilter']['returningEntity']['id'] = actions_ids.get('Watched a movie')

    existing_ret = get_existing_by(insights_endpoint, 'name', movie_retention_data['name'])
    if not existing_ret:
        response = make_posthog_api_request(insights_endpoint, movie_retention_data)

    existing_path = get_existing_by(insights_endpoint, 'name', path_data['name'])
    if not existing_path:
        response = make_posthog_api_request(insights_endpoint, path_data)
except PostHogForbiddenError as e:
    report_403_and_reraise(e, "creating insights")

# --- feature flag ---
try:
    feature_flag_data['filters']['groups'][0]['properties'][0]['value'] = cohorts_ids.get('Adult Subscribers')
    existing_ff = get_existing_by(feature_flag_endpoint, 'key', feature_flag_data['key'])
    if not existing_ff:
        response = make_posthog_api_request(feature_flag_endpoint, feature_flag_data)
except PostHogForbiddenError as e:
    report_403_and_reraise(e, "creating feature flag")


# =============================================================================
# Phase 8: extended artifacts (surveys, more flags, experiment, cohorts,
# insights, dashboards). Each helper is idempotent: it checks for an existing
# artifact with the same name (or key, for flags) before creating.
# Errors are caught locally so a single failure does not abort the whole run.
# =============================================================================


def _list_all(endpoint, params=None):
    """Return all items at a list endpoint (best-effort, single page).

    Used as a more reliable idempotency helper for endpoints where the
    `?search=` parameter is unsupported or unreliable (surveys, experiments,
    dashboards). Reads up to 100 items, which is plenty for a demo project.
    """
    try:
        query = params or {"limit": 100}
        resp = requests.get(url + endpoint, headers=headers, params=query, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("results", [])
    except Exception:
        return []


def _find_by_name(endpoint, name):
    """Idempotency helper: find an artifact by exact name match.

    Tries the existing search-based helper first, then falls back to listing
    all items. Returns the matching item dict or None.
    """
    hit = get_existing_by(endpoint, 'name', name)
    if hit:
        return hit
    for item in _list_all(endpoint):
        if isinstance(item, dict) and item.get('name') == name:
            return item
    return None


def _find_flag_by_key(key):
    """Idempotency helper for feature flags (matched by `key`, not `name`)."""
    hit = get_existing_by(feature_flag_endpoint, 'key', key)
    if hit:
        return hit
    for item in _list_all(feature_flag_endpoint):
        if isinstance(item, dict) and item.get('key') == key:
            return item
    return None


def create_surveys():
    """Create demo surveys.

    1. 'Post-purchase NPS' — popover rating survey, no end_date (running
       indefinitely on purpose; this surfaces issue E7 — surveys that have
       outlived their usefulness because nobody set an end date).
    2. 'Why did you cancel?' — open-text question, end_date 30 days from now.
    """
    surveys_endpoint = '/surveys/'
    surveys = [
        {
            "name": "Post-purchase NPS",
            "description": "How likely are you to recommend Hogflix?",
            "type": "popover",
            "questions": [
                {
                    "type": "rating",
                    "scale": 10,
                    "display": "number",
                    "question": "How likely are you to recommend Hogflix to a friend?",
                    "lowerBoundLabel": "Not likely",
                    "upperBoundLabel": "Very likely",
                }
            ],
            "conditions": {
                "events": {
                    "values": [{"name": "subscription_purchased"}]
                }
            },
            # No end_date intentionally — issue E7.
            "start_date": datetime.now(timezone.utc).isoformat(),
        },
        {
            "name": "Why did you cancel?",
            "description": "Cancellation feedback",
            "type": "popover",
            "questions": [
                {
                    "type": "open",
                    "question": "We're sorry to see you go. What made you cancel?",
                }
            ],
            "conditions": {
                "events": {
                    "values": [{"name": "subscription_cancelled"}]
                }
            },
            "start_date": datetime.now(timezone.utc).isoformat(),
            "end_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    ]
    for survey in surveys:
        try:
            existing = _find_by_name(surveys_endpoint, survey['name'])
            if existing:
                print(f"  [skip] survey already exists: {survey['name']}")
                continue
            resp = make_posthog_api_request(surveys_endpoint, survey)
            if resp and 'id' in resp:
                print(f"  [ok] created survey: {survey['name']}")
            else:
                print(f"  [warn] survey create returned no id: {survey['name']}")
        except PostHogForbiddenError as e:
            print(f"  [error] 403 creating survey '{survey['name']}': {e.body[:200]}")
            print("  Hint: scope 'survey:write' may be missing.")
        except Exception as e:
            print(f"  [error] failed creating survey '{survey['name']}': {e}")


def create_more_feature_flags():
    """Create additional feature flags. Several are intentionally messy.

    - action_mode_on: 50% rollout (real flag, may already exist from
      earlier creation — skipped if so).
    - payment_flow_v2: 100% rollout, stale (issue E3).
    - premium_trial_banner: 0% rollout, never enabled (issue E4).
    - churn_risk_targeting: property targeting on plan='Free' for 60+ days.
    """
    flags = [
        {
            "name": "Action mode on",
            "key": "action_mode_on",
            "tags": ["demo"],
            "filters": {
                "groups": [
                    {"properties": [], "rollout_percentage": 50}
                ],
                "payloads": {},
                "multivariate": None,
            },
        },
        {
            "name": "Payment flow v2 (stale)",
            "key": "payment_flow_v2",
            "tags": ["demo", "stale"],
            "filters": {
                "groups": [
                    {"properties": [], "rollout_percentage": 100}
                ],
                "payloads": {},
                "multivariate": None,
            },
        },
        {
            "name": "Premium trial banner (never enabled)",
            "key": "premium_trial_banner",
            "tags": ["demo", "unused"],
            "filters": {
                "groups": [
                    {"properties": [], "rollout_percentage": 0}
                ],
                "payloads": {},
                "multivariate": None,
            },
        },
        {
            "name": "Churn risk targeting",
            "key": "churn_risk_targeting",
            "tags": ["demo"],
            "filters": {
                "groups": [
                    {
                        "properties": [
                            {
                                "key": "plan",
                                "type": "person",
                                "value": ["Free"],
                                "operator": "exact",
                            },
                            {
                                "key": "signup_date",
                                "type": "person",
                                "value": "-60d",
                                "operator": "is_date_before",
                            },
                        ],
                        "rollout_percentage": 100,
                    }
                ],
                "payloads": {},
                "multivariate": None,
            },
        },
    ]
    for flag in flags:
        try:
            existing = _find_flag_by_key(flag['key'])
            if existing:
                print(f"  [skip] feature flag already exists: {flag['key']}")
                continue
            resp = make_posthog_api_request(feature_flag_endpoint, flag)
            if resp and 'id' in resp:
                print(f"  [ok] created feature flag: {flag['key']}")
            else:
                print(f"  [warn] feature flag create returned no id: {flag['key']}")
        except PostHogForbiddenError as e:
            print(f"  [error] 403 creating feature flag '{flag['key']}': {e.body[:200]}")
            print("  Hint: scope 'feature_flag:write' may be missing.")
        except Exception as e:
            print(f"  [error] failed creating feature flag '{flag['key']}': {e}")


def create_experiment():
    """Create one completed experiment: 'Free trial length: 7 days vs 14 days'.

    Backed by a multivariate feature flag with control/test variants.
    Marked completed via end_date in the past.
    """
    experiments_endpoint = '/experiments/'
    exp_name = "Free trial length: 7 days vs 14 days"
    flag_key = "free_trial_length"

    try:
        existing = _find_by_name(experiments_endpoint, exp_name)
        if existing:
            print(f"  [skip] experiment already exists: {exp_name}")
            return

        # PostHog creates the backing feature flag automatically when an
        # experiment is created with `feature_flag_key`. If a flag with that
        # key already exists (from a prior partial run), reuse it; otherwise
        # let the experiment endpoint create it.
        existing_flag = _find_flag_by_key(flag_key)

        # Mark as completed: start in the past, end yesterday.
        start = datetime.now(timezone.utc) - timedelta(days=30)
        end = datetime.now(timezone.utc) - timedelta(days=1)

        payload = {
            "name": exp_name,
            "description": "Does giving a 14-day free trial improve conversion vs 7 days?",
            "feature_flag_key": flag_key,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "parameters": {
                "feature_flag_variants": [
                    {"key": "control", "name": "7 days", "rollout_percentage": 50},
                    {"key": "test", "name": "14 days", "rollout_percentage": 50},
                ],
                "recommended_sample_size": 1000,
                "minimum_detectable_effect": 5,
            },
            "filters": {
                "events": [
                    {"id": "subscription_purchased", "name": "subscription_purchased",
                     "type": "events", "order": 0}
                ],
                "insight": "FUNNELS",
            },
        }
        if existing_flag:
            # Avoid duplicate-flag-key 400 by passing the existing flag id.
            payload["feature_flag"] = existing_flag.get("id")

        resp = make_posthog_api_request(experiments_endpoint, payload)
        if resp and 'id' in resp:
            print(f"  [ok] created experiment: {exp_name}")
        else:
            print(f"  [warn] experiment create returned no id: {exp_name}")
    except PostHogForbiddenError as e:
        print(f"  [error] 403 creating experiment '{exp_name}': {e.body[:200]}")
        print("  Hint: scope 'experiment:write' may be missing.")
    except Exception as e:
        print(f"  [error] failed creating experiment '{exp_name}': {e}")


def create_more_cohorts():
    """Create additional cohorts.

    - 'Power users': performed any movie_*_complete event 5+ times in 30 days.
      Uses the existing 'Watched a movie' action as a proxy (which matches
      pageviews to /movie/, the seed-data signal for movie completion).
    - 'Trial bouncers': signed up but no plan_changed within 7 days.
    - 'High-value subscribers': subscription_purchased with plan='Max-imal'.
    - 'Defined but unused': Hogflix internal IPs (issue E5: never referenced
      in any insight).
    """
    watched_a_movie_id = actions_ids.get('Watched a movie')

    cohorts = [
        {
            "name": "Power users",
            "description": "Watched 5+ movies in the last 30 days.",
            "filters": {
                "properties": {
                    "type": "AND",
                    "values": [
                        {
                            "type": "AND",
                            "values": [
                                {
                                    "type": "behavioral",
                                    "value": "performed_event_multiple",
                                    "key": watched_a_movie_id,
                                    "negation": False,
                                    "operator": "gte",
                                    "event_type": "actions",
                                    "operator_value": 5,
                                    "explicit_datetime": "-30d",
                                }
                            ],
                        }
                    ],
                }
            },
        },
        {
            "name": "Trial bouncers",
            "description": "Hit /signup but never fired plan_changed within 7 days.",
            "filters": {
                "properties": {
                    "type": "AND",
                    "values": [
                        {
                            "type": "AND",
                            "values": [
                                {
                                    "type": "behavioral",
                                    "value": "performed_event",
                                    "key": "$pageview",
                                    "negation": False,
                                    "event_type": "events",
                                    "explicit_datetime": "-30d",
                                    "event_filters": [
                                        {
                                            "key": "$pathname",
                                            "type": "event",
                                            "value": ["/signup"],
                                            "operator": "exact",
                                        }
                                    ],
                                },
                                {
                                    "type": "behavioral",
                                    "value": "performed_event",
                                    "key": "plan_changed",
                                    "negation": True,
                                    "event_type": "events",
                                    "explicit_datetime": "-7d",
                                },
                            ],
                        }
                    ],
                }
            },
        },
        {
            "name": "High-value subscribers",
            "description": "Bought a Max-imal subscription.",
            "filters": {
                "properties": {
                    "type": "AND",
                    "values": [
                        {
                            "type": "AND",
                            "values": [
                                {
                                    "type": "behavioral",
                                    "value": "performed_event",
                                    "key": "subscription_purchased",
                                    "negation": False,
                                    "event_type": "events",
                                    "explicit_datetime": "-90d",
                                    "event_filters": [
                                        {
                                            "key": "plan",
                                            "type": "event",
                                            "value": ["Max-imal"],
                                            "operator": "exact",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            },
        },
        {
            "name": "Defined but unused",
            "description": "Hogflix internal IPs. Never referenced in any insight (issue E5).",
            "filters": {
                "properties": {
                    "type": "OR",
                    "values": [
                        {
                            "type": "OR",
                            "values": [
                                {
                                    "key": "$ip",
                                    "type": "person",
                                    "value": ["10.0.0.0/8", "192.168.0.0/16"],
                                    "operator": "exact",
                                }
                            ],
                        }
                    ],
                }
            },
        },
    ]
    for cohort in cohorts:
        try:
            existing = _find_by_name(cohorts_endpoint, cohort['name'])
            if existing:
                print(f"  [skip] cohort already exists: {cohort['name']}")
                cohorts_ids[cohort['name']] = existing['id']
                continue
            resp = make_posthog_api_request(cohorts_endpoint, cohort)
            if resp and 'id' in resp:
                cohorts_ids[cohort['name']] = resp['id']
                print(f"  [ok] created cohort: {cohort['name']}")
            else:
                print(f"  [warn] cohort create returned no id: {cohort['name']}")
        except PostHogForbiddenError as e:
            print(f"  [error] 403 creating cohort '{cohort['name']}': {e.body[:200]}")
            print("  Hint: scope 'cohort:write' may be missing.")
        except Exception as e:
            print(f"  [error] failed creating cohort '{cohort['name']}': {e}")


# Module-level cache so create_dashboards() can reference insights created
# by create_more_insights() by name->id.
extra_insights_ids = {}


def create_more_insights():
    """Create additional insights.

    Returns a dict mapping insight name -> id for the dashboards step.
    Includes one intentionally broken insight (action id 999999, issue E6)
    and one SQL insight that uses the wrong field name (issue C1).
    """
    insights = [
        # 1. Trend: subscription_purchased per day
        {
            "name": "Subscriptions purchased per day",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "TrendsQuery",
                    "dateRange": {"date_from": "-30d"},
                    "series": [
                        {"kind": "EventsNode", "event": "subscription_purchased",
                         "name": "subscription_purchased", "math": "total"}
                    ],
                    "interval": "day",
                    "trendsFilter": {"display": "ActionsLineGraph"},
                },
                "full": True,
            },
        },
        # 2. Trend: movie_buy_complete per day
        {
            "name": "Movie purchases per day",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "TrendsQuery",
                    "dateRange": {"date_from": "-30d"},
                    "series": [
                        {"kind": "EventsNode", "event": "movie_buy_complete",
                         "name": "movie_buy_complete", "math": "total"}
                    ],
                    "interval": "day",
                    "trendsFilter": {"display": "ActionsLineGraph"},
                },
                "full": True,
            },
        },
        # 3. Funnel: subscription_intent -> subscription_purchased
        {
            "name": "Subscription intent to purchase funnel",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "FunnelsQuery",
                    "dateRange": {"date_from": "-30d"},
                    "series": [
                        {"kind": "EventsNode", "event": "subscription_intent",
                         "name": "subscription_intent"},
                        {"kind": "EventsNode", "event": "subscription_purchased",
                         "name": "subscription_purchased"},
                    ],
                    "funnelsFilter": {"funnelVizType": "steps"},
                },
                "full": True,
            },
        },
        # 4. Funnel: signup pageview -> subscription_purchased
        {
            "name": "Signup to subscription funnel",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "FunnelsQuery",
                    "dateRange": {"date_from": "-30d"},
                    "series": [
                        {
                            "kind": "EventsNode", "event": "$pageview",
                            "name": "$pageview", "custom_name": "Signup",
                            "properties": [
                                {"key": "$pathname", "type": "event",
                                 "value": ["/signup"], "operator": "exact"}
                            ],
                        },
                        {"kind": "EventsNode", "event": "subscription_purchased",
                         "name": "subscription_purchased"},
                    ],
                    "funnelsFilter": {"funnelVizType": "steps"},
                },
                "full": True,
            },
        },
        # 5. Retention: weekly retention by subscription_purchased
        {
            "name": "Weekly subscription retention",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "RetentionQuery",
                    "retentionFilter": {
                        "retentionType": "retention_first_time",
                        "totalIntervals": 8,
                        "period": "Week",
                        "targetEntity": {
                            "id": "subscription_purchased",
                            "name": "subscription_purchased",
                            "type": "events",
                            "order": 0,
                        },
                        "returningEntity": {
                            "id": "subscription_purchased",
                            "name": "subscription_purchased",
                            "type": "events",
                            "order": 0,
                        },
                    },
                },
                "full": True,
            },
        },
        # 6. Lifecycle: user_logged_in (returning vs dormant)
        {
            "name": "Login lifecycle",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "LifecycleQuery",
                    "dateRange": {"date_from": "-30d"},
                    "interval": "week",
                    "series": [
                        {"kind": "EventsNode", "event": "user_logged_in",
                         "name": "user_logged_in", "math": "total"}
                    ],
                },
                "full": True,
            },
        },
        # 7. Stickiness: movie_*_complete by week. PostHog stickiness queries
        # operate on a single event per series, so we use the broader
        # 'Watched a movie' action when available (action id) to capture the
        # family of movie events.
        {
            "name": "Movie watch stickiness",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "StickinessQuery",
                    "dateRange": {"date_from": "-30d"},
                    "interval": "week",
                    "series": [
                        {"kind": "ActionsNode",
                         "id": actions_ids.get('Watched a movie'),
                         "name": "Watched a movie", "math": "total"}
                    ],
                    "stickinessFilter": {},
                },
                "full": True,
            },
        },
        # 8. SQL: top movies by view count.
        {
            "name": "Top movies by view count",
            "saved": True,
            "tags": ["demo"],
            "query": {
                "kind": "DataTableNode",
                "source": {
                    "kind": "HogQLQuery",
                    "query": (
                        "SELECT properties.$pathname AS movie, count() AS views\n"
                        "FROM events\n"
                        "WHERE event = '$pageview'\n"
                        "  AND properties.$pathname LIKE '/movie/%'\n"
                        "  AND timestamp > now() - INTERVAL 30 DAY\n"
                        "GROUP BY movie\n"
                        "ORDER BY views DESC\n"
                        "LIMIT 25"
                    ),
                },
                "full": True,
            },
        },
        # 9. SQL: revenue by plan tier — INTENTIONALLY uses `value` instead of
        # `price`. The seed data writes `price` in cents; querying `value`
        # silently returns zero/NULL across the board. Demonstrates issue C1
        # (silent metric drift via wrong field name).
        {
            "name": "Revenue by plan tier (broken: wrong field)",
            "saved": True,
            "tags": ["demo", "broken"],
            "query": {
                "kind": "DataTableNode",
                "source": {
                    "kind": "HogQLQuery",
                    "query": (
                        "SELECT properties.plan AS plan,\n"
                        "       sum(toFloat(properties.value)) / 100 AS revenue_usd\n"
                        "FROM events\n"
                        "WHERE event = 'subscription_purchased'\n"
                        "  AND timestamp > now() - INTERVAL 30 DAY\n"
                        "GROUP BY plan\n"
                        "ORDER BY revenue_usd DESC"
                    ),
                },
                "full": True,
            },
        },
        # 10. Trend referencing a fake action id (issue E6: broken reference).
        {
            "name": "Trend with broken action reference",
            "saved": True,
            "tags": ["demo", "broken"],
            "query": {
                "kind": "InsightVizNode",
                "source": {
                    "kind": "TrendsQuery",
                    "dateRange": {"date_from": "-30d"},
                    "series": [
                        {"kind": "ActionsNode", "id": 999999,
                         "name": "Nonexistent action", "math": "total"}
                    ],
                    "interval": "day",
                    "trendsFilter": {"display": "ActionsLineGraph"},
                },
                "full": True,
            },
        },
    ]
    for insight in insights:
        try:
            existing = _find_by_name(insights_endpoint, insight['name'])
            if existing:
                extra_insights_ids[insight['name']] = existing['id']
                print(f"  [skip] insight already exists: {insight['name']}")
                continue
            resp = make_posthog_api_request(insights_endpoint, insight)
            if resp and 'id' in resp:
                extra_insights_ids[insight['name']] = resp['id']
                print(f"  [ok] created insight: {insight['name']}")
            else:
                print(f"  [warn] insight create returned no id: {insight['name']}")
        except PostHogForbiddenError as e:
            print(f"  [error] 403 creating insight '{insight['name']}': {e.body[:200]}")
            print("  Hint: scope 'insight:write' may be missing.")
        except Exception as e:
            print(f"  [error] failed creating insight '{insight['name']}': {e}")


def create_dashboards():
    """Create demo dashboards and attach insight tiles.

    Customer health (insights 1-7): subs/day, movie buys/day, intent funnel,
    signup funnel, weekly retention, login lifecycle, movie stickiness.
    Revenue (insights 8-9): top movies SQL + broken revenue SQL.
    """
    dashboards_endpoint = '/dashboards/'
    tiles_endpoint = '/dashboard_tiles/'

    customer_health_names = [
        "Subscriptions purchased per day",
        "Movie purchases per day",
        "Subscription intent to purchase funnel",
        "Signup to subscription funnel",
        "Weekly subscription retention",
        "Login lifecycle",
        "Movie watch stickiness",
    ]
    revenue_names = [
        "Top movies by view count",
        "Revenue by plan tier (broken: wrong field)",
    ]

    plan = [
        ("Customer health", "Onboarding & retention demo dashboard.", customer_health_names),
        ("Revenue", "Revenue tracking demo dashboard. Includes one broken SQL insight (issue C1).", revenue_names),
    ]

    for dash_name, dash_desc, insight_names in plan:
        try:
            existing = _find_by_name(dashboards_endpoint, dash_name)
            if existing:
                dashboard_id = existing['id']
                print(f"  [skip] dashboard already exists: {dash_name} (id={dashboard_id})")
            else:
                resp = make_posthog_api_request(dashboards_endpoint, {
                    "name": dash_name,
                    "description": dash_desc,
                    "tags": ["demo"],
                })
                if not (resp and 'id' in resp):
                    print(f"  [warn] dashboard create returned no id: {dash_name}")
                    continue
                dashboard_id = resp['id']
                print(f"  [ok] created dashboard: {dash_name} (id={dashboard_id})")

            # Attach insights as tiles. Skip insights that aren't in the
            # cache (e.g. failed earlier).
            for iname in insight_names:
                insight_id = extra_insights_ids.get(iname)
                if not insight_id:
                    print(f"    [skip-tile] missing insight '{iname}'")
                    continue
                # Two paths exist for adding tiles: PATCH the dashboard with
                # tile_layouts, or POST to /dashboard_tiles/. The tiles
                # endpoint is simpler and idempotent on (dashboard, insight).
                tile_payload = {
                    "dashboard": dashboard_id,
                    "insight": insight_id,
                }
                try:
                    resp = requests.post(url + tiles_endpoint, headers=headers,
                                         json=tile_payload, timeout=30)
                    if resp.status_code in (200, 201):
                        print(f"    [ok] tiled '{iname}' on '{dash_name}'")
                    elif resp.status_code == 404:
                        # Older PostHog versions don't expose dashboard_tiles
                        # directly; fall back to PATCHing the insight to
                        # include this dashboard.
                        patch_url = f"{url}{insights_endpoint}{insight_id}/"
                        patch_resp = requests.patch(
                            patch_url, headers=headers,
                            json={"dashboards": [dashboard_id]}, timeout=30
                        )
                        if patch_resp.status_code in (200, 201):
                            print(f"    [ok] tiled '{iname}' on '{dash_name}' (via insight patch)")
                        else:
                            print(f"    [warn] could not tile '{iname}': "
                                  f"tiles={resp.status_code} patch={patch_resp.status_code}")
                    else:
                        print(f"    [warn] tile create returned {resp.status_code}: "
                              f"{(resp.text or '')[:200]}")
                except Exception as e:
                    print(f"    [error] tiling '{iname}' on '{dash_name}': {e}")
        except PostHogForbiddenError as e:
            print(f"  [error] 403 creating dashboard '{dash_name}': {e.body[:200]}")
            print("  Hint: scope 'dashboard:write' may be missing.")
        except Exception as e:
            print(f"  [error] failed creating dashboard '{dash_name}': {e}")


# --- run extended creation steps in order. Each is wrapped so a single
# failure does not abort the whole run. ---
print("\n--- creating surveys ---")
try:
    create_surveys()
except Exception as e:
    print(f"  [error] create_surveys() top-level failure: {e}")

print("\n--- creating additional feature flags ---")
try:
    create_more_feature_flags()
except Exception as e:
    print(f"  [error] create_more_feature_flags() top-level failure: {e}")

print("\n--- creating experiment ---")
try:
    create_experiment()
except Exception as e:
    print(f"  [error] create_experiment() top-level failure: {e}")

print("\n--- creating additional cohorts ---")
try:
    create_more_cohorts()
except Exception as e:
    print(f"  [error] create_more_cohorts() top-level failure: {e}")

print("\n--- creating additional insights ---")
try:
    create_more_insights()
except Exception as e:
    print(f"  [error] create_more_insights() top-level failure: {e}")

print("\n--- creating dashboards ---")
try:
    create_dashboards()
except Exception as e:
    print(f"  [error] create_dashboards() top-level failure: {e}")

print("\n--- done ---")
