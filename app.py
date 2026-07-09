import logging
import uuid
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, make_response, session
from config import DevelopmentConfig
from models import db, User, Movie, MovieStats, BlogPost
from forms import SignupForm, LoginForm, ChangePlanForm, BlogPostForm
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_wtf.csrf import CSRFProtect
from posthog import Posthog

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

# Initialize CSRF protection
csrf = CSRFProtect(app)

posthog = Posthog(app.config['PH_PROJECT_KEY'], host=app.config['PH_HOST'])
posthog.debug = True

db.init_app(app)
migrate = Migrate(app, db)

login = LoginManager(app)
login.login_view = 'login'

# --- LLM Chat setup (enabled when OPENAI_API_KEY is set) ---
chat_enabled = bool(app.config.get('OPENAI_API_KEY'))
openai_client = None
openai_instrumented = False
langchain_available = False
if chat_enabled:
    # Prefer LangChain for chat; fall back to direct OpenAI client
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage  # type: ignore
        from posthog.ai.langchain import CallbackHandler  # type: ignore
        langchain_available = True
    except Exception:
        langchain_available = False

    if not langchain_available:
        try:
            from posthog.ai.openai import OpenAI as PHOpenAI  # type: ignore
            openai_client = PHOpenAI(api_key=app.config['OPENAI_API_KEY'], posthog_client=posthog)
            openai_instrumented = True
        except Exception:
            try:
                from openai import OpenAI as RawOpenAI  # type: ignore
                openai_client = RawOpenAI(api_key=app.config['OPENAI_API_KEY'])
            except Exception:
                openai_client = None
                chat_enabled = False

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/')
def index():

    family_movies = Movie.query.filter_by(genre='Family').all()
    action_movies = Movie.query.filter_by(genre='Action').all()

    response = make_response(render_template(
        'index.html',
        family_movies=family_movies,
        action_movies=action_movies,
        chat_enabled=chat_enabled
    ))

    response.delete_cookie('posthog_js')

    return response


@app.route('/movie/<int:movie_id>')
def movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    return render_template('movie.html', movie=movie)

current_time = datetime.now()
formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
# Output example: "2024-01-15 14:30:45"

PLAN_PRICES = {
    "Premium": 9.99,
    "Max-imal": 19.99,
    "Free": 0
}


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    preselected_plan = request.args.get('plan')

    if request.method == 'POST':
        app.logger.debug(f"Form data received: {request.form}")
        plan = request.form.get('plan')  # Get plan from form data
        app.logger.debug(f"Plan value: {plan}")
        
        if form.validate_on_submit() and plan in ['Free', 'Premium', 'Max-imal']:
            user = User(
                username=form.username.data,
                email=form.email.data,
                plan=plan,
                is_adult=not form.is_adult.data  
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            app.logger.debug(f"New user created: {user.username} with plan: {user.plan}")
            posthog.capture(
                'user_signed_up',
                distinct_id=form.email.data,
                properties = {
                    'plan': plan,
                    'date_time': formatted_time
                }
            )
            # Subscription purchase event for Revenue Analytics
            try:
                months = 1
                price_dollars = PLAN_PRICES.get(plan, 0)
                posthog.capture(
                    'subscription_purchased',
                    distinct_id=form.email.data,
                    properties={
                        'plan': plan,
                        'months': months,
                        'price': int(round(price_dollars * 100)),
                        'currency': 'USD'
                    }
                )
            except Exception:
                pass
            flash('Congratulations, you are now a registered user!')
            return redirect(url_for('login'))
        else:
            if 'plan' not in request.form or not request.form['plan']:
                flash('Please select a plan.', 'error')
            app.logger.debug(f"Form validation failed. Errors: {form.errors}")
    
    return render_template('signup.html', form=form, preselected_plan=preselected_plan)


@app.route('/login', methods=['GET', 'POST'])

def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
        
        login_user(user, remember=True)
    

        flash('Welcome back!', 'success') 
        
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))
    
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        posthog.capture(
            'user_logged_out',                    # Required - name of the event
            distinct_id=current_user.email,       # Required - your user's ID
            properties={
                'date_time': formatted_time
            }
        )

    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index', reload='true'))


@app.route('/search', methods=['POST'])
@csrf.exempt  # Disable CSRF for this route for debugging. 
def search():
    query = request.form.get('query')
    posthog.capture('search_performed', distinct_id='search', properties={'query': query})
    return redirect(url_for('search_results', query=query))

@app.route('/search_results')
def search_results():
    query = request.args.get('query')
    movies = Movie.query.filter(Movie.title.like(f'%{query}%')).all()
    return render_template('search_results.html', query=query, movies=movies)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ChangePlanForm()

    if request.method == 'POST':
        new_plan = request.form.get('plan')
        app.logger.debug(f"Plan to update: {new_plan}")
        if new_plan in ['Free', 'Premium', 'Max-imal']:
            current_user.plan = new_plan
            try:
                db.session.commit()
                app.logger.debug(f"User plan updated to: {new_plan}")
                flash('Your subscription plan has been updated!')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True})
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating plan: {e}")
                flash('An error occurred while updating your plan. Please try again.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False})
        else:
            flash('Please select a valid plan.', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False})
        
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return redirect(url_for('profile'))

    stats_week = [stat.to_dict() for stat in MovieStats.query.filter_by(user_id=current_user.id, time_frame='week').all()]
    stats_month = [stat.to_dict() for stat in MovieStats.query.filter_by(user_id=current_user.id, time_frame='month').all()]
    stats_year = [stat.to_dict() for stat in MovieStats.query.filter_by(user_id=current_user.id, time_frame='year').all()]

    return render_template('profile.html', user=current_user, form=form, stats_week=stats_week, stats_month=stats_month, stats_year=stats_year)
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        pass
    return render_template('settings.html', user=current_user)

@app.route('/plans', methods=['GET'])
def plans():
    return render_template('plans.html', user=current_user)

@app.route('/fourohfour', methods=['GET'])
def fourohfour():
    return render_template('404.html', user=current_user)

@app.route('/blog')
def blog():
    posts = BlogPost.query.order_by(BlogPost.timestamp.desc()).all()
    return render_template('blog.html', posts=posts)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    form = BlogPostForm()
    if form.validate_on_submit():
        post = BlogPost(title=form.title.data, content=form.content.data)
        db.session.add(post)
        db.session.commit()
        flash('Blog post created successfully!', 'success')
        return redirect(url_for('blog'))
    return render_template('create_post.html', form=form)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/toc')
def toc():
    return render_template('toc.html')

@app.route('/feature-flags')
@login_required  # Optional: restrict to logged-in users only
def feature_flags():
    return render_template('feature_flags.html')

# --- Chat routes ---
@app.route('/chat', methods=['GET'])
def chat_page():
    if not chat_enabled:
        return redirect(url_for('index'))
    return render_template('chat.html', chat_enabled=chat_enabled)


@app.route('/chat', methods=['POST'])
@csrf.exempt
def chat_api():
    if not chat_enabled:
        return jsonify({ 'error': 'Chat disabled' }), 400

    user_message = (request.get_json() or {}).get('message') or request.form.get('message')
    if not user_message:
        return jsonify({ 'error': 'Message required' }), 400

    # Establish a stable conversation id for analytics and memory
    if 'conversation_id' not in session:
        session['conversation_id'] = uuid.uuid4().hex
    conversation_id = session['conversation_id']

    distinct_id = current_user.email if current_user.is_authenticated else request.remote_addr or 'anonymous'

    try:
        ai_text = None
        if 'history' not in session:
            session['history'] = []

        if langchain_available:
            # Build chat history for LangChain
            lc_messages = [
                SystemMessage(content=(
                    "You are HogFlix's helpful assistant. Keep answers concise and use GitHub-Flavored Markdown. "
                    "When appropriate, include code blocks fenced with the correct language."
                ))
            ]
            for m in session['history']:
                role = m.get('role')
                content = m.get('content')
                if role == 'user':
                    lc_messages.append(HumanMessage(content=content))
                elif role == 'assistant':
                    lc_messages.append(AIMessage(content=content))
            lc_messages.append(HumanMessage(content=user_message))

            model = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=app.config['OPENAI_API_KEY'],
                temperature=0.2,
            )

            # PostHog LangChain callback for detailed analytics
            try:
                callback_handler = CallbackHandler(
                    client=posthog,
                    distinct_id=distinct_id,
                    trace_id=conversation_id,
                    properties={"conversation_id": conversation_id},
                )
                result = model.invoke(lc_messages, config={"callbacks": [callback_handler]})
            except Exception:
                result = model.invoke(lc_messages)

            ai_text = getattr(result, 'content', None) or str(result)
        else:
            if openai_client is None:
                return jsonify({ 'error': 'Chat disabled' }), 400
            # Fallback to direct OpenAI client
            if hasattr(openai_client, 'responses'):
                resp = openai_client.responses.create(
                    model="gpt-4o-mini",
                    input=[{"role": "user", "content": user_message}],
                    **({"posthog_distinct_id": distinct_id} if openai_instrumented else {})
                )
                try:
                    ai_text = resp.output_text
                except Exception:
                    choice = getattr(resp, 'choices', [{}])[0] if hasattr(resp, 'choices') else None
                    ai_text = (choice.get('message', {}) or {}).get('content') if isinstance(choice, dict) else None
            else:
                completion = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": user_message}],
                )
                ai_text = completion.choices[0].message.content

        if not ai_text:
            ai_text = "(no response)"

        # Update session history
        session['history'].append({"role": "user", "content": user_message})
        session['history'].append({"role": "assistant", "content": ai_text})

        # Capture a basic generation event for visibility even without wrapper.
        # The LangChain callback and the PostHog-instrumented OpenAI client each
        # emit $ai_generation themselves, so only capture here when neither is active.
        if not (langchain_available or openai_instrumented):
            try:
                posthog.capture(
                    '$ai_generation',
                    distinct_id=distinct_id,
                    properties={
                        '$ai_model': 'gpt-4o-mini',
                        '$ai_provider': 'openai',
                        '$ai_input': user_message,
                        '$ai_output': ai_text,
                        '$ai_trace_id': conversation_id,
                    }
                )
            except Exception:
                pass

        return jsonify({ 'message': ai_text })
    except Exception as e:
        app.logger.exception('Chat API error')
        return jsonify({ 'error': 'Failed to generate response' }), 500

if __name__ == '__main__':
    # app.run(debug=True, host=app.config['APP_HOST'], port=app.config['APP_PORT'])
    app.run(debug=True)
