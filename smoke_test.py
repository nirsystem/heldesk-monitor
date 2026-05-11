import sys
import os

os.environ.setdefault('FLASK_SECRET_KEY', 'smoke-test-secret')
os.environ.setdefault('S3_BUCKET_NAME', '')
os.environ.setdefault('DB_DIR', '/tmp/helpdesk-test')

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

app = create_app()

with app.test_client() as c:
    r = c.get('/login')
    assert r.status_code == 200, f'Expected 200 on /login, got {r.status_code}'

print('Smoke test passed')
