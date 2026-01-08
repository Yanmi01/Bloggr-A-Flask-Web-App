import sqlite3
from datetime import datetime

import click
from flask import current_app, g            # g is an object provided by Flask. It is a global namespace for holding any data you want during a single app context.
                                            # Also think of g as a request-scoped storage object where you create attributes dynamically that last only for that request.
def get_db():                               # Why use g? if not g, you might need to create a new db everytime needed or create a global db shared by everyone which is very risky
    if "db" not in g:                       # g provides one connection per request which is stored afely withoput any crosss-request interference and also cleaned up automatically 
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types = sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db

def close_db(e = None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


sqlite3.register_converter(
    "timestamp", lambda v: datetime.fromisoformat(v.decode())
)

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
