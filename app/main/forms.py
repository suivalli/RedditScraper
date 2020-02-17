from flask_wtf import FlaskForm
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.fields import (
    StringField,
    SubmitField,
)

from wtforms.validators import (
    InputRequired,
    Length,
)

from app import db
from app.models import Submission



class ScrapeSubmissionForm(FlaskForm):
    submission_id = StringField('Submission ID', validators=[InputRequired(), Length(1, 20)])
    submit = SubmitField('Scrape Comments')


class ShowCommentsForm(FlaskForm):
    submission_id = QuerySelectField(
        'Submission ID',
        validators=[InputRequired()],
        get_label='id',
        query_factory=lambda: db.session.query(Submission).order_by('id'))
    submit = SubmitField('Show Comments')
