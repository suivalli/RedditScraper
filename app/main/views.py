import datetime
import json
import os
import re
import requests
import time
from datetime import datetime
import csv

import praw
from flask import Blueprint, render_template, send_file
from flask import (
    flash,
    request,
)
from praw.models import MoreComments
from sqlalchemy.exc import InvalidRequestError

from app import db
from app.main.forms import ScrapeSubmissionForm, ShowCommentsForm
from app.models import EditableHTML, Submission, Comment

main = Blueprint('main', __name__)


@main.route('/')
def index():
    return render_template('main/index.html')


@main.route('/about')
def about():
    editable_html_obj = EditableHTML.get_editable_html('about')
    return render_template(
        'main/about.html', editable_html_obj=editable_html_obj)


@main.route('/scrape', methods=['GET', 'POST'])
def scrape():
    form = ScrapeSubmissionForm()
    if form.validate_on_submit():
        id = form.submission_id.data
        num_comments = scrape_reddit(id)
        flash('{} comments successfully added for the submission'.format(num_comments),
              'form-success')

    return render_template('main/scrape.html', form=form)


@main.route('/csv', methods=['POST'])
def csv_writing():
    id = request.form["id"]
    file = get_or_create_csv(id)
    return send_file(os.path.join("static", "csv", id + ".csv"))


def get_or_create_csv(id):
    file_path = os.path.join("app", "static", "csv", id + ".csv")
    if os.path.isfile(file_path):
        return file_path
    else:
        tl_comments = Comment.query.filter_by(parent_id=id).order_by(Comment.created_utc.asc())
        with open(file_path, 'w', newline='', encoding='utf-8') as file:
            f = csv.writer(file, quoting=csv.QUOTE_NONNUMERIC, delimiter='|')
            f.writerow(['ID', 'author', 'body', 'parent_id', 'permalink', 'created_utc', 'score'])
            write_csv(f, tl_comments)
        return file_path


def write_csv(f, comments):
    for comment in comments:
        f.writerow([
            comment.id, comment.author, comment.get_unescaped_body_no_newlines(), comment.parent_id, comment.permalink,
            comment.created_utc.strftime("%m/%d/%Y, %H:%M:%S"), comment.score
        ])
        if comment.get_children_count() > 0:
            write_csv(f, comment.get_children())

@main.route('/txt', methods=['POST'])
def txt():
    id = request.form["id"]
    file = get_or_create_txt(id)
    return send_file(os.path.join("static", "txt", id + ".txt"))


def get_or_create_txt(id):
    file_path = os.path.join("app", "static", "txt", id + ".txt")
    if os.path.isfile(file_path):
        return file_path
    else:
        tl_comments = Comment.query.filter_by(parent_id=id).order_by(Comment.created_utc.asc())
        f = open(file_path, "w", encoding="utf-8")
        write(f, tl_comments)
        f.close()
        return file_path


def write(f, comments, level=0):
    for comment in comments:
        line =""
        for i in range(0, level):
            line = line + "\t"
        line = line + "Author: " + comment.author + ", Commented on: " + comment.created_utc.strftime("%m/%d/%Y, %H:%M:%S") + "\n"
        f.write(line)
        line = ""
        for i in range(0, level):
            line = line + "\t"
        line = line + comment.get_unescaped_body() + "\n\n"
        f.write(line)
        if comment.get_children_count() > 0:
            write(f, comment.get_children(), level + 1)

@main.route('/read', methods=['GET', 'POST'], defaults={"page": 1})
@main.route('/read/<int:page>', methods=['GET', 'POST'])
def read(id=None, page=1):
    per_page = 25
    form = ShowCommentsForm()
    if form.validate_on_submit():
        id = form.submission_id.data.id
        tl_comments = Comment.query.filter_by(parent_id=id).order_by(Comment.created_utc.desc())\
            .paginate(page, per_page, error_out=False)  # Get top level comments
        return render_template('main/read.html', form=form, tl_comments=tl_comments, page=1, id=id)

    id = request.args.get("id")
    if id is not None:
        tl_comments = Comment.query.filter_by(parent_id=id).order_by(Comment.created_utc.desc()) \
            .paginate(page, per_page, error_out=False)  # Get top level comments
        return render_template('main/read.html', form=form, tl_comments=tl_comments, page=page, id=id)

    return render_template('main/read.html', form=form)



def scrape_reddit(id):
    user_agent = ("RScraper")
    r = praw.Reddit(user_agent=user_agent, client_id=os.getenv('REDDIT_CLIENT_ID'),
                         client_secret=os.getenv('REDDIT_SECRET'),
                         recirect_url=os.getenv('REDIRECT_URI'))

    submission = r.submission(id=id)

    if not submission.author:
        name = '[deleted]'
    else:
        name = submission.author.name

    if Submission.query.filter_by(id=id).count() == 0:
        sub = Submission(
            id=id,
            author=name,
            created_utc=datetime.fromtimestamp(submission.created_utc),
            score=submission.score,
            subreddit=submission.subreddit.name
        )

        db.session.add(sub)
        db.session.commit()

    comment_queue = submission.comments[:]
    while comment_queue:
        comment = comment_queue.pop(0)
        if isinstance(comment, MoreComments):
            comment_queue.extend(comment.comments())
        else:
            submit_comment(comment)
            comment_queue.extend(comment.replies)

    return submission.num_comments

def sanitize_link_id(link_id):
    if len(re.findall("^t[0-9]_", link_id)) == 0:
        return link_id
    else:
        return link_id.split("_")[1]


def submit_comment(comment):
    if Comment.query.filter_by(id=comment.id).count() != 0:
        return True
    if not comment.author:
        name = '[deleted]'
    else:
        name = comment.author.name

    link_id = sanitize_link_id(comment.link_id)
    parent_id = sanitize_link_id(comment.parent_id)

    com = Comment(
        id=comment.id,
        author=name,
        body=comment.body,
        parent_id=parent_id,
        permalink=comment.permalink,
        created_utc=datetime.fromtimestamp(comment.created_utc),
        score=comment.score,
        link_id=link_id
    )
    db.session.add(com)
    try:
        db.session.commit()
        return True
    except InvalidRequestError:
        return False


#Using pushshift instead of reddit API
'''
def make_request(uri, max_retries=5):
    def fire_away(uri):
        response = requests.get(uri)
        assert response.status_code == 200
        return json.loads(response.content)

    current_tries = 1
    while current_tries < max_retries:
        try:
            time.sleep(1)
            response = fire_away(uri)
            return response
        except:
            time.sleep(1)
            current_tries += 1
    return fire_away(uri)
    
    
def pull_comments_for(id, limit=20000):
    uri_template = r'https://api.pushshift.io/reddit/comment/search/?link_id={}&limit={}'
    return make_request(uri_template.format(id, limit))


def pull_submission_data(id, limit=1):
    uri_template = r'https://api.pushshift.io/reddit/submission/search/?ids={}&limit={}'
    return make_request(uri_template.format(id, limit))

def scrape_and_commit(id):

    if Submission.query.filter_by(id=id).count() == 0:
        submission_json = pull_submission_data(id)["data"][0]

        submission = Submission(
            id=submission_json["id"],
            author=submission_json["author"],
            created_utc=datetime.datetime.fromtimestamp(submission_json["created_utc"]),
            domain=submission_json["domain"],
            score=submission_json["score"],
            subreddit=submission_json["subreddit"]
        )
        db.session.add(submission)
        db.session.commit()

    comments_json = pull_comments_for(id)

    for comment_json in comments_json["data"]:
        if Comment.query.filter_by(id=comment_json["id"]).count() == 0:

            link_id = sanitize_link_id(comment_json["link_id"])

            comment = Comment(
                id=comment_json["id"],
                author=comment_json["author"],
                body=comment_json["body"],
                parent_id=comment_json["parent_id"],
                permalink=comment_json["permalink"],
                created_utc=datetime.datetime.fromtimestamp(comment_json["created_utc"]),
                score=comment_json["score"],
                link_id=link_id
            )

            db.session.add(comment)

    db.session.commit()

    return len(comments_json["data"])
'''

