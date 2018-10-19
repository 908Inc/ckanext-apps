from ckan import plugins
from ckan.plugins import toolkit as tk
from ckanext.apps import actions


if tk.check_ckan_version(min_version='2.5'):
    from ckan.lib.plugins import DefaultTranslation


    class AppsPluginBase(plugins.SingletonPlugin, DefaultTranslation):
        plugins.implements(plugins.ITranslation, inherit=True)
else:
    class AppsPluginBase(plugins.SingletonPlugin):
        pass


class AppsPlugin(AppsPluginBase):
    plugins.implements(plugins.IConfigurer, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IActions, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        tk.add_template_directory(config_, 'templates')
        tk.add_public_directory(config_, 'public')
        tk.add_resource('fanstatic', 'apps')

    # IRoutes

    def after_map(self, sub_map):
        from ckan.config.routing import SubMapper
        with SubMapper(sub_map, controller='ckanext.apps.controllers:AppsController') as m:
            m.connect('apps_index', '/apps', action='index',
                      highlight_actions='index show_app app_add board_add activity board_show')
            m.connect('apps_app_show', '/apps/show/:id', action='show_app')
            m.connect('apps_app_edit', '/apps/edit/:id', action='edit_app')
            m.connect('apps_app_add', '/apps/add', action='app_add')
            m.connect('apps_board_add', '/apps/board_add', action='board_add')
            m.connect('apps_activity', '/apps/activity', action='activity')
            m.connect('apps_board_unhide', '/apps/:slug/unhide', action='board_unhide')
            m.connect('apps_board_hide', '/apps/:slug/hide', action='board_hide')
            m.connect('apps_board_show', '/apps/:slug', action='board_show')
            m.connect('apps_close_app', '/apps/:id/close', action='close_app')
            m.connect('apps_change_status', '/apps/:id/:status', action='change_app_status')
            m.connect('apps_app_set_mark', '/apps/mark/:id/:rate', action='set_mark')
        return sub_map

    # IActions

    def get_actions(self):
        actions_dict = {
            'apps_active_apps': actions.get_active_apps,
        }
        return actions_dict
