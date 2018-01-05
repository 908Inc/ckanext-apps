from ckan.lib.cli import CkanCommand

import logging
import sys


class AppsCommand(CkanCommand):
    """
    Usage:

        paster apps init_db
           - Creates the database table apps needs to run
    """
    summary = __doc__.split('\n')[0]
    usage = __doc__

    def command(self):
        """
        Parse command line arguments and call appropriate method.
        """
        if not self.args or self.args[0] in ['--help', '-h', 'help']:
            print self.usage
            sys.exit(1)

        cmd = self.args[0]
        self._load_config()

        self.log = logging.getLogger(__name__)

        if cmd == 'init_db':
            from ckanext.apps.models import init_db
            init_db()
            self.log.info('Apps tables have been initialized')
        else:
            self.log.warning('Command %s not recognized' % (cmd,))
