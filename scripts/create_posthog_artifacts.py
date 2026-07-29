import requests
from argparse import ArgumentParser
import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import quote

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

# templates/index.html reads this flag and branches on the "control" and
# "james-test" variants to decide whether to show the co-founder signup modal.
# Without it the modal never appears and the page logs a failed flag evaluation.
james_experiment_flag_data = {
            "name": "Shows the co-founder signup modal on the home page.",
            "key": "james-experiment",
            "tags": ["demo"],
            "filters": {
                "groups": [
                    {
                        "variant": None,
                        "properties": [],
                        "rollout_percentage": 100
                    }
                ],
                "payloads": {},
                "multivariate": {
                    "variants": [
                        {
                            "key": "control",
                            "name": "No modal shown",
                            "rollout_percentage": 50
                        },
                        {
                            "key": "james-test",
                            "name": "Show the co-founder signup modal",
                            "rollout_percentage": 50
                        }
                    ]
                }
            }
        }

def make_posthog_api_request(endpoint, data):
    response = requests.post(url + endpoint, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    print(f"Request failed with status code {response.status_code}")
    print("Response:", response.text)
    try:
        return response.json()
    except Exception:
        return None


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

# Making the POST request

for data in actions_data:
    # Try to find existing action by name
    existing = get_existing_by(actions_endpoint, 'name', data['name'])
    if existing:
        actions_ids[data['name']] = existing['id']
        continue
    response = make_posthog_api_request(actions_endpoint, data)
    if response and 'id' in response:
        actions_ids[data['name']] = response['id']

cohorts_data[1]['filters']['properties']['values'][0]['values'][0]['key'] =  actions_ids.get('Watched a movie')
cohorts_data[2]['filters']['properties']['values'][0]['values'][0]['key'] =  actions_ids.get('Watched a movie')

for data in cohorts_data:
    existing = get_existing_by(cohorts_endpoint, 'name', data['name'])
    if existing:
        cohorts_ids[data['name']] = existing['id']
        continue
    response = make_posthog_api_request(cohorts_endpoint, data)
    if response and 'id' in response:
        cohorts_ids[data['name']] = response['id']

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

feature_flag_data['filters']['groups'][0]['properties'][0]['value'] = cohorts_ids.get('Adult Subscribers')
existing_ff = get_existing_by(feature_flag_endpoint, 'key', feature_flag_data['key'])
if not existing_ff:
    response = make_posthog_api_request(feature_flag_endpoint, feature_flag_data)

existing_james_ff = get_existing_by(feature_flag_endpoint, 'key', james_experiment_flag_data['key'])
if not existing_james_ff:
    response = make_posthog_api_request(feature_flag_endpoint, james_experiment_flag_data)


