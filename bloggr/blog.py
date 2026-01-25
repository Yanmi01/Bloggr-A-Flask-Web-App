from flask import (
    Blueprint, 
    flash, 
    g, 
    redirect, 
    render_template, 
    request, url_for
)
from werkzeug.exceptions import abort
from bloggr.auth import login_required
from bloggr.db import get_db

bp = Blueprint("blog", __name__)

@bp.route("/")
def index():
    db = get_db()
    posts = db.execute(
        """
            SELECT p.id, title, body, created, author_id, username
            FROM post p JOIN user u ON p.author_id = u.id
            ORDER BY created DESC
        """,
    ).fetchall()
    return render_template("blog/index.html", posts=posts)

@bp.route("/create", methods = ("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required!"

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                "INSERT INTO post (title, body, author_id)"
                "VALUES (?, ?, ?)",
                (title, body, g.user["id"])
            )
            db.commit()
            return redirect(url_for("blog.index"))
        
    return render_template("blog/create.html")

def get_post(id, check_author=True):
    post = get_db().execute(
        """
            SELECT p.id, title, body, created, author_id, username
            FROM post p JOIN user u ON p.author_id = u.id
            WHERE p.id = ?
        """,
        (id,)
    ).fetchone()

    if post is None:
        abort(404, f"Post id {id} doesn't exit.")

    if check_author and post["author_id"] !=g.user["id"]:
        abort(403)

    return post

# add a detailed view to each post
@bp.route("/<int:id>/detailed_view")
def detailed_view(id):
    post = get_post(id, check_author = True)
    return render_template("blog/detailed_view.html", post = post)


@bp.route("/<int:id>/update", methods = ("GET", "POST"))
@login_required
def update(id):
    post = get_post(id)

    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required!"

        if error is not None:
            flash(error)

        else:
            db = get_db()
            db.execute(
                "UPDATE post SET title = ?, body = ?"
                "WHERE id = ?",
                (title, body, id)
            )
            db.commit()
            return redirect(url_for("blog.index"))
        
    return render_template("blog/update.html", post = post)

@bp.route("/<int:id>/delete", methods= ("POST",))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("blog.index"))

@bp.route("/<int:id>/like", methods= ("POST",))
@login_required
def like_post(id):
    db = get_db()
    post = get_post(id, check_author=False)

    current_likes = db.execute(
        "SELECT id FROM post_likes WHERE post_id = ? AND user_id =?",
        (id, g.user["id"])
    ).fetchone()

    if current_likes is None:
        db.execute(
            "INSERT INTO pos_likes (post_id, user_id) VALUES (?, ?)",
            (id, g.user["id"])
        )
        db.commit()

    return redirect(url_for("blog_index"))


@bp.route("/<int:id>/unlike", methods= ("POST",))
@login_required
def unlike_post(id):
    db = get_db()
    post = get_post(id, check_author=False)

    db.execute(
        "DELETE FROM post_like WHERE post_id =? AND user_id = ?",
        (id, g.user["id"])
    )
    db.commit()

    return redirect(url_for("blog.index"))
