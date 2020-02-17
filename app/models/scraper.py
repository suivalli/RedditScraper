from flask import current_app
import html
from .. import db


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.String(20), primary_key=True)
    author = db.Column(db.String(20))
    body = db.Column(db.Text())
    parent_id = db.Column(db.String(20), index=True)
    permalink = db.Column(db.Text())
    created_utc = db.Column(db.DateTime())
    score = db.Column(db.Integer())

    link_id = db.Column(db.String(20), db.ForeignKey('submissions.id'), nullable=False)
    submission = db.relationship('Submission', backref=db.backref('comments'), lazy=True)

    def __repr__(self):
        return '<Comment \'%s\'>' % self.id

    def get_children_count(self):
        return Comment.query.filter_by(parent_id=self.id).count()

    def get_children(self):
        return Comment.query.filter_by(parent_id=self.id).all()

    def get_unescaped_body(self):
        return html.unescape(self.body)

    def get_unescaped_body_no_newlines(self):
        unescaped_body = self.get_unescaped_body()
        return " ".join(unescaped_body.splitlines())


class Submission(db.Model):
    __tablename__ = 'submissions'

    id = db.Column(db.String(20), primary_key=True)
    author = db.Column(db.String(20))
    created_utc = db.Column(db.DateTime())
    domain = db.Column(db.String(150))
    score = db.Column(db.Integer())
    subreddit = db.Column(db.String(100))

    def __repr__(self):
        return '<Submission \'%s\'>' % self.id
