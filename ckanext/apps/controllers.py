import logging
from operator import itemgetter

from ckan.lib.base import BaseController, abort
from ckan.plugins import toolkit as tk
from ckan.lib.helpers import flash_success, flash_error
from ckan.common import c
from jinja2.filters import do_striptags


from ckanext.apps.models import App, Board, Mark
from ckanext.apps.forms import CreateAppForm, CreateBoardForm, CloseAppForm


log = logging.getLogger(__name__)


class AppsController(BaseController):
    paginated_by = 3

    def __render(self, template_name, context):
        if c.userobj is None or not c.userobj.sysadmin:
            board_list = Board.filter_active()
        else:
            board_list = Board.all()
        context.update({
            'board_list': board_list,
        })
        log.debug('AppController.__render context: %s', context)
        return tk.render(template_name, context)

    def index(self):
        page = int(tk.request.GET.get('page', 1))
        total_pages = int(App.all_active().count() / self.paginated_by) + 1
        if not 1 < page <= total_pages:
            page = 1
        context = {
            'apps_list': App.all_active().offset((page - 1) * self.paginated_by).limit(self.paginated_by),
            'total_pages': total_pages,
            'current_page': page,
        }
        log.debug('AppsController.index context: %s', context)
        return self.__render('apps_index.html', context)

    def close_app(self, id):
        if c.userobj is None or not c.userobj.sysadmin:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        app = App.get_by_id(id=id)
        if not app:
            tk.redirect_to(tk.url_for('apps_activity'))
        form = CloseAppForm(tk.request.POST)
        if tk.request.POST:
            if form.validate():
                form.populate_obj(app)
                app.status = "close"
                app.save()
                log.debug("Closed app")
                flash_success(tk._('You successfully closed app'))
                tk.redirect_to(tk.url_for('apps_activity'))
            else:
                flash_error(tk._('You have errors in form'))
                log.debug("Validate errors: %s", form.errors)
        context = {
            'form': form,
        }
        return self.__render('close_app.html', context)

    def show_app(self, id):
        app = App.get_by_id(id=id)
        if not app or app.status != "active":
            return tk.redirect_to(tk.url_for("apps_index"))
        if c.userobj:
            mark = Mark.get_by_user(c.userobj.id)
        else:
            mark = None
        return self.__render('show_app.html', {'app': app,
                                               'my_mark': mark.mark if mark else 0,
                                               'app_mark': Mark.get_app_mark(app.id)})

    def set_mark(self, id, rate):
        app = App.get_by_id(id=id)
        if c.userobj is None:
            return tk.redirect_to(tk.url_for(controller='user', action='login'))
        mark = Mark.get_by_user(c.userobj.id)
        try:
            rate = int(rate)
        except ValueError:
            return tk.redirect_to(tk.url_for('apps_index'))
        if 1 > rate > 6:
            return tk.redirect_to(tk.url_for('apps_index'))
        if not app or app.status != 'active':
            tk.redirect_to(tk.url_for('apps_index'))
        if not mark:
            mark = Mark()
            mark.user_id = c.userobj.id
            mark.app_id = app.id
        mark.mark = int(rate)
        mark.save()
        return tk.redirect_to(tk.url_for('apps_app_show', id=app.id))

    def app_add(self):
        if c.userobj is None:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        form = CreateAppForm(tk.request.POST)
        if tk.request.POST:
            if form.validate():
                app = App()
                form.populate_obj(app)
                app.author_id = c.userobj.id
                app.content = do_striptags(app.content)
                app.logo = do_striptags(app.logo)
                app.status = "pending"
                app.save()
                log.debug("App data is valid. Content: %s", do_striptags(app.name))
                flash_success(tk._('You successfully create app'))
                tk.redirect_to(app.get_absolute_url())
            else:
                flash_error(tk._('You have errors in form'))
                log.info("Validate errors: %s", form.errors)
        context = {
            'form': form,
        }
        log.debug('ForumController.thread_add context: %s', context)
        return self.__render('create_app.html', context)

    def board_add(self):
        if c.userobj is None:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        form = CreateBoardForm(tk.request.POST)
        if tk.request.POST:
            if form.validate():
                board = Board()
                form.populate_obj(board)
                board.save()
                flash_success(tk._('You successfully create thread'))
                tk.redirect_to(board.get_absolute_url())
            else:
                flash_error(tk._('You have errors in form'))
                log.info("Validate errors: %s", form.errors)
        context = {
            'form': form,
        }
        log.debug('AppsController.thread_add context: %s', context)
        return self.__render('create_board.html', context)

    def board_show(self, slug):
        board = Board.get_by_slug(slug)
        if not board:
            abort(404)
        page = int(tk.request.GET.get('page', 1))
        total_pages = int(App.filter_board(board_slug=board.slug).count() / self.paginated_by) + 1
        if not 1 < page <= total_pages:
            page = 1
        context = {
            'board': board,
            'apps_list': App.filter_board(board_slug=board.slug).offset((page - 1) * self.paginated_by).limit(self.paginated_by),
            'total_pages': total_pages,
            'current_page': page,
        }
        log.debug('AppController.board_show context: %s', context)
        return self.__render('apps_index.html', context)

    def activity(self):
        apps_activity = App.all().order_by(App.created.desc())
        activity = [dict(id=i.id,
                         url=i.get_absolute_url(),
                         content=i.content,
                         name=i.name,
                         status=i.status,
                         author_name=i.author.name,
                         created=i.created) for i in apps_activity]
        context = {
            'activity': sorted(activity, key=itemgetter('created'), reverse=True),
            'statuses': ["active", "pending", "close"]
        }
        return self.__render('apps_activity.html', context)

    def change_app_status(self, id, status):
        app = App.get_by_id(id=id)
        if not app:
            abort(404)
        if c.userobj is None or not c.userobj.sysadmin:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        app.status = status
        app.closed_message = ""
        app.save()
        tk.redirect_to(tk.url_for('apps_activity'))

    def board_hide(self, slug):
        board = Board.get_by_slug(slug)
        if not board:
            abort(404)
        if c.userobj is None or not c.userobj.sysadmin:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        board.hide()
        flash_success(tk._('You successfully hided board'))
        tk.redirect_to(tk.url_for('apps_index'))

    def board_unhide(self, slug):
        board = Board.get_by_slug(slug)
        if not board:
            abort(404)
        if c.userobj is None or not c.userobj.sysadmin:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        board.unhide()
        flash_success(tk._('You successfully unhided board'))
        tk.redirect_to(tk.url_for('apps_index'))