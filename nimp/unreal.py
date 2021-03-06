# -*- coding: utf-8 -*-
# Copyright (c) 2014-2019 Dontnod Entertainment

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

''' Unreal Engine 4 related stuff '''

import json
import logging
import os
import platform
import re
import glob

import nimp.build
import nimp.system
import nimp.sys.platform
import nimp.sys.process
import nimp.summary

def load_config(env):
    ''' Loads Unreal specific configuration values on env before parsing
        command-line arguments '''
    ue4_file = 'UE4/Engine/Build/Build.version'
    ue4_dir = nimp.system.find_dir_containing_file(ue4_file)

    ''' Retry by looking for a Engine/ folder if failed to find UE4/ (pre-reboot compatibility) '''
    ue4_file = 'Engine/Build/Build.version'
    if not ue4_dir:
        ue4_dir = nimp.system.find_dir_containing_file(ue4_file)
    else:
        ue4_dir = os.path.join(ue4_dir, 'UE4') # (backward compatibility)

    if not ue4_dir:
        env.is_ue4 = False
        env.is_dne_legacy_ue4 = True
        return True

    env.is_ue4 = True

    with open('%s/%s' % (ue4_dir, ue4_file)) as version_file:
        data = json.load(version_file)
        env.ue4_major = data['MajorVersion']
        env.ue4_minor = data['MinorVersion']
        env.ue4_patch = data['PatchVersion']

    if not hasattr(env, 'vs_version') or env.vs_version is None:
        if env.ue4_minor < 20:
            env.vs_version = '14'
        else:
            env.vs_version = '15'

    env.ue4_dir = ue4_dir
    # Backward compatibility (TODO: remove later)
    env.is_dne_legacy_ue4 = (env.ue4_minor < 22)

    if not hasattr(env, 'root_dir') or env.root_dir is None:
        env.root_dir = os.path.normpath(ue4_dir)

    # The host platform
    env.ue4_host_platform = 'Win64' if nimp.sys.platform.is_windows() \
                       else 'Mac' if platform.system() == 'Darwin' \
                       else 'Linux'

    logging.debug('Found UE4 engine %s.%s.%s for %s in %s' % (env.ue4_major, env.ue4_minor, env.ue4_patch, env.ue4_host_platform, ue4_dir))

    # Forward compatibility (TODO: remove later when all configuration files use uproject)
    if hasattr(env, 'game'):
        env.uproject = env.game
    if hasattr(env, 'game_dir'):
        env.uproject_dir = env.game_dir

    # If no uproject information is provided, look for one
    if not hasattr(env, 'uproject_dir') or not hasattr(env, 'uproject'):
        patterns = set()
        for upd in glob.glob(ue4_dir + '/*.uprojectdirs'):
            with open(upd, 'r') as upd_file:
                for pattern in upd_file.readlines():
                    if pattern.startswith(';'):
                        continue
                    patterns.add(pattern.strip())
        for pat in patterns:
            for ufile in glob.glob('%s/%s/*/*.uproject' % (ue4_dir, pat)):
                uproject = os.path.splitext(os.path.basename(ufile))[0]
                # Prefer anything over template and engine test directories as default uproject
                if not hasattr(env, 'uproject') or 'TP_' in env.uproject or 'EngineTest' in env.uproject:
                    env.uproject = uproject
                if uproject == env.uproject:
                    env.uproject_dir = os.path.normpath(os.path.dirname(ufile))

    # Do not throw here, as it *could* be on purpose to not have any uproject
    #if not hasattr(env, 'uproject_dir'):
    #    raise KeyError('No uproject found.')

    # Backwards compatibility (TODO: remove later)
    if hasattr(env, 'uproject'):
        env.game = env.uproject
    if hasattr(env, 'uproject_dir'):
        env.game_dir = env.uproject_dir

    if hasattr(env, 'uproject') and hasattr(env, 'uproject_dir'):
        logging.debug('Found UE4 project %s in %s' % (env.uproject, env.uproject_dir))

    return True


def load_arguments(env):
    ''' Loads Unreal specific environment parameters. '''

    # This is safe even when we failed to detect UE4
    _ue4_sanitize_arguments(env)
    _ue4_set_env(env)

    if env.is_ue4:
        if not hasattr(env, 'target') or env.target is None:
            if env.platform in ['win64', 'mac', 'linux']:
                env.target = 'editor'
            else:
                env.target = 'game'

    return True


# TODO: deprecate this in favour of env.ue4_host_platform
def get_host_platform():
    ''' Get the Unreal platform for the host platform '''
    if platform.system() == 'Windows':
        return 'Win64'
    if platform.system() == 'Linux':
        return 'Linux'
    if platform.system() == 'Darwin':
        return 'Mac'
    raise ValueError('Unsupported platform: ' + platform.system())


def get_configuration_platform(ue4_platform):
    ''' Gets the platform name used for configuration files '''
    # From PlatformProperties IniPlatformName
    platform_map = {
        "Android": "Android",
        "IOS": "IOS",
        "Linux": "Linux",
        "Mac": "Mac",
        "PS4": "PS4",
        "Win32": "Windows",
        "Win64": "Windows",
        "XboxOne": "XboxOne",
    }
    return platform_map[ue4_platform]

def get_cook_platform(ue4_platform):
    ''' Gets the platform name used for cooking assets '''
    # From Automation GetCookPlatform
    platform_map = {
        "Android": "Android",
        "IOS": "IOS",
        "Linux": "LinuxNoEditor",
        "Mac": "MacNoEditor",
        "PS4": "PS4",
        "Win32": "WindowsNoEditor",
        "Win64": "WindowsNoEditor",
        "XboxOne": "XboxOne",
    }
    return platform_map[ue4_platform]


def commandlet(env, command, *args, heartbeat = 0):
    ''' Runs an Unreal Engine commandlet. It can be usefull to run it through
        nimp as OutputDebugString will be redirected to standard output. '''
    if not _check_for_unreal(env):
        return False
    return _ue4_commandlet(env, command, *args, heartbeat = heartbeat)

def is_unreal4_available(env):
    ''' Returns a tuple containing unreal availability and a help text
        giving a reason of why it isn't if it's the case '''
    return env.is_ue4, ('No .nimp.conf configured for Unreal 4 was found in '
                        'this directory or one of its parents. Check that you '
                        'are launching nimp from inside an UE4 project directory'
                        ' and that you have a properly configured .nimp.conf. '
                        'Check documentation for more details on .nimp.conf.')

def _check_for_unreal(env):
    if not env.is_ue4:
        logging.error('This doesn\'t seems to be a supported project type.')
        logging.error('Check that you are launching nimp from an UE project')
        logging.error('directory, and that you have a .nimp.conf file in the')
        logging.error('project root directory (see documentation for further')
        logging.error('details)')
        return False
    return True


def _ue4_commandlet(env, command, *args, heartbeat = 0):
    ''' Runs an UE4 commandlet '''

    exe = '{ue4_dir}/Engine/Binaries/{ue4_host_platform}/UE4Editor.exe'
    cmdline = [nimp.system.sanitize_path(env.format(exe)),
               env.game,
               '-run=%s' % command]

    cmdline += list(args)
    cmdline += ['-buildmachine', '-nopause', '-unattended', '-noscriptcheck']
    # Remove -forcelogflush because it slows down cooking
    # (https://udn.unrealengine.com/questions/330502/increased-cook-times-in-ue414.html)
    #cmdline += ['-forcelogflush']

    return nimp.sys.process.call(cmdline, heartbeat=heartbeat) == 0


def _ue4_sanitize_arguments(env):

    if hasattr(env, "platform") and env.platform is not None:
        def sanitize_platform(platform):
            ''' Sanitizes platform '''
            std_platforms = { "ps4"       : "ps4",
                              "orbis"     : "ps4",
                              "xboxone"   : "xboxone",
                              "dingo"     : "xboxone",
                              "win32"     : "win32",
                              "pcconsole" : "win32",
                              "win64"     : "win64",
                              "pc"        : "win64",
                              "windows"   : "win64",
                              "xbox360"   : "xbox360",
                              "x360"      : "xbox360",
                              "ps3"       : "ps3",
                              "linux"     : "linux",
                              "android"   : "android",
                              "switch"    : "switch",
                              "nx"        : "switch",
                              "mac"       : "mac",
                              "macos"     : "mac",
                              "ios"       : "ios" }

            if platform.lower() not in std_platforms:
                return platform
            return std_platforms[platform.lower()]

        ue4_platform = '+'.join(map(sanitize_platform, env.platform.split('+')))

        env.is_win32   = 'win32'   in ue4_platform.split('+')
        env.is_win64   = 'win64'   in ue4_platform.split('+')
        env.is_ps3     = 'ps3'     in ue4_platform.split('+')
        env.is_ps4     = 'ps4'     in ue4_platform.split('+')
        env.is_x360    = 'xbox360' in ue4_platform.split('+')
        env.is_xone    = 'xboxone' in ue4_platform.split('+')
        env.is_linux   = 'linux'   in ue4_platform.split('+')
        env.is_android = 'android' in ue4_platform.split('+')
        env.is_mac     = 'mac'     in ue4_platform.split('+')
        env.is_ios     = 'ios'     in ue4_platform.split('+')
        env.is_switch  = 'switch'  in ue4_platform.split('+')

        env.is_microsoft_platform = env.is_win32 or env.is_win64 or env.is_x360 or env.is_xone
        env.is_sony_platform      = env.is_ps3 or env.is_ps4
        env.is_mobile_platform    = env.is_ios or env.is_android

        if env.is_ue4:
            env.platform = ue4_platform

    if hasattr(env, 'configuration') and env.configuration is not None:
        def sanitize_config(config):
            ''' Sanitizes config '''
            std_configs = { 'debug'    : 'debug',
                            'devel'    : 'devel',
                            'release'  : 'release',
                            'test'     : 'test',
                            'shipping' : 'shipping',
                          }

            if config.lower() not in std_configs:
                return ""
            return std_configs[config.lower()]

        ue4_configuration = '+'.join(map(sanitize_config, env.configuration.split('+')))

        if env.is_ue4:
            env.configuration = ue4_configuration


def _ue4_set_env(env):

    ''' Sets some variables for use with unreal 4 '''
    def _get_ue4_config(config):
        configs = { "debug"    : "Debug",
                    "devel"    : "Development",
                    "test"     : "Test",
                    "shipping" : "Shipping", }
        if config not in configs:
            if env.is_ue4:
                logging.warning('Unsupported UE4 build config “%s”', config)
            return None
        return configs[config]

    def _get_ue4_platform(in_platform):
        platforms = { "ps4"     : "PS4",
                      "xboxone" : "XboxOne",
                      "win64"   : "Win64",
                      "win32"   : "Win32",
                      "linux"   : "Linux",
                      "android" : "Android",
                      "switch"  : "Switch",
                      "mac"     : "Mac",
                      "ios"     : "IOS", }
        if in_platform not in platforms:
            if env.is_ue4:
                logging.warning('Unsupported UE4 build platform “%s”', in_platform)
            return None
        return platforms[in_platform]

    if hasattr(env, 'platform') and env.platform is not None:
        platform_list = list(map(_get_ue4_platform, env.platform.split('+')))
        if None not in platform_list:
            env.ue4_platform = '+'.join(platform_list)

    # Transform configuration list, default to 'devel'
    if hasattr(env, 'configuration') and env.configuration is not None:
        config = env.configuration
    else:
        config = 'devel'
    config_list = list(map(_get_ue4_config, config.split('+')))
    if None not in config_list:
        env.ue4_config = '+'.join(config_list)


def _cant_find_file(_, group_dict):
    assert 'asset' in group_dict
    asset_name = group_dict['asset']
    msg_str = ('This asset contains a reference to %s which is missing.'
               'You probably didn\'t fix references when deleting it, or '
               'you forgot to add it to source control.')
    return msg_str % asset_name

_MESSAGE_PATTERNS = [
    (re.compile(r'.*Can\'t find file.* \'\(?P<asset>[^\']\)\'.*'), _cant_find_file)
]

class _AssetSummary():
    def __init__(self, hints, asset_name):
        self._hints = hints
        self._asset_name = asset_name
        self._errors = set()
        self._warnings = set()

    def add_error(self, msg):
        """ Adds a message to this asset's summary """
        self._add_message(msg, self._errors)

    def add_warning(self, msg):
        """ Adds a message to this asset's summary """
        self._add_message(msg, self._warnings)

    def write(self, destination):
        """ Writes summary for this asset into destination """
        if not self._errors and not self._warnings:
            return
        destination.write('%s :\n' % self._asset_name)
        for error in self._errors:
            destination.write(' * ERROR   : %s\n' % error)
        for warning in self._warnings:
            destination.write(' * WARNING : %s\n' % warning)

        destination.write('\n')

    def _add_message(self, msg, destination):
        for message_format, patterns in self._hints.items():
            for pattern in patterns:
                match = pattern.match(msg)
                if match is not None:
                    try:
                        group_dict = match.groupdict()
                        message = message_format.format(**group_dict)
                        destination.add(message)
                        return
                    finally:
                        pass

        destination.add(msg)

class UnrealSummaryHandler(nimp.summary.SummaryHandler):
    """ Default summary handler, showing one line by error / warning and
    adding three lines of context before / after errors """
    def __init__(self, env):
        super().__init__(env)
        self._summary = ''
        self._asset_summaries = {}
        self._hints = {}
        self._load_asset_patterns = {}
        self._current_asset = None
        self._unknown_asset = _AssetSummary(self._hints, 'Unknown location')
        load_asset_patterns = [
            r'.*\[\d+\/\d+\] Loading [\.|\/]*(?P<asset>.*)\.\.\.$'
        ]

        self._load_asset_patterns = [
            re.compile(it) for it in load_asset_patterns
        ]

        if hasattr(env, 'unreal_summary_hints'):
            for message_format, patterns in env.unreal_summary_hints.items():
                self._hints[message_format] = []
                for pattern in patterns:
                    try:
                        self._hints[message_format].append(re.compile(pattern))
                    #pylint: disable=broad-except
                    except Exception as ex:
                        logging.error('Error while compiling pattern %s: %s',
                                      pattern, ex)

    def _add_notif(self, msg):
        self._update_current_asset(msg)

    def _add_warning(self, msg):
        current_asset = self._update_current_asset(msg)
        current_asset.add_warning(msg)

    def _add_error(self, msg):
        current_asset = self._update_current_asset(msg)
        current_asset.add_error(msg)

    def _write_summary(self, destination):
        ''' Writes summary to destination '''
        for _, asset_summary in self._asset_summaries.items():
            asset_summary.write(destination)

        self._unknown_asset.write(destination)

    def _update_current_asset(self, msg):
        for pattern in self._load_asset_patterns:
            match = pattern.match(msg)
            if match is not None:
                group_dict = match.groupdict()
                assert 'asset' in group_dict
                asset_name = group_dict['asset']
                if asset_name not in self._asset_summaries:
                    asset_summary = _AssetSummary(self._hints, asset_name)
                    self._asset_summaries[asset_name] = asset_summary

                self._current_asset = self._asset_summaries[asset_name]
                return self._current_asset

        if self._current_asset is not None:
            return self._current_asset

        return self._unknown_asset
