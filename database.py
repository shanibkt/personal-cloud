from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Folder(db.Model):
    __tablename__ = 'folders'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subfolders = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]), lazy=True)
    files = db.relationship('File', backref='folder', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat()
        }

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    telegram_id = db.Column(db.Integer) # Message ID
    chat_id = db.Column(db.Integer) # Channel ID or User ID where it lives
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'size': self.size,
            'mime_type': self.mime_type,
            'telegram_id': self.telegram_id,
            'folder_id': self.folder_id,
            'created_at': self.created_at.isoformat()
        }
