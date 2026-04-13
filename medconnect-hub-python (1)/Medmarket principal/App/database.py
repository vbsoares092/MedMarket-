from flask_sqlalchemy import SQLAlchemy

# Shared db instance — initialised in app.py via db.init_app(app)
db = SQLAlchemy()