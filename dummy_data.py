# used to create some dummy data to show historical view count of movies in the profile etc. 

from app import app, db
from models import User, MovieStats
from datetime import datetime, timedelta, timezone
import random

def generate_dummy_data(user, start_date, end_date, time_frame, count_range, genre):
    current_date = start_date
    while current_date <= end_date:
        count = random.randint(*count_range)
        stat = MovieStats(user_id=user.id, time_frame=time_frame, count=count, date=current_date, genre=genre)
        db.session.add(stat)
        current_date += timedelta(days=7 if time_frame == 'week' else 30 if time_frame == 'month' else 365 if time_frame == 'year' else 1)
    db.session.commit()

with app.app_context():
    # Clear existing data
    MovieStats.query.delete()
    
    # Add dummy data for MovieStats
    user = User.query.first()

    # Generate data for weeks, months, and years
    today = datetime.now(timezone.utc).date()
    generate_dummy_data(user, today - timedelta(weeks=12), today, 'week', (1, 10), 'Action')  # Last 12 weeks for action movies
    generate_dummy_data(user, today - timedelta(weeks=12), today, 'week', (1, 10), 'Romantic Comedy')  # Last 12 weeks for romantic comedies
    generate_dummy_data(user, today - timedelta(days=365*5), today, 'month', (20, 100), 'Action')  # Last 5 years for action movies
    generate_dummy_data(user, today - timedelta(days=365*5), today, 'month', (20, 100), 'Romantic Comedy')  # Last 5 years for romantic comedies
    generate_dummy_data(user, today - timedelta(days=365*10), today, 'year', (200, 1000), 'Action')  # Last 10 years for action movies
    generate_dummy_data(user, today - timedelta(days=365*10), today, 'year', (200, 1000), 'Romantic Comedy')  # Last 10 years for romantic comedies

    print("Dummy data added successfully!")
