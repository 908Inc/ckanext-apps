from ckan import plugins
from ckan.plugins import toolkit as tk


class AppsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        tk.add_template_directory(config_, 'templates')
        tk.add_public_directory(config_, 'public')
        tk.add_resource('fanstatic', 'apps')

    # IRoutes

    def after_map(self, sub_map):
        from ckan.config.routing import SubMapper
        with SubMapper(sub_map, controller='ckanext.apps.controllers:AppsController') as m:
            m.connect('apps_index', '/apps', action='index')
            m.connect('apps_app_add', '/apps/add', action='app_add')
            m.connect('apps_board_add', '/apps/board_add', action='board_add')
            m.connect('apps_activity', '/apps/activity', action='activity')
            m.connect('apps_board_unhide', '/apps/:slug/unhide', action='board_unhide')
            m.connect('apps_board_hide', '/apps/:slug/hide', action='board_hide')
            m.connect('apps_board_show', '/apps/:slug', action='board_show')
            m.connect('apps_change_status', '/apps/:id/:status', action='change_app_status')
        return sub_map
