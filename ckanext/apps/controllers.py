import logging
from operator import itemgetter

import ckan.lib.jobs as jobs
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.lib.uploader as uploader
import ckan.logic as logic
from ckan.common import c
from ckan.lib.base import BaseController, abort
from ckan.lib.helpers import flash_success, flash_error
from ckan.plugins import toolkit as tk
from jinja2.filters import do_striptags

from ckanext.apps.forms import CreateAppForm, CreateBoardForm, CloseAppForm
from ckanext.apps.models import App, Board, Mark

clean_dict = logic.clean_dict
parse_params = logic.parse_params
tuplize_dict = logic.tuplize_dict

log = logging.getLogger(__name__)


def send_notifications_on_change_app_status(app, status):
    """ Send mail when app changes status  """
    from ckan.lib.mailer import mail_user
    from ckan.lib.base import render_jinja2
    from ckan.model import User

    app_author = User.get(app.author_id)
    data = {'author_name': app_author.name}
    template_name = 'mails/app_{0}_app_mail.html'.format(status)
    if status == 'close':
        data['closed_message'] = app.closed_message
    body = render_jinja2(template_name, data)
    mail_user(app_author, tk._('{0} app'.format(status)), body)


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
        total_pages = (App.all_active().count() - 1) / self.paginated_by + 1
        if not 1 < page <= total_pages:
            page = 1
        context = {
            'apps_list': tk.get_action('apps_active_apps')(
                data_dict={"page": page, "paginated_by": self.paginated_by}
            ),
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
                jobs.enqueue(send_notifications_on_change_app_status, [app, 'close'])
                flash_success(tk._('You successfully closed app'))
                tk.redirect_to(tk.url_for('apps_activity'))
            else:
                flash_error(tk._('You have errors in form'))
                log.debug("Validate errors: %s", form.errors)
        context = {
            'form': form
        }
        return self.__render('close_app.html', context)

    def show_app(self, id):
        app = App.get_by_id(id=id)
        if not app or app.status != "active":
            return tk.redirect_to(tk.url_for("apps_index"))
        return self.__render('show_app.html', {'app': app})

    def set_mark(self, id, rate):
        app = App.get_by_id(id=id)
        if c.userobj is None:
            return tk.redirect_to(tk.url_for(controller='user', action='login'))
        mark = Mark.get_by_user(c.userobj.id, app.id)
        try:
            rate = int(rate)
        except ValueError:
            return tk.redirect_to(tk.url_for('apps_index'))
        if 1 > rate > 6:
            return tk.redirect_to(tk.url_for('apps_index'))
        if not app or app.status != 'active':
            tk.redirect_to(tk.url_for('apps_index'))
        if app.author_id == c.userobj.id:
            flash_success(tk._('You can\'t set rank for your app'))
            return tk.redirect_to(tk.url_for('apps_app_show', id=app.id))
        if not mark:
            mark = Mark()
            mark.user_id = c.userobj.id
            mark.app_id = app.id
        mark.mark = rate
        mark.save()
        flash_success(tk._('You successfully set rank {0}'.format(rate)))
        return tk.redirect_to(tk.url_for('apps_app_show', id=app.id))

    def app_add(self):
        if c.userobj is None:
            tk.redirect_to(tk.url_for(controller='user', action='login'))
        form = CreateAppForm(tk.request.POST)
        data_dict = clean_dict(dict_fns.unflatten(
            tuplize_dict(parse_params(tk.request.params))))
        upload = uploader.get_uploader('apps')
        if tk.request.POST:
            if form.validate():
                # Upload[load image
                upload.update_data_dict(data_dict, 'image_url',
                                        'image_upload', 'clear_upload')
                upload.upload(uploader.get_max_image_size())

                app = App()
                form.populate_obj(app)
                app.author_id = c.userobj.id
                app.content = do_striptags(app.content)
                app.status = "pending"
                app.image_url = data_dict.get('image_url')
                app.save()
                log.debug("App data is valid. Content: %s", do_striptags(app.name))
                flash_success(tk._('You successfully create app'))
                jobs.enqueue(send_notifications_on_change_app_status, [app, 'pending'])
                tk.redirect_to(app.get_absolute_url())
            else:
                flash_error(tk._('You have errors in form'))
                log.info("Validate errors: %s", form.errors)
        context = {
            'form': form,
            'active_boards': Board.filter_active()
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
        return self.__render('create_app_board.html', context)

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
            'apps_list': App.filter_board(board_slug=board.slug).offset((page - 1) * self.paginated_by).limit(
                self.paginated_by),
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
        if app.status == 'active':
            jobs.enqueue(send_notifications_on_change_app_status, [app, 'active'])
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
