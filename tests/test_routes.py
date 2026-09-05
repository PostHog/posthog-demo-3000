import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SQLALCHEMY_DATABASE_URI', f"sqlite:///{tmp_path / 'test.sqlite'}")
    monkeypatch.setenv('PH_PROJECT_KEY', 'phc_test')
    for name in ('app', 'config', 'models', 'forms'):
        sys.modules.pop(name, None)
    import app as hogflix

    hogflix.app.config['WTF_CSRF_ENABLED'] = False
    hogflix.posthog.disabled = True
    captured = []
    monkeypatch.setattr(hogflix.posthog, 'capture', lambda event, **kwargs: captured.append((event, kwargs)))
    with hogflix.app.app_context():
        hogflix.db.create_all()
        yield hogflix.app.test_client(), captured
        hogflix.db.session.remove()
        hogflix.db.drop_all()


SIGNUP = dict(username='hog', email='hog@example.com', password='pw', password2='pw', plan='Premium')


def test_public_pages_render(client):
    c, _ = client
    for path in ['/', '/signup', '/login', '/plans', '/blog', '/toc', '/search_results?query=a']:
        assert c.get(path).status_code == 200, path
    assert c.get('/does-not-exist').status_code == 404


def test_signup_login_search_logout_capture_events(client):
    c, captured = client

    r = c.post('/signup', data=SIGNUP)
    assert r.status_code == 302 and r.headers['Location'].endswith('/login')

    r = c.post('/login', data=dict(username='hog', password='pw'))
    assert r.status_code == 302

    for path in ['/profile', '/settings', '/feature-flags', '/create_post']:
        assert c.get(path).status_code == 200, path
    assert c.post('/search', data=dict(query='hedge')).status_code == 302
    assert c.get('/logout').status_code == 302

    events = [(event, kwargs['distinct_id']) for event, kwargs in captured]
    assert events == [
        ('user_signed_up', 'hog@example.com'),
        ('subscription_purchased', 'hog@example.com'),
        ('user_logged_in', 'hog@example.com'),
        ('search_performed', 'hog@example.com'),
        ('user_logged_out', 'hog@example.com'),
    ]
    assert captured[1][1]['properties'] == {'plan': 'Premium', 'months': 1, 'price': 999, 'currency': 'USD'}
