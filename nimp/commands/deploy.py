# -*- coding: utf-8 -*-

import zipfile

from nimp.commands._command import *
from nimp.utilities.ue3 import *
from nimp.utilities.ue4 import *
from nimp.utilities.deployment import *
from nimp.utilities.file_mapper import *

#-------------------------------------------------------------------------------
class DeployCommand(Command):
    def __init__(self):
        Command.__init__(self,
                         'deploy',
                         'Deployment command')

    #---------------------------------------------------------------------------
    def configure_arguments(self, env, parser):
        parser.add_argument('-r', '--revision',
                            help = 'revision',
                            metavar = '<revision>')

        parser.add_argument('-p', '--platform',
                            help = 'platform to deploy',
                            metavar = '<platform>')

        parser.add_argument('-c', '--configuration',
                            help = 'configuration to deploy',
                            metavar = '<config>')

        parser.add_argument('-t', '--target',
                            help = 'target to deploy (game, editor, tools)',
                            metavar = '<platform>')

        parser.add_argument('--max-revision',
                            help = 'Find a revision <= to this',
                            metavar = '<revision>')

        return True

    #---------------------------------------------------------------------------
    def run(self, env):
        files_to_deploy = mapper = env.map_files()

        mapper = mapper.to(env.root_dir)

        log_notification("Deploying version…")

        if env.revision is None:
            env.revision = get_latest_available_revision(env, env.binaries_archive, **vars(env))

        if env.revision is None:
            return False

        # Now uncompress the archive; it’s simple
        fd = open(sanitize_path(env.format(env.binaries_archive)), 'rb')
        z = zipfile.ZipFile(fd)
        for name in z.namelist():
            log_notification('Extracting {0} to {1}', name, env.root_dir)
            z.extract(name, sanitize_path(env.format(env.root_dir)))
        fd.close()

        return True

