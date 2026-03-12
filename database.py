from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class CDR(db.Model):
    __tablename__ = "cd_ratio_table"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    px_id      = db.Column(db.Integer, nullable=False, index=True)
    eye        = db.Column(db.String(5), nullable=False, default='right')  # 'right' | 'left'
    year       = db.Column(db.Integer, nullable=False)
    cd_ratio   = db.Column(db.Float, nullable=False)
    disc_area  = db.Column(db.Float, nullable=True)
    cup_area   = db.Column(db.Float, nullable=True)
    notes      = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id":         self.id,
            "px_id":      self.px_id,
            "eye":        self.eye,
            "year":       self.year,
            "cd_ratio":   round(self.cd_ratio, 4),
            "disc_area":  self.disc_area,
            "cup_area":   self.cup_area,
            "notes":      self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# Keep alias so existing imports don't break
cd_ratio_table = CDR








