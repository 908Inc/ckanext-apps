import logging
import os
from operator import itemgetter

import ckan.lib.jobs as jobs
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.lib.uploader as uploader
import ckan.logic as logic
import jinja2
from babel.support import Translations
from ckan.common import c
from ckan.lib.base import BaseController, abort
from ckan.lib.helpers import flash_success, flash_error, full_current_url, get_page_number, Page
from ckan.plugins import toolkit as tk
from jinja2.filters import do_striptags

from ckanext.apps.forms import CreateAppForm, CreateBoardForm, CloseAppForm
from ckanext.apps.models import App, Board, Mark

clean_dict = logic.clean_dict
parse_params = logic.parse_params
tuplize_dict = logic.tuplize_dict

log = logging.getLogger(__name__)


def do_if_user_not_sysadmin():
    if not c.userobj:
        tk.redirect_to(tk.url_for(controller='user', action='login', came_from=tk.request.path))
    if not c.userobj.sysadmin:
        abort(404)  # not 403 for security reasons


def send_notifications_on_change_app_status(app, status, lang):
    """ Send mail when app changes status  """
    from ckan.model import User

    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    locale_dir = os.path.join(os.path.dirname(__file__), 'i18n')
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), extensions=['jinja2.ext.i18n'])
    translations = Translations.load(locale_dir, [lang], domain='ckanext-apps')
    env.install_gettext_translations(translations)
    env.globals['get_locale'] = lambda: lang

    app_author = User.get(app.author_id)
    data = {
        'author_name': app_author.name,
        'site_title': tk.config.get('ckan.site_title'),
        'site_url': tk.config.get('ckan.site_url')
    }
    template_name = 'email/app_{0}_app_mail.html'.format(status)
    template = env.get_template(template_name)
    if status == 'close':
        data['closed_message'] = app.closed_message
    body = template.render(data)
    if status == 'pending':
        subject = tk._('You added an application')
    elif status == 'active':
        subject = tk._('Your application has been approved')
    elif status == 'close':
        subject = tk._('Your application has been rejected')
    else:
        subject = status
    tk.get_action('send_mail')({}, {
        'to': app_author.email,
        'subject': env.globals['gettext'](subject),
        'message_html': body
    })


class AppsController(BaseController):
    paginated_by = 10

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
        page = get_page_number(tk.request.params)
        total_rows = App.all_active().count()
        total_pages = (total_rows - 1) / self.paginated_by + 1
        if not 1 < page <= total_pages:
            page = 1

        apps_list = tk.get_action('apps_active_apps')(data_dict={"page": page, "paginated_by": self.paginated_by})
        c.page = Page(
            collection=apps_list,
            page=page,
            item_count=total_rows,
            items_per_page=self.paginated_by
        )
        context = {
            'apps_list': apps_list,
        }
        log.debug('AppsController.index context: %s', context)
        return self.__render('apps_index.html', context)
    # def index(self):
    #     print 'INDEx'
    #     page = get_page_number(tk.request.params)
    #     total_rows = App.all_active().count()
    #     total_pages = (total_rows - 1) / self.paginated_by + 1
    #     if not 1 < page <= total_pages:
    #         page = 1
    #     apps_list = tk.get_action('apps_active_apps')(data_dict={"page": page, "paginated_by": self.paginated_by})
    #     c.page = Page(
    #         collection=apps_list.all(),
    #         page=page,
    #         item_count=total_rows,
    #         items_per_page=self.paginated_by
    #     )
    #     print 'PAGER: {}'.format(c.page)
    #     context = {
    #         'apps_list': tk.get_action('apps_active_apps')(
    #             data_dict={"page": page, "paginated_by": self.paginated_by}
    #         ),
    #         'total_pages': total_pages,
    #         'current_page': page,
    #     }
    #     log.debug('AppsController.index context: %s', context)
    #     return self.__render('apps_index.html', context)

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
                jobs.enqueue(send_notifications_on_change_app_status,
                             [app, 'close', tk.request.environ.get('CKAN_LANG')])
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
            tk.redirect_to(tk.url_for(controller='user', action='login', came_from=full_current_url()))
        form = CreateAppForm(tk.request.POST)
        data_dict = clean_dict(dict_fns.unflatten(
            tuplize_dict(parse_params(tk.request.params))))
        upload = uploader.get_uploader('apps')
        if tk.request.POST:
            if form.validate():
                # Upload[load image
                upload.update_data_dict(data_dict, 'image_url',
                                        'image_upload', 'clear_upload')
                try:
                    upload.upload(uploader.get_max_image_size())
                except logic.ValidationError as err:
                    flash_error(err.error_dict['image_upload'][0])
                else:
                    app = App()
                    form.populate_obj(app)
                    app.author_id = c.userobj.id
                    app.content = do_striptags(app.content)
                    app.status = "pending"
                    app.image_url = data_dict.get('image_url')
                    app.save()
                    log.debug("App data is valid. Content: %s", do_striptags(app.name))
                    flash_success(tk._('You successfully create app'))
                    jobs.enqueue(send_notifications_on_change_app_status, [app, 'pending',
                                                                           tk.request.environ.get('CKAN_LANG')])
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
        page = get_page_number(tk.request.params)
        total_rows = App.filter_board(board_slug=board.slug).count()
        total_pages = int(total_rows / self.paginated_by) + 1
        if not 1 < page <= total_pages:
            page = 1
        apps_list =  App.filter_board(board_slug=board.slug).offset((page - 1) * self.paginated_by).limit(
            self.paginated_by)
        c.page = Page(
            collection=apps_list,
            page=page,
            item_count=total_rows,
            items_per_page=self.paginated_by
        )
        context = {
            'board': board,
            'apps_list': apps_list,
        }
        log.debug('AppController.board_show context: %s', context)
        return self.__render('apps_index.html', context)

    def activity(self):
        do_if_user_not_sysadmin()
        page = get_page_number(tk.request.params)
        total_rows = App.all().count()
        total_pages = (total_rows - 1) / self.paginated_by + 1
        if not 1 < page <= total_pages:
            page = 1
        apps_activity = App.all().order_by(App.created.desc()).offset((page - 1) * self.paginated_by).limit(self.paginated_by)
        activity = [dict(id=i.id,
                         url=i.get_absolute_url(),
                         content=i.content,
                         name=i.name,
                         status=i.status,
                         author_name=i.author.name,
                         created=i.created) for i in apps_activity]
        c.page = Page(
            collection=apps_activity,
            page=page,
            item_count=total_rows,
            items_per_page=self.paginated_by
        )
        context = {
            'activity': sorted(activity, key=itemgetter('created'), reverse=True),
            'statuses': ["active", "pending", "close"],
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
            jobs.enqueue(send_notifications_on_change_app_status, [app, 'active', tk.request.environ.get('CKAN_LANG')])
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
