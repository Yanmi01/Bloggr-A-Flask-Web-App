from flask import Flask
from flask_mail import Mail
from dotenv import load_dotenv

import os

load_dotenv()

mail = Mail()

def create_app(test_config=None):
    #create and configure the app
    app = Flask(__name__, instance_relative_config = True)
    app.config.from_mapping(
        SECRET_KEY = os.environ.get('SECRET_KEY', 'dev'),
        DATABASE = os.path.join(app.instance_path, "BLOGGR.sqlite"),

        SESSION_COOKIE_SECURE=True,     
        SESSION_COOKIE_HTTPONLY=True,    
        SESSION_COOKIE_SAMESITE='Lax', 
        
        GOOGLE_CLIENT_ID=os.environ.get('GOOGLE_CLIENT_ID'),
        GOOGLE_CLIENT_SECRET=os.environ.get('GOOGLE_CLIENT_SECRET'),

        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=465,
        MAIL_USE_TLS=False,
        MAIL_USE_SSL = True,
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER'),
    )
    
    if test_config is None:
        #load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        #load the test config if passed in
        app.config.from_mapping(test_config)

    #ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass 

    # a simple page that says hello
    # @app.route("/hello")
    # def hello():
    #     return "Hello, to the World!"
    
    mail.init_app(app)

    from . import db
    db.init_app(app)
    
    from . import auth
    app.register_blueprint(auth.bp)

    auth.google = auth.init_oauth(app)

    from . import blog
    app.register_blueprint(blog.bp)
    app.add_url_rule("/", endpoint="index")

    return app


