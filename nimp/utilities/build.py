# -*- coding: utf-8 -*-

import platform

from nimp.utilities.processes import *


def sanitize_config(env):
    ''' Cleans config related env variables '''
    if hasattr(env, 'configuration') and env.configuration is not None:
        std_configs = { 'debug'    : 'debug',
                        'devel'    : 'devel',
                        'release'  : 'release',
                        'test'     : 'test',
                        'shipping' : 'shipping',
                      }

        if env.configuration.lower() in std_configs:
            env.configuration = std_configs[env.configuration.lower()]
        else:
            env.configuration = ""

#---------------------------------------------------------------------------
def vsbuild(solution, platform_name, configuration, project = None, vs_version = '12', target = 'Build'):
    build_directory = '.'

    if is_windows():
        devenv_path = _find_devenv_path(vs_version)
        if devenv_path is None:
            log_error("Unable to find Visual Studio {0}", vs_version)
            return False
        command = [ devenv_path, solution ]
        command = command + [ '/' + target, configuration + '|' + platform_name ]
        if project is not None:
            command = command + [ '/project', project ]

        return call_process(build_directory, command) == 0

    else: # Mac and Linux alike
        command = [ 'xbuild', solution, '/verbosity:quiet', '/p:TargetFrameworkVersion=v4.5', '/p:TargetFrameworkProfile=', '/nologo' ]
        return call_process(build_directory, command) == 0


#-------------------------------------------------------------------------------
def _find_devenv_path(vs_version):
    devenv_path = None

    # First try the registry, because the environment variable is unreliable
    # (case of Visual Studio installed on a different drive; it still sets
    # the envvar to point to C:\Program Files even if devenv.com is on D:\)
    from winreg import OpenKey, QueryValue, HKEY_LOCAL_MACHINE
    key_path = 'SOFTWARE\\Classes\\VisualStudio.accessor.' + vs_version + '.0\\shell\\Open'
    try:
        with OpenKey(HKEY_LOCAL_MACHINE, key_path) as key:
            cmdline = QueryValue(key, 'Command')
            if cmdline[:1] == '"':
                cmdline = cmdline.split('"')[1]
            elif ' ' in cmdline:
                cmdline = cmdline.split(' ')[0]
            devenv_path = cmdline.replace('devenv.exe', 'devenv.com')
    except:
        pass

    # If the registry key is unhelpful, try the environment variable
    if not devenv_path:
        vstools_path = os.getenv('VS' + vs_version + '0COMNTOOLS')
        if vstools_path is not None:
            # Sanitize this because os.path.join sometimes gets confused
            if vstools_path[-1] in [ '/', '\\' ]:
                vstools_path = vstools_path[:-1]
            devenv_path = os.path.join(vstools_path, '../../Common7/IDE/devenv.com')

    if not os.path.exists(devenv_path):
        return None

    log_verbose("Found Visual Studio at {0}", devenv_path)
    return devenv_path


def install_distcc_and_ccache():
    """ Install environment variables suitable for distcc and ccache usage
        if relevant.
    """
    distcc_dir = '/usr/lib/distcc'
    ccache_dir = '/usr/lib/ccache'

    # Make sure distcc will be called if we use ccache
    if os.path.exists(distcc_dir):
        log_verbose('Found distcc, so setting CCACHE_PREFIX=distcc')
        os.environ['CCACHE_PREFIX'] = 'distcc'

    # Add ccache to PATH if it exists, otherwise add distcc
    if os.path.exists(ccache_dir):
        extra_path = ccache_dir
    elif os.path.exists(distcc_dir):
        extra_path = distcc_dir
    else:
        return
    log_verbose('Adding {0} to PATH', extra_path)
    os.environ['PATH'] = extra_path + ':' + os.getenv('PATH')

    if os.path.exists(distcc_dir):
        # Set DISTCC_HOSTS if necessary
        if not os.getenv('DISTCC_HOSTS'):
            hosts = subprocess.Popen(['lsdistcc'], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
            hosts = ' '.join(hosts.split())
            log_verbose('Setting DISTCC_HOSTS={0}', hosts)
            os.environ['DISTCC_HOSTS'] = hosts

        # Compute a reasonable number of workers for UBT
        if not os.getenv('UBT_PARALLEL'):
            workers = subprocess.Popen(['distcc', '-j'], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
            log_verbose('Setting UBT_PARALLEL={0}', workers)
            os.environ['UBT_PARALLEL'] = workers

