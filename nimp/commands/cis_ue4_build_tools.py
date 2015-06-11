# -*- coding: utf-8 -*-

from nimp.commands._cis_command import *
from nimp.utilities.ue4 import *

#-------------------------------------------------------------------------------
class CisUe4BuildTools(CisCommand):
    abstract = 0
    def __init__(self):
        CisCommand.__init__(self,
                            'cis-ue4-build-tools',
                            'Builds and submits Unreal Tools')

    #---------------------------------------------------------------------------
    def cis_configure_arguments(self, env, parser):
        parser.add_argument('-r',
                            '--revision',
                            help    = 'Current revision',
                            metavar = '<revision>',
                            default = None)

        parser.add_argument('--no-checkin',
                            help    = 'Don\'t checkin result.',
                            action  = "store_false",
                            default = True)

        parser.add_argument('tools_to_build',
                            help    = 'Tools to build',
                            metavar = '<ARGS>',
                            nargs    = argparse.REMAINDER,
                            default = ['DotNetUtilities',
                                       'Swarm',
                                       'LightMass',
                                       'ShaderCompileWorker',
                                       'SymbolDebugger',
                                       'UnrealFileServer',
                                       'UnrealFrontend',
                                       'Swarm',
                                       'NetworkProfiler'])

        return True

    #---------------------------------------------------------------------------
    def _cis_run(self, env):
        return ue4_build_tools(env)