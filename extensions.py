from flask_migrate import Migrate
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
security = Security()
csrf = CSRFProtect()

import redis

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
