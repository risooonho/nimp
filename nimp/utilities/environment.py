# -*- coding: utf-8 -*-
''' Class and function relative to the nimp environment, i.e. configuration
values and command line parameters set for this nimp execution '''

import time
import platform
import os

import nimp.utilities.file_mapper
import nimp.utilities.logging
import nimp.utilities.system
import nimp.utilities.ue3
import nimp.utilities.ue4

class Environment:
    ''' Environment '''

    def __init__(self):
        # Some Windows tools don’t like “duplicate” environment variables, i.e.
        # where only the case differs; we remove any lowercase version we find.
        # The loop is O(n²) but we don’t have that many entries so it’s all right.
        env_vars = [x.lower() for x in os.environ.keys()]
        for dupe in set([x for x in env_vars if env_vars.count(x) > 1]):
            dupelist = sorted([x for x in os.environ.keys() if x.lower() == dupe ])
            nimp.utilities.logging.log_warning("Fixing duplicate environment variable: " + '/'.join(dupelist))
            for duplicated in dupelist[1:]:
                del os.environ[duplicated]
        # … But in some cases (Windows Python) the duplicate variables are masked
        # by the os.environ wrapper, so we do it another way to make sure there
        # are no dupes:
        for key in sorted(os.environ.keys()):
            val = os.environ[key]
            del os.environ[key]
            os.environ[key] = val

        self.command_to_run = None
        self.configuration           = None
        self.dlc                     = None
        self.environment             = {}
        self.is_linux                = False
        self.is_mac                  = False
        self.is_microsoft_platform   = False
        self.is_ps3                  = False
        self.is_ps4                  = False
        self.is_sony_platform        = False
        self.is_ue3                  = False
        self.is_ue4                  = False
        self.is_win32                = False
        self.is_win64                = False
        self.is_x360                 = False
        self.is_xone                 = False
        self.platform                = None
        self.project_type            = None
        self.root_dir                = None
        self.target                  = None
        self.ue3_build_configuration = None
        self.ue3_build_platform      = None
        self.ue3_cook_directory      = None
        self.ue3_cook_platform       = None
        self.ue3_shader_platform     = None
        self.ue4_build_configuration = None
        self.ue4_build_platform      = None
        self.ue4_cook_platform       = None
        self.wwise_banks_platform    = None

    def format(self, fmt, **override_kwargs):
        ''' Interpolates given string with config values & command line para-
            meters set in the environment '''
        assert isinstance(fmt, str)
        kwargs = vars(self).copy()
        kwargs.update(override_kwargs)
        result = fmt.format(**kwargs)
        result = time.strftime(result)
        return result

    def call(self, method, *args, **override_kwargs):
        ''' Calls a method after interpolating its arguments '''
        kwargs = vars(self).copy()
        kwargs.update(override_kwargs)
        return method(*args, **kwargs)

    def map_files(self):
        ''' Returns a file mapper to list / copy files. '''
        def _default_mapper(_, dest):
            yield (self.root_dir, dest)
        return nimp.utilities.file_mapper.FileMapper(_default_mapper, format_args = vars(self))

    def check_keys(self, *args):
        ''' Checks if a given key is set on this environment '''
        error_format = "{key} should be defined, either in settings or in command line arguments. Check those."
        return check_keys(vars(self), error_format, *args)

    #---------------------------------------------------------------------------
    def load_config_file(self, filename):
        ''' Loads a config file and adds its values to this environment '''
        settings_content = read_config_file(filename)

        if settings_content is None:
            return False

        for key, value in settings_content.items():
            setattr(self, key, value)

        return True


    @staticmethod
    def _normalize_platform_string(in_platform):
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
                          "mac"       : "mac",
                          "macos"     : "mac" }

        if in_platform.lower() in std_platforms:
            return std_platforms[in_platform.lower()]
        else:
            return ""

    def _standardize_configuration(self):
        if not hasattr(self, 'configuration') or self.configuration is None:
            if self.is_ue4:
                self.configuration = 'devel'
            elif self.is_ue3:
                self.configuration = 'release'

        if hasattr(self, 'configuration') and self.configuration is not None:
            std_configs = { 'debug'    : 'debug',
                            'devel'    : 'devel',
                            'release'  : 'release',
                            'test'     : 'test',
                            'shipping' : 'shipping',
                          }

            if self.configuration.lower() in std_configs:
                self.configuration = std_configs[self.configuration.lower()]
            else:
                self.configuration = ""

    def _standardize_platform(self):
        if not hasattr(self, 'platform') or self.platform is None:
            if self.is_ue4 or self.is_ue3:
                if nimp.utilities.system.is_windows():
                    self.platform = 'win64'
                elif platform.system() == 'Darwin':
                    self.platform = 'mac'
                else:
                    self.platform = 'linux'

        if hasattr(self, "platform") and self.platform is not None:
            self.platform = Environment._normalize_platform_string(self.platform)

            self.is_win32 = self.platform == "win32"
            self.is_win64 = self.platform == "win64"
            self.is_ps3   = self.platform == "ps3"
            self.is_ps4   = self.platform == "ps4"
            self.is_x360  = self.platform == "xbox360"
            self.is_xone  = self.platform == "xboxone"
            self.is_linux = self.platform == "linux"
            self.is_mac   = self.platform == "mac"

            self.is_microsoft_platform = self.is_win32 or self.is_win64 or self.is_x360 or self.is_xone
            self.is_sony_platform      = self.is_ps3 or self.is_ps4

            # UE3 stuff
            self.ue3_build_platform =  nimp.utilities.ue3.get_ue3_build_platform(self.platform)
            self.ue3_cook_platform =   nimp.utilities.ue3.get_ue3_cook_platform(self.platform)
            self.ue3_shader_platform = nimp.utilities.ue3.get_ue3_shader_platform(self.platform)

            if hasattr(self, "configuration"):
                self.ue3_build_configuration = nimp.utilities.ue3.get_ue3_build_config(self.configuration)
                self.ue4_build_configuration = nimp.utilities.ue4.get_ue4_build_config(self.configuration)

            cook_cfg = self.configuration if hasattr(self, 'configuration') else None
            cook_suffix = 'Final' if cook_cfg in ['test', 'shipping', None] else ''
            self.ue3_cook_directory = 'Cooked{0}{1}'.format(self.ue3_cook_platform, cook_suffix)

            # UE4 stuff
            self.ue4_build_platform = nimp.utilities.ue4.get_ue4_build_platform(self.platform)
            self.ue4_cook_platform  = nimp.utilities.ue4.get_ue4_cook_platform(self.platform)

            if hasattr(self, 'dlc'):
                if self.dlc is None:
                    self.dlc = 'main'

            if self.is_ue3:
                banks_platforms = { "win32"   : "PC",
                                    "win64"   : "PC",
                                    "xbox360" : "X360",
                                    "xboxone" : "XboxOne",
                                    "ps3"     : "PS3",
                                    "ps4"     : "PS4" }
            else:
                banks_platforms = { "win32"   : "Windows",
                                    "win64"   : "Windows",
                                    "xbox360" : "X360",
                                    "xboxone" : "XboxOne",
                                    "ps3"     : "PS3",
                                    "ps4"     : "PS4" }

            if self.platform in banks_platforms:
                self.wwise_banks_platform = banks_platforms[self.platform]

    def _standardize_target(self):
        if not hasattr(self, 'target') or self.target is None:
            if self.is_ue4:
                if self.platform in ['win64', 'mac', 'linux']:
                    self.target = 'editor'
                else:
                    self.target = 'game'
            elif self.is_ue3:
                if self.platform == 'win64':
                    self.target = 'editor'
                else:
                    self.target = 'game'



    def standardize_names(self):
        ''' Standardize some environment values (ex: Durango -> XboxOne) '''
        # Detect Unreal Engine 3 or Unreal Engine 4
        self.is_ue3 = hasattr(self, 'project_type') and self.project_type is 'UE3'
        self.is_ue4 = hasattr(self, 'project_type') and self.project_type is 'UE4'

        self._standardize_configuration()
        self._standardize_platform()
        self._standardize_target()

    def setup_envvars(self):
        ''' Applies environment variables from .nimp.conf '''
        if hasattr(self, 'environment'):
            for key, val in self.environment.items():
                os.environ[key] = val

    def execute_hook(self, hook_name):
        ''' Executes a hook in the .nimp/hooks directory '''
        pass


#---------------------------------------------------------------------------
def check_keys(dictionary, error_format, *args):
    ''' Checks a key is defined on environment '''
    result = True
    for in_key in args:
        if in_key not in dictionary:
            result = False
    return result

#---------------------------------------------------------------------------
def read_config_file(filename):
    try:
        conf = open(filename, "rb").read()
    except Exception as exception:
        log_error("Unable to open configuration file : {0}", exception)
        return None
    # Parse configuration file
    try:
        locals = {}
        exec(compile(conf, filename, 'exec'), None, locals)
        if "config" in locals:
            return locals["config"]
        log_error("Configuration file {0} has no 'config' section.", filename)
    except Exception as e:
        log_error("Unable to load configuration file {0}: {1}", filename, str(e))
        return None

    return {}

