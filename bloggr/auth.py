import functools
import secrets
import sqlite3
import threading

from flask import (
    Blueprint, 
    flash, 
    g, 
    redirect, 
    render_template, 
    request, 
    session, 
    url_for,
    current_app
)

from flask_mail import Message

from authlib.integrations.flask_client import OAuth

from werkzeug.security import (
    check_password_hash, 
    generate_password_hash
)

from itsdangerous import URLSafeTimedSerializer


from bloggr.db import get_db
from bloggr import mail


bp = Blueprint('auth', __name__, url_prefix='/auth')

oauth = OAuth()
google = None

@bp.route("/register", methods = ("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        db = get_db()
        error = None

        if not username:
            error = "Username is required!"
        elif not password:
            error = "Password is required!"
        elif not email:
            error = "Email is required!"

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, email, password) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(password))
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = f"User {username} is already registered."
                flash(error)
                return render_template("auth/register.html")

            # email_sent = False
            # try:
            #     send_welcome_email(email, username)
            #     email_sent = True
            # except Exception as e:
            #     current_app.logger.error(f"Failed to send welcome email: {e}")
            
            # if email_sent:
            #     flash("Registration successful! We sent you a welcome email. Kindly log in.")
            # else:
            #     flash("Registration successful! Please log in.")
            app = current_app._get_current_object()
            thread = threading.Thread(
                target=send_welcome_email_async,
                args=(email, username, app)
            )
            thread.daemon = True
            thread.start()
            
            flash("Registration successful! Please log in.")
            return redirect(url_for("auth.login"))
                      
        flash(error)

    return render_template("auth/register.html")


def init_oauth(app):
    oauth.init_app(app)
    google = oauth.register(
        name = "google",
        client_id = app.config.get("GOOGLE_CLIENT_ID"),
        client_secret = app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs = {"scope": "openid email profile"},
    )

    return google


@bp.route("/login", methods = ("GET", "POST"))
def login():
    if request.method == "POST":
        username_or_email = request.form["username_or_email"]
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute(
            "SELECT * FROM user WHERE username = ? OR email = ?",
            (username_or_email, username_or_email),            
        ).fetchone()

        if user is None:
            error = "Incorrect Username or Email!"
        elif not check_password_hash(user["password"], password):
            error = "Incorrect Password."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        
        flash(error)

    return render_template("auth/login.html")


@bp.route("/login/google")
def login_google():
    try:
        redirect_url = url_for("auth.authorize_google", _external = True)
        return google.authorize_redirect(redirect_url)
    except Exception as e:
        current_app.logger.error(f"Error logging in: {str(e)}")
        flash("Error occurred during login")
        return redirect(url_for("auth.login"))
    
@bp.route("/authorize/google")
def authorize_google():
    try:
        token = google.authorize_access_token()
        
        if not token:
            flash("Google authorization was cancelled or failed. Please try again.")
            return redirect(url_for("auth.login"))
        
        # resp = google.get("userinfo")
        resp = google.get("https://www.googleapis.com/oauth2/v3/userinfo")

        if not resp.ok:
            raise Exception(f"Failed to fetch user info from Google.  Status: {resp.status_code}")
        
        user_info = resp.json()
        email = user_info.get("email")

        if not email:
            flash("Invalid Email")
            return redirect(url_for("auth.login"))
        
        username = email.split('@')[0]

        db = get_db()
        user = db.execute(
            "SELECT * FROM user WHERE email = ?", (email,)
        ).fetchone() 

        if not user:

            random_password = secrets.token_urlsafe(32)

            try:
                db.execute(
                    "INSERT INTO user (username, email, password) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(random_password))
                )
                db.commit()
            except sqlite3.IntegrityError:
                username = f"{username}_{secrets.token_hex(4)}"
                db.execute(
                    "INSERT INTO user (username, email, password) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(random_password))
                )
                db.commit()

            # try:
            #     send_welcome_email(email, username)
            # except Exception as e:
            #     current_app.logger.error(f"Failed to send welcome email to {email}: {e}")

            # Send welcome email in background using thread
            login_url = url_for('auth.login', _external=True)
            
            app = current_app._get_current_object()
            thread = threading.Thread(
                target=send_welcome_email_async,
                args=(email, username, app, login_url)
            )
            thread.daemon = True
            thread.start()

            user = db.execute(
                "SELECT * FROM user WHERE email = ?", (email,)
            ).fetchone()

        session.clear()

        session["user_id"] = user["id"]

        return redirect(url_for("index"))
    
    except Exception as e:
        current_app.logger.error(f"Error during Google authorization: {str(e)}")
        flash("Error occurred during Google login")
        return redirect(url_for("auth.login"))      


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):               # still trying to understand what is happening here
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        
        return view(**kwargs)
    
    return wrapped_view


@bp.route("/change_password", methods = ("GET", "POST"))
def change_password():

    if g.user is None:
        flash("You are not logged in")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        db = get_db()
        user_id = g.user["id"]
        user = db.execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone() 

        if check_password_hash(user["password"], current_password):
            db.execute(
            "UPDATE user SET password = ? "
            "WHERE id = ? ",
            (generate_password_hash(new_password), user_id)
            )
            db.commit()
            flash("Password changed successfully!")
            return redirect(url_for("auth.login"))
        else:
            flash("Incorrect password!")
        
                
    return render_template("auth/change_password.html")


def send_password_reset_email(user_email, token):
    try:
        reset_url = url_for("auth.reset_password", token = token, _external = True)

        msg = Message(
            subject = 'Bloggr: Password Reset Request',
            recipients = [user_email],
            sender = current_app.config["MAIL_DEFAULT_SENDER"]
        )

        msg.html = render_template("email/reset_password.html", reset_url = reset_url)

        try:
            mail.send(msg)
            current_app.logger.info(f"Password reset email sent to {user_email}")
        except Exception as e:
            print(f"SMTP Error: {str(e)}")
            return False
        return True
    
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        return False

def send_welcome_email(user_email, username, login_url):
    try:
        msg = Message(
            subject='Welcome to Bloggr!',
            recipients=[user_email],
            sender=current_app.config["MAIL_DEFAULT_SENDER"]
        )
        
        msg.html = render_template(
            "email/welcome.html", 
            username=username,
            # login_url=url_for('auth.login', _external=True)
            login_url = login_url
        )

        try:
            mail.send(msg)
            current_app.logger.info(f"Welcome email sent to {user_email}")
        except Exception as e:
            current_app.logger.error(f"SMTP connection failed: {e}")
            return False
            
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending welcome email: {str(e)}")
        return False

def send_welcome_email_async(user_email, username, app, login_url):
    """Send email in background thread"""
    with app.app_context():
        try:
            send_welcome_email(user_email, username, login_url)
        except Exception as e:
            app.logger.error(f"Background email failed: {e}")

@bp.route("/forgot_password", methods = ("GET", "POST"))
def forgot_password():
    if g.user:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        email = request.form["email"]
        db = get_db()
        user = db.execute(
            "SELECT * FROM user WHERE email = ? ", (email,)
        ).fetchone() 

        if user:
            try:
                confirm_serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
                token = confirm_serializer.dumps(email, salt="password-reset-salt")

                send_password_reset_email(user['email'], token)

            except Exception as e:
                current_app.logger.error(f"Error generating token: {str(e)}")

        flash("If that email exists, a reset link has been sent.")
        return redirect(url_for("index"))

    return render_template("auth/forgot_password.html")


@bp.route("/reset_password/<token>", methods=("GET", "POST"))
def reset_password(token):
    try:
        confirm_serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        email = confirm_serializer.loads(token, salt="password-reset-salt", max_age=600)
    except:
        flash("The password reset link is invalid or has expired!")
        return redirect(url_for("auth.forgot_password"))
    
    if request.method =="POST":
        new_password = request.form["new_password"]
        db = get_db()

        db.execute(
            "UPDATE user SET password = ? WHERE email = ?",
            (generate_password_hash(new_password), email)
        )
        db.commit()

        flash("Your password has been reset!")
        return redirect(url_for("auth.login"))
    
    return render_template("auth/reset_password.html")


@bp.route("/profile_page")
def profile_page():
    if g.user is  None:
        return redirect(url_for("auth.login"))
    
    return render_template("auth/profile_page.html")


