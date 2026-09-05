from posthog import Posthog
from datetime import datetime,timedelta
from faker import Faker
from argparse import ArgumentParser
import random
import csv
import sys
from argparse import ArgumentParser
from pathlib import Path
import os
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.seed_helpers.browser_context import make_session_properties
from scripts.seed_helpers.growth import (
    daily_user_count,
    behavioral_profile,
    events_per_session,
    is_user_active_on_day,
)
from scripts.seed_helpers.autocapture import (
    synthesize_autocapture,
    synthesize_rageclick,
    synthesize_dead_click,
)
from scripts.seed_helpers.exceptions import synthesize_exception
from scripts.seed_helpers.cost_amplifiers import (
    spam_pageleave,
    spam_groupidentify,
    flag_eval_flood,
    identify_spam,
    double_fire_purchase,
    anonymous_profile_creation,
)
from scripts.seed_helpers.identity_issues import (
    maybe_identify_user,
    unstable_distinct_ids,
    flag_flip_pattern,
)
from scripts.seed_helpers.data_quality import (
    apply_event_typo,
    apply_property_typo,
    maybe_jsonify_property,
    date_format_drift,
    plan_name_drift,
)

# The PostHog Python SDK injects host-machine $os/$os_version into every event,
# overriding caller-supplied values. Strip those keys from the SDK's system
# context so the per-session device profile wins. ($python_runtime/$python_version
# stay; they're harmless metadata.)
import posthog.client as _ph_client
_original_system_context = _ph_client.system_context
def _system_context_without_os():
    ctx = dict(_original_system_context())
    ctx.pop("$os", None)
    ctx.pop("$os_version", None)
    return ctx
_ph_client.system_context = _system_context_without_os


def _hash_seed(value):
    """Stable positive 31-bit int seed from any value."""
    return abs(hash(str(value))) & 0x7FFFFFFF

days_to_generate = 30
number_of_iterations = 100

parser = ArgumentParser()
parser.add_argument("-d", "--number_of_days",
                    help="Number of days before today to generate data from",default=30, required=False)
parser.add_argument("-i", "--number_of_iterations",
                    help="Number of iterations of the data generator",default=100, required=False)
parser.add_argument("-k", "--posthog_api_key",
                    help="PostHog Project API Key", required=False)
parser.add_argument("-p", "--posthog_host",
                    help="PostHog Host", required=False)
args = parser.parse_args()

# Load .env from project root to support Codespaces/devcontainer auto-creation
project_root_env = Path(__file__).resolve().parents[1] / '.env'
if project_root_env.exists():
  load_dotenv(dotenv_path=project_root_env)

# Fallback to environment variables if CLI params not provided
if not args.posthog_api_key:
  args.posthog_api_key = os.getenv("PH_PROJECT_KEY")
if not args.posthog_host:
  args.posthog_host = os.getenv("PH_HOST")
if not args.posthog_api_key or not args.posthog_host:
  raise SystemExit("PH_PROJECT_KEY and PH_HOST must be provided via flags or environment variables.")

# PostHog Python Client
posthog = Posthog(args.posthog_api_key, 
  host=args.posthog_host,
  debug=True,
  historical_migration=True,
  disable_geoip=False
)

fake = Faker() 

csv_path = Path(__file__).resolve().parent / '500_names_and_emails.csv'
with open(csv_path, newline='') as csvfile:
    csvreader = csv.DictReader(csvfile, delimiter=',')
    fake_users = [row for row in csvreader]

device_properties = [
    {
       "$os": "Mac OS X",
      "$browser": "Chrome",
      "$device_type": "Desktop"
    },
    {
       "$os": "Mac OS X",
      "$browser": "Firefox",
      "$device_type": "Desktop"
    },
    {
       "$os": "Mac OS X",
      "$browser": "Safari",
      "$device_type": "Desktop"
    },{
       "$os": "Windows",
      "$browser": "Chrome",
      "$device_type": "Desktop"
    },
    {
       "$os": "Windows",
      "$browser": "Edge",
      "$device_type": "Desktop"
    },
    {
       "$os": "Windows",
      "$browser": "Firefox",
      "$device_type": "Desktop"
    },
    {
       "$os": "iOS",
      "$browser": "Mobile Safari",
      "$device_type": "Mobile"
    },
    {
       "$os": "Android",
      "$browser": "Android Mobile",
      "$device_type": "Mobile"
    }]

plans = ['Free', 'Premium', 'Max-imal']

# Simple catalog mirror of pop_db.py entries for titles
movies_catalog = {
  1: {"title": "Code & Quills"},
  2: {"title": "Palette of Prickles"},
  3: {"title": "Data Spikes"},
  4: {"title": "Fists of Fury"},
  5: {"title": "Spikes & Consequences"},
  6: {"title": "The Hedge Abides"}
}

def get_random_time(day_offset=None):
    """Random timestamp. If day_offset is set, return a time within that day
    (days_ago=day_offset). Otherwise scatter across the whole window."""
    if day_offset is not None:
        return datetime.now() - timedelta(days=day_offset, seconds=random.randint(0, 86400))
    random_seconds = random.randint(0, int(args.number_of_days) * 86400)
    return datetime.now() - timedelta(seconds=random_seconds)


def _user_id_int(email):
    """Stable positive int per email for behavioral_profile()."""
    return abs(hash(email)) & 0x7FFFFFFF


def sprinkle_clicks_on_page(distinct_id, page, base_timestamp, client_properties, groups=None, family_id=None, family_name=None):
    """Emit a few $autocapture clicks (and rare $rageclick / $dead_click) for the
    page the user just landed on, plus the cost-amplifier patterns: $pageleave
    spam (3x), $groupidentify spam (re-fires each pageview)."""
    n_clicks = random.randint(1, 4)
    for i in range(n_clicks):
        synthesize_autocapture(
            posthog,
            distinct_id=distinct_id,
            page=page,
            timestamp=base_timestamp + timedelta(seconds=5 + i * 7),
            session_props=client_properties,
            groups=groups or {},
        )
    if random.random() < 0.01:
        synthesize_rageclick(
            posthog, distinct_id=distinct_id, page=page,
            timestamp=base_timestamp + timedelta(seconds=20),
            session_props=client_properties, groups=groups or {},
        )
    if random.random() < 0.005:
        synthesize_dead_click(
            posthog, distinct_id=distinct_id, page=page,
            timestamp=base_timestamp + timedelta(seconds=25),
            session_props=client_properties, groups=groups or {},
        )
    # A6/A2 cost amplifiers: $pageleave fires 3x per pageview; $groupidentify
    # re-fires after every pageview when the user is in a family group.
    spam_pageleave(posthog, distinct_id, page, base_timestamp + timedelta(seconds=2),
                   client_properties, count=3, groups=groups or {})
    if family_id is not None:
        spam_groupidentify(posthog, distinct_id, 'family', family_id,
                           {'name': family_name or ''},
                           base_timestamp + timedelta(seconds=1))


def maybe_emit_exception(distinct_id, base_timestamp, client_properties, groups=None, probability=0.03):
    """~3% of sessions emit an $exception event."""
    if random.random() < probability:
        synthesize_exception(
            posthog,
            distinct_id=distinct_id,
            timestamp=base_timestamp + timedelta(seconds=random.randint(10, 60)),
            session_props=client_properties,
            groups=groups or {},
        )

def capture_pageview(url, timestamp, client_properties, distinct_id, groups = {}):
   properties = {
      "$current_url": url,
      "$host": 'hogflix.net',
      "$pathname": url.replace('https://hogflix.net', ''),
      **client_properties
   }
   capture_event('$pageview',properties,timestamp, distinct_id, groups)
   
   
# Convert and capture Amplitude data
def capture_event(event, extra_properties, timestamp, distinct_id, groups = {}):
  uid = _hash_seed(distinct_id)
  # C4 data quality: event-name typo for ~1.5% of mapped events.
  event = apply_event_typo(event, uid)

  merged_props = {
    "timestamp": timestamp,
    **extra_properties,
  }

  # C5 data quality: occasionally rename user_id -> userId/userID/userid.
  merged_props = apply_property_typo(merged_props, uid)

  posthog.capture(
    event=event,
    distinct_id=distinct_id,
    properties=merged_props,
    timestamp=timestamp,
    groups=groups,
  )

def get_client_properties(user = None):
   session_id = fake.uuid4()
   session_props = make_session_properties(_hash_seed(session_id))
   if (user is not None):
      properties= {
         **session_props,
         "$ip": user['ip'],
         "$session_id": session_id,
         "$active_feature_flags": ["action_mode_on"],
         "$feature/action_mode_on": True if user['is_adult'] == 'Yes' else False,
         "user_id": user['email'],  # C5 source for property-name typo
         "family_id": user['family_id'],
         "$set": {
            "email": user['email'],
            "is_adult": user['is_adult'],
            "plan": user['plan']
         }
      }
   else:
      properties= {
         **session_props,
         "$ip": fake.ipv4_public(),
         "$session_id": session_id,
         "$active_feature_flags": ["action_mode_on"],
         "$feature/action_mode_on": random.choice([True,False])
      }
   return properties

_identified_users = set()


def browse_and_watch_movie(number = 1, user=None, day_offset=None):
   fake_user = user or random.choice(fake_users)
   base_distinct_id = fake_user['email']
   family_id = fake_user['family_id']
   family_name = fake_user['last_name']

   posthog.group_identify('family', family_id, {'name': family_name})

   groups = {'family': family_id}

   # B3 identity instability: ~5% of users have 2-3 distinct_ids; per session we
   # pick one of them. Across multiple sessions the same user lands on different
   # IDs, so PostHog sees them as separate persons (no alias, no merge).
   distinct_id_pool = unstable_distinct_ids(fake_user, base_distinct_id)
   distinct_id = random.choice(distinct_id_pool)

   for i in range(random.randint(1, number)):
        timestamp = get_random_time(day_offset=day_offset)
        client_properties = get_client_properties(user=fake_user)

        # B1 partial identification: ~10% of users ever get identified.
        if base_distinct_id not in _identified_users:
            if maybe_identify_user(posthog, fake_user, distinct_id, timestamp,
                                   client_properties, probability=0.10, groups=groups):
                _identified_users.add(base_distinct_id)

        # B4 flag flip: ~5% of users emit a 3-event flip-flop pattern at session start.
        flag_flip_pattern(posthog, fake_user, distinct_id, timestamp,
                          client_properties, groups=groups)

        # A4 cost amplifier: $feature_flag_called flood once per session for
        # ~30% of sessions (action_mode_on flag re-evaluated 4x in a tight loop).
        if random.random() < 0.3:
            flag_eval_flood(posthog, distinct_id, ['action_mode_on'],
                            timestamp + timedelta(seconds=1),
                            client_properties, flood_count=4, groups=groups)

        # B2 identify spam: ~10% of sessions emit identify() five times.
        if random.random() < 0.10:
            identify_spam(posthog, distinct_id,
                          timestamp,
                          properties_to_set={
                              'email': fake_user['email'],
                              'plan': fake_user['plan'],
                              'is_adult': fake_user['is_adult'],
                          },
                          count=5)

        capture_event(event='user_logged_in', extra_properties=client_properties, timestamp=timestamp, distinct_id=distinct_id, groups=groups)

        timestamp = timestamp + timedelta(minutes=random.randint(1,5))

        capture_pageview(url='https://hogflix.net/', client_properties = client_properties,timestamp=timestamp, distinct_id = distinct_id, groups=groups)
        sprinkle_clicks_on_page(distinct_id, '/', timestamp, client_properties, groups,
                                family_id=family_id, family_name=family_name)

        movie_id = random.randint(1,3)

        timestamp = timestamp + timedelta(minutes=random.randint(1,15))

        capture_pageview(url=f'https://hogflix.net/movie/{movie_id}', client_properties = client_properties, timestamp=timestamp, distinct_id = distinct_id, groups=groups)
        sprinkle_clicks_on_page(distinct_id, f'/movie/{movie_id}', timestamp, client_properties, groups,
                                family_id=family_id, family_name=family_name)
        maybe_emit_exception(distinct_id, timestamp, client_properties, groups)

        # Simulate occasional revenue events
        if random.randrange(100) < 25:
            action_type = random.choice(['buy','rent'])
            price = 14.99 if action_type == 'buy' else 4.99
            value_minor = int(round(price * 100))
            movie_title = movies_catalog.get(movie_id, {}).get('title', f'Movie {movie_id}')

            # Intent event (no revenue aggregation)
            capture_event(
               event=f'movie_{action_type}_intent',
               extra_properties={
                  **client_properties,
                  "movie_id": movie_id,
                  "movie_title": movie_title,
                  "action": action_type,
                  "price": price,
                  "currency": "USD",
               },
               timestamp=timestamp + timedelta(minutes=1),
               distinct_id=distinct_id,
               groups=groups,
            )

            # Complete event with value and currency for Revenue Analytics
            capture_event(
               event=f'movie_{action_type}_complete',
               extra_properties={
                  **client_properties,
                  "movie_id": movie_id,
                  "movie_title": movie_title,
                  "action": action_type,
                  "value": value_minor,
                  "currency": "USD",
               },
               timestamp=timestamp + timedelta(minutes=2),
               distinct_id=distinct_id,
               groups=groups,
            )

def anon_browse_homepage_and_plans(day_offset=None):
   client_properties = get_client_properties()
   distinct_id = fake.uuid4()

   timestamp = get_random_time(day_offset=day_offset)

   # A6 cost amplifier: anonymous browse session creates a billed person profile
   # (mimics the customer running with person_profiles='always').
   anonymous_profile_creation(posthog, distinct_id, timestamp, client_properties)

   capture_pageview(url='https://hogflix.net/', client_properties = client_properties,timestamp=timestamp, distinct_id = distinct_id)
   sprinkle_clicks_on_page(distinct_id, '/', timestamp, client_properties)

   timestamp = timestamp + timedelta(minutes=random.randint(1,10))

   capture_pageview(url=f'https://hogflix.net/plans', client_properties = client_properties, timestamp=timestamp, distinct_id = distinct_id)
   sprinkle_clicks_on_page(distinct_id, '/plans', timestamp, client_properties)

   if random.randrange(100) < 40:
      maybe_emit_exception(distinct_id, timestamp, client_properties)
      return None

   timestamp = timestamp + timedelta(minutes=random.randint(1,10))

   capture_pageview(url=f'https://hogflix.net/signup', client_properties = client_properties, timestamp=timestamp, distinct_id = distinct_id)
   sprinkle_clicks_on_page(distinct_id, '/signup', timestamp, client_properties)
   maybe_emit_exception(distinct_id, timestamp, client_properties)

def browse_plans_and_signup(user=None, day_offset=None):
   fake_user = user or random.choice(fake_users)
   client_properties = get_client_properties(user=fake_user)
   distinct_id = fake_user['email']
   family_id = fake_user['family_id']
   family_name = fake_user['last_name']
   timestamp = get_random_time(day_offset=day_offset)

   posthog.group_identify('family', family_id, {'name': family_name})

   groups = {'family': family_id}

   # A4 cost amplifier: flag eval flood at session start.
   if random.random() < 0.3:
       flag_eval_flood(posthog, distinct_id, ['action_mode_on'],
                       timestamp + timedelta(seconds=1),
                       client_properties, flood_count=4, groups=groups)

   capture_pageview(url='https://hogflix.net/', client_properties = client_properties,timestamp=timestamp, distinct_id = distinct_id, groups=groups)
   sprinkle_clicks_on_page(distinct_id, '/', timestamp, client_properties, groups,
                           family_id=family_id, family_name=family_name)

   timestamp = timestamp + timedelta(minutes=random.randint(1,10))

   capture_pageview(url=f'https://hogflix.net/plans', client_properties = client_properties, timestamp=timestamp, distinct_id = distinct_id, groups=groups)
   sprinkle_clicks_on_page(distinct_id, '/plans', timestamp, client_properties, groups,
                           family_id=family_id, family_name=family_name)

   timestamp = timestamp + timedelta(minutes=random.randint(1,10))

   capture_pageview(url=f'https://hogflix.net/signup', client_properties = client_properties, timestamp=timestamp, distinct_id = distinct_id, groups=groups)
   sprinkle_clicks_on_page(distinct_id, '/signup', timestamp, client_properties, groups,
                           family_id=family_id, family_name=family_name)
   maybe_emit_exception(distinct_id, timestamp, client_properties, groups)

   timestamp = timestamp + timedelta(minutes=random.randint(1,10))

   selected_plans = random.sample(plans,2)
   previous_plan = selected_plans[0]
   new_plan_canonical = selected_plans[1]
   # C3 plan name drift: 5-10% of users see Maximal/Maxi-Mal instead of Max-imal.
   uid = _user_id_int(distinct_id)
   new_plan = plan_name_drift(new_plan_canonical, uid)
   # C6 date format drift: signup_date is sometimes Date, sometimes DateTime.
   signup_date = date_format_drift(datetime.now() - timedelta(days=random.randint(1, 60)), uid)
   client_properties = { **client_properties,
                        "previous_plan": previous_plan,
                        "new_plan": new_plan,
                        "signup_date": signup_date,
                        "$set": {
                           "plan": new_plan
                        }}
   capture_event(event='plan_changed', extra_properties=client_properties, timestamp=timestamp, distinct_id=distinct_id, groups=groups)

   # Emit subscription intent and purchase for Revenue Analytics
   months = 1
   price_dollars = 19.99 if new_plan == 'Max-imal' else 9.99 if new_plan == 'Premium' else 0
   timestamp = timestamp + timedelta(minutes=1)
   capture_event(event='subscription_intent', extra_properties={
      **client_properties,
      'plan': new_plan,
      'months': months,
      'price': int(round(price_dollars * 100)),
      'currency': 'USD',
   }, timestamp=timestamp, distinct_id=distinct_id, groups=groups)

   timestamp = timestamp + timedelta(minutes=1)
   purchase_props = {
      "timestamp": timestamp,
      **client_properties,
      'plan': new_plan,
      'months': months,
      'price': int(round(price_dollars * 100)),
      'currency': 'USD',
      # Structured 'address' property — C7 occasionally JSON-stringifies it.
      'address': {
         'city': fake.city(),
         'country': fake.country_code(),
         'zip': fake.postcode(),
      },
   }
   purchase_props = maybe_jsonify_property(purchase_props, 'address', uid, probability=0.05)
   # A5 cost amplifier: double-fire subscription_purchased. Apply C4 event-typo
   # before the double-fire so the typo'd variant also fires twice.
   subscription_event_name = apply_event_typo('subscription_purchased', uid)
   double_fire_purchase(posthog, distinct_id, subscription_event_name,
                        purchase_props, timestamp, groups=groups)

total_days = int(args.number_of_days)

# Pre-assign a deterministic signup_days_ago per fake_user. Distribute across
# the window so the growth curve has natural fuel: only old signups can be
# active on early days; recent signups appear later.
user_signups = {
    u['email']: random.Random(u['email']).randint(0, max(1, total_days - 1))
    for u in fake_users
}

# Track which users have already had a signup flow emitted (browse_plans_and_signup)
signed_up_users = set()

print(f"Generating events for {total_days} days, {len(fake_users)} potential users.")

for days_ago in range(total_days, -1, -1):
    target = daily_user_count(days_ago, total_days)
    eligible = [
        u for u in fake_users
        if is_user_active_on_day(_user_id_int(u['email']), days_ago, user_signups[u['email']])
    ]
    if len(eligible) > target:
        eligible = random.Random(days_ago).sample(eligible, target)

    for user in eligible:
        profile = behavioral_profile(_user_id_int(user['email']))

        # First active day for this user => emit the signup flow once.
        if user['email'] not in signed_up_users and user_signups[user['email']] == days_ago:
            browse_plans_and_signup(user=user, day_offset=days_ago)
            signed_up_users.add(user['email'])
            continue

        # Otherwise pick a flow shape based on profile.
        if profile == 'power':
            browse_and_watch_movie(number=4, user=user, day_offset=days_ago)
        elif profile == 'casual':
            browse_and_watch_movie(number=2, user=user, day_offset=days_ago)
        elif profile == 'churned':
            browse_and_watch_movie(number=1, user=user, day_offset=days_ago)
        elif profile == 'bouncer':
            # Bouncers also browse anonymously sometimes
            if random.random() < 0.5:
                anon_browse_homepage_and_plans(day_offset=days_ago)
            else:
                browse_and_watch_movie(number=1, user=user, day_offset=days_ago)

    # A handful of pure-anonymous browse sessions per day (top-of-funnel noise).
    for _ in range(max(1, target // 10)):
        anon_browse_homepage_and_plans(day_offset=days_ago)

    posthog.flush()