from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Request(db.Model):
    __tablename__ = "requests"
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500))
    result = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)

class Usage(db.Model):
    __tablename__ = "usage"
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50))
    date = db.Column(db.String(20))
    count = db.Column(db.Integer, default=0)

class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
