from ckanext.apps.models import App


def get_active_apps(context, data_dict):
    if not data_dict:
        data_dict = dict()
    if "page" not in data_dict:
        data_dict["page"] = 1
    if "paginated_by" not in data_dict:
        data_dict["paginated_by"] = 3
    return App.all_active().offset((data_dict["page"] - 1) * data_dict["paginated_by"]).limit(data_dict["paginated_by"])