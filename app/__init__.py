import os
from flask import Flask
from .db import init_db, close_db


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-me-in-production')

    db_dir = os.environ.get('DB_DIR', '/data')
    if db_dir == '/data' and not os.path.isdir('/data'):
        db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(db_dir, exist_ok=True)

    app.config['DB_PATH'] = os.path.join(db_dir, 'helpdesk.db')
    app.config['S3_BUCKET'] = os.environ.get('S3_BUCKET_NAME', '')
    app.config['AWS_REGION'] = os.environ.get('AWS_REGION', 'us-east-1')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    with app.app_context():
        init_db(app.config['DB_PATH'])

    app.teardown_appcontext(close_db)

    from .auth import auth_bp
    from .main import main_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app
