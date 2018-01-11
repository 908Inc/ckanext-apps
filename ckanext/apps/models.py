# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from operator import isCallable

from ckan import model
from ckan.model import meta, User, Package, Session, Resource
from ckan.plugins import toolkit as tk

from sqlalchemy import types, Table, ForeignKey, Column
from sqlalchemy.orm import relation, backref, foreign, remote
from sqlalchemy.exc import ProgrammingError

from slugify import slugify_url

log = logging.getLogger(__name__)

DEFAULT_BOARDS = {
    'Мобільний додаток': '',
    'Чат-бот': '',
    'Візуалізація': ''
}


def init_db():
    """
    Create board, app, mark tables in the database.
    Prepopulate category table with default data.
    """
    if not model.package_table.exists():
        # during tests?
        return
    session = Session()
    for table in [board_table, app_table, mark_table]:
        if not table.exists():
            table.create(checkfirst=True)
            log.debug("Apps {} have been created".format(table.name))

    for board_name, board_desc in DEFAULT_BOARDS.iteritems():
        if not Board.get_by_slug(slugify_url(board_name)):
            board = Board()
            board.name = board_name
            board.slug = slugify_url(board_name)
            board.description = board_desc
            session.add(board)
            log.debug("Add {0} to {1} table".format(board_name, board_table.name))
            session.commit()

    if not migration_table.exists():
        migration_table.create(checkfirst=True)
        session.commit()
    migration_number = session.query(migration_table).count()
    log.debug('Migration number: %s', migration_number)
    migration_sql_list = [
    ]
    for counter, sql in enumerate(migration_sql_list, start=1):
        if migration_number < counter:
            try:
                session.execute(sql)
            except ProgrammingError:
                session.rollback()
            finally:
                session.execute(migration_table.insert())
                session.commit()

    session.close()


board_table = Table('apps_board', meta.metadata,
                    Column('id', types.Integer, primary_key=True, autoincrement=True),
                    Column('name', types.Unicode(128)),
                    Column('slug', types.String(128), unique=True),
                    Column('active', types.Boolean, default=True),
                    )

app_table = Table('apps_app', meta.metadata,
                  Column('id', types.Integer, primary_key=True, autoincrement=True),
                  Column('author_id', types.Unicode, nullable=False, index=True),
                  Column('board_id', types.Integer,
                         ForeignKey('apps_board.id', onupdate='CASCADE', ondelete='CASCADE'),
                         nullable=False, index=True),
                  Column('name', types.Unicode(128)),
                  Column('content', types.UnicodeText),
                  Column('created', types.DateTime, default=datetime.utcnow, nullable=False),
                  Column('status', types.Enum("active", "pending", "close", name="app_status"), default="pending"),
                  Column('closed_message', types.UnicodeText),
                  Column('image_url', types.UnicodeText),
                  Column('external_link', types.UnicodeText)
                  )

mark_table = Table('apps_mark', meta.metadata,
                   Column('id', types.Integer, primary_key=True, autoincrement=True),
                   Column('user_id', types.Unicode, nullable=False, index=True),
                   Column('app_id', types.Integer,
                          ForeignKey('apps_app.id', onupdate='CASCADE', ondelete='CASCADE'),
                          nullable=False, index=True),
                   Column('mark', types.Integer),
                   )

migration_table = Table('apps_migrations', meta.metadata,
                        Column('id', types.Integer, primary_key=True, autoincrement=True),
                        Column('created', types.DateTime, default=datetime.utcnow),
                        )


class Board(object):
    """
    Forum board mapping class
    """

    def get_absolute_url(self):
        return tk.url_for('apps_board_show', slug=self.slug)

    @classmethod
    def get_by_slug(cls, slug):
        return Session.query(cls).filter(cls.slug == slug).first()

    def save(self, commit=True):
        if not hasattr(self, 'slug') or not self.slug:
            self.slug = slugify_url(self.name)
        session = Session()
        log.debug(self)
        session.add(self)
        if commit:
            session.commit()

    @classmethod
    def all(cls):
        query = Session.query(cls)
        if hasattr(cls, 'order_by') and isCallable(cls.order_by):
            query = cls.order_by(query)
        return query.all()

    @classmethod
    def filter_active(cls):
        query = Session.query(cls).filter(cls.active == True)
        if hasattr(cls, 'order_by') and isCallable(cls.order_by):
            query = cls.order_by(query)
        return query.all()

    def hide(self):
        self.active = False
        session = Session()
        session.add(self)
        session.commit()

    def unhide(self):
        self.active = True
        session = Session()
        session.add(self)
        session.commit()


class App(object):
    """
    App thread mapping class
    """

    def get_rate(self):
        session = Session()
        marks = session.query(Mark).filter(Mark.app_id == self.id)
        if not marks.count():  # If no marks then return 0
            return 0
        return int(sum([mark.mark for mark in marks]) / marks.count())

    @classmethod
    def get_by_id(cls, id):
        return Session.query(cls).filter(cls.id == id).first()

    @classmethod
    def get_by_slug(cls, slug):
        return Session.query(cls).filter(cls.slug == slug).first()

    @classmethod
    def order_by(cls, query):
        return query.order_by(cls.created.desc())

    def get_absolute_url(self):
        return tk.url_for('apps_app_show', id=self.id)

    @classmethod
    def filter_board(cls, board_slug):
        return Session.query(cls).filter(cls.board.has(slug=board_slug), cls.status == "active")

    def save(self, commit=True):
        session = Session()
        log.debug(self)
        session.add(self)
        if commit:
            session.commit()

    @classmethod
    def all(cls):
        query = Session.query(cls).filter()
        if hasattr(cls, 'order_by') and isCallable(cls.order_by):
            query = cls.order_by(query)
        return query

    @classmethod
    def all_active(cls):
        query = Session.query(cls).filter(
            cls.status == 'active',
            cls.board_id.in_([b.id for b in Board.filter_active()]))
        if hasattr(cls, 'order_by') and isCallable(cls.order_by):
            query = cls.order_by(query)
        return query


class Mark(object):
    """
    Mark post mapping class
    """

    def save(self, commit=True):
        session = Session()
        log.debug(self)
        session.add(self)
        if commit:
            session.commit()

    @classmethod
    def get_by_id(cls, id):
        return Session.query(cls).filter(cls.id == id).first()

    @classmethod
    def filter_by_user_id(cls, id):
        return Session.query(cls).filter(cls.user_id == id)

    @classmethod
    def get_by_user(cls, id, app_id):
        return Session.query(cls).filter(cls.user_id == id, cls.app_id == app_id).first()

meta.mapper(Board, board_table)

meta.mapper(App,
            app_table,
            properties={
                'author': relation(User,
                                   backref=backref('apps_app', cascade='all, delete-orphan', single_parent=True),
                                   primaryjoin=foreign(app_table.c.author_id) == remote(User.id)
                                   ),
                'board': relation(Board,
                                  backref=backref('apps_app', cascade='all, delete-orphan', single_parent=True),
                                  primaryjoin=foreign(app_table.c.board_id) == remote(Board.id)
                                  )
            }
            )

meta.mapper(Mark,
            mark_table,
            properties={
                'user': relation(User,
                                 backref=backref('apps_mark', cascade='all, delete-orphan', single_parent=True),
                                 primaryjoin=foreign(mark_table.c.user_id) == remote(User.id)
                                 ),
                'app': relation(App,
                                backref=backref('apps_mark', cascade='all, delete-orphan', single_parent=True),
                                primaryjoin=foreign(mark_table.c.app_id) == remote(App.id))
            }
            )

if __name__ == "__main__":
    init_db()
