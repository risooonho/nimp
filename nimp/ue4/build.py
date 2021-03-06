# -*- coding: utf-8 -*-
# Copyright © 2014—2016 Dontnod Entertainment

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

import logging
import os
import platform
import re
from pathlib import Path

import nimp.build
import nimp.system
import nimp.sys.platform
import nimp.sys.process
import nimp.summary
import nimp.unreal

def build(env):
    ''' Builds an Unreal Engine Project. config and platform arguments should
        be set on environment in order to call this function. You can use
        `nimp.environment.add_arguments` and `nimp.build.add_arguments` to do
        so.'''
    if not nimp.unreal._check_for_unreal(env):
        return False

    assert hasattr(env, 'ue4_config')
    assert env.ue4_config is not None

    if env.disable_unity:
        os.environ['UBT_bUseUnityBuild'] = 'false'

    if env.fastbuild:
        os.environ['UBT_bAllowFastBuild'] = 'true'
        os.environ['UBT_bUseUnityBuild'] = 'false'

    # Pre-reboot run prebuild *BEFORE* GenerateProjectFiles.bat
    if env.is_dne_legacy_ue4:
        nimp.environment.execute_hook('prebuild', env)

    # Bootstrap if necessary
    if hasattr(env, 'bootstrap') and env.bootstrap:
        # Now generate project files
        if _ue4_generate_project(env) != 0:
            logging.error("Error generating UE4 project files")
            return False

    # Pre-reboot run prebuild *AFTER* GenerateProjectFiles.bat
    if not env.is_dne_legacy_ue4:
        nimp.environment.execute_hook('prebuild', env)

    # The main solution file
    solution = env.format('{ue4_dir}/UE4.sln')

    # Decide which VS version to use
    if hasattr(env, 'vs_version') and env.vs_version:
        vs_version = env.vs_version
    else:
        # Default to VS 2015.
        vs_version = '14'
        try:
            for line in open(solution):
                if 'MinimumVisualStudioVersion = 15' in line:
                    vs_version = '15'
                    break
        except IOError:
            pass

    # Build tools that all targets require
    if not _ue4_build_common_tools(env, solution=solution, vs_version=vs_version):
        return False

    if env.target == 'tools':
        if not _ue4_build_extra_tools(env, solution=solution, vs_version=vs_version):
            return False

    if env.target == 'game':
        if not _ue4_build_game(env, solution=solution, vs_version=vs_version):
            return False

    if env.target == 'editor':
        if not _ue4_build_editor(env, solution=solution, vs_version=vs_version):
            return False

    nimp.environment.execute_hook('postbuild', env)

    return True

### UAT + UBT helpers

def _ue4_vsversion_to_ubt(vs_version):
    if vs_version == '14' or vs_version == '2015':
        return ['-2015']
    elif vs_version == '15' or vs_version == '2017':
        return ['-2017']
    elif vs_version == '16' or vs_version == '2019':
        return ['-2019']
    else:
        return []


def _ue4_generate_project(env):
    # Check for prerequisites
    if env.is_dne_legacy_ue4:
        has_prereq = os.path.exists(env.format('{ue4_dir}/Engine/Binaries/DotNET/RPCUtility.exe'))
        if not has_prereq:
            if nimp.sys.platform.is_windows():
                command = ['cmd', '/c', 'Setup.bat', '<nul']
            else:
                command = ['/bin/sh', './Setup.sh']
            if not nimp.sys.process.call(command, cwd=env.ue4_dir):
                return False
    else:
        # We do not use GitDependencies.exe but the build scripts depend on its
        # successful run, so create this .ue4dependencies file instead.
        Path(env.format('{ue4_dir}/.ue4dependencies')).touch()
        logging.debug("Skipping prereq for the reboot (already done by GenerateProjectFiles)")

    # Generate project files
    if nimp.sys.platform.is_windows():
        command = ['cmd', '/c', 'GenerateProjectFiles.bat', '<nul']
        if hasattr(env, 'vs_version'):
            command += _ue4_vsversion_to_ubt(env.vs_version)
    else:
        command = ['/bin/sh', './GenerateProjectFiles.sh']

    return nimp.sys.process.call(command, cwd=env.ue4_dir)


def _ue4_run_ubt(env, target, build_platform, build_configuration, vs_version=None, flags=None):
    if nimp.sys.platform.is_windows():
        command = ['cmd', '/c', 'Engine\\Build\\BatchFiles\\Build.bat']
        command += _ue4_vsversion_to_ubt(vs_version)
    else:
        command = ['/bin/bash', './Engine/Build/BatchFiles/%s/Build.sh' % env.ue4_host_platform]

    command += [ target, build_platform, build_configuration ]

    if flags is not None:
        command += flags

    return nimp.sys.process.call(command, cwd=env.ue4_dir) == 0


def _ue4_run_uat(env, target, build_platforms, flags=None):
    if nimp.sys.platform.is_windows():
        command = ['cmd', '/c', 'Engine\\Build\\BatchFiles\\RunUAT.bat']
    else:
        command = ['/bin/bash', './RunUAT.sh']

    if build_platforms is not str:
        build_platforms = '+'.join(build_platforms)

    command += [ target, '-platforms=' + build_platforms ]

    if flags is not None:
        command += flags

    return nimp.sys.process.call(command, cwd=env.ue4_dir) == 0


### Targets

def _ue4_build_game(env, solution, vs_version):
    if env.is_dne_legacy_ue4:
        return _ue4_build_game_legacy(env, solution, vs_version)

    game = env.game if hasattr(env, 'game') else 'UE4'
    if not _ue4_run_ubt(env, game, env.ue4_platform, env.ue4_config, vs_version=vs_version):
        logging.error("Could not build game project")
        return False

    return True

def _ue4_build_editor(env, solution, vs_version):
    if env.is_dne_legacy_ue4:
        return _ue4_build_editor_legacy(env, solution, vs_version)

    game = env.game if hasattr(env, 'game') else 'UE4'
    if not _ue4_run_ubt(env, game + 'Editor', env.ue4_platform, env.ue4_config, vs_version=vs_version):
        logging.error("Could not build editor project")
        return False

    return True

def _ue4_build_common_tools(env, solution, vs_version):
    if env.is_dne_legacy_ue4:
        return _ue4_build_common_tools_legacy(env, solution, vs_version)

    return _ue4_run_ubt(env, 'UnrealHeaderTool', env.ue4_host_platform, 'Development', vs_version)

def _ue4_build_extra_tools(env, solution, vs_version):
    if env.is_dne_legacy_ue4:
        return _ue4_build_extra_tools_legacy(env, solution, vs_version)

    uat_platforms = [ env.ue4_platform ]
    need_ps4tools = ( env.platform == 'ps4' )

    # also compile console tools on Win64
    if nimp.sys.platform.is_windows():
        uat_platforms += [ 'XboxOne' ] # + [ 'PS4' ]
        need_ps4tools = True

    # UAT has a special target to build common tools
    if not _ue4_run_uat(env, 'BuildCommonTools', uat_platforms):
        logging.error("BuildCommonTools failed")
        return False

    # CrashReportClient is not built in Shipping by default, however this is required by the staging process
    if not _ue4_run_ubt(env, 'CrashReportClient', env.ue4_host_platform, 'Shipping', vs_version=vs_version):
        logging.error("Could not build CrashReportClient")
        return False

    # these are not builded by Epic by default
    extra_tools = [
        'LiveCodingConsole',
        'MinidumpDiagnostics',
        'UnrealFileServer',
        'UnrealFrontend',
        'SymbolDebugger'
    ]

    # build projects are currently broken for PS4SymbolTool and BuildCommonTools.Automation.cs (4.22)
    if need_ps4tools:
        # extra_tools.append('PS4MapFileUtil') # removed in 4.22
        _ue4_build_ps4_tools_workaround(env, solution, vs_version)

    # this is DNE specific
    if os.path.exists(nimp.system.sanitize_path(env.format('{ue4_dir}/Game/Tools/DNEAssetRegistryQuery/DNEAssetRegistryQuery.Build.cs'))):
        extra_tools.append('DNEAssetRegistryQuery')

    # use UBT for remaining extra tool targets
    for tool in extra_tools:
        if (not _ue4_run_ubt(env, tool, env.ue4_host_platform, 'Development', vs_version=vs_version)):
            logging.error("Could not build %s", tool)
            return False

    return True

def _ue4_build_ps4_tools_workaround(env, solution, vs_version):
    csproj = env.format('{ue4_dir}/Engine/Source/Programs/PS4/PS4DevKitUtil/PS4DevKitUtil.csproj')
    if not nimp.build.msbuild(csproj, 'AnyCPU', 'Development', vs_version=vs_version):
        logging.error("Could not build PS4DevKitUtil")
        return False

    csproj = env.format('{ue4_dir}/Engine/Source/Programs/PS4/PS4SymbolTool/PS4SymbolTool.csproj')
    if not nimp.build.msbuild(csproj, None, None, vs_version=vs_version):
        logging.error("Could not build PS4SymbolTool")
        return False

    return True

### LEGACY (now using UAT+UBT since 4.22/reboot)

def _ue4_build_project(env, sln_file, project, build_platform,
                       configuration, vs_version, target = 'Rebuild'):

    if nimp.sys.platform.is_windows():
        return nimp.build.vsbuild(sln_file, build_platform, configuration,
                                  project=project,
                                  vs_version=vs_version,
                                  target=target)

    # This file uses bash explicitly
    return nimp.sys.process.call(['/bin/bash', './Engine/Build/BatchFiles/%s/Build.sh' % (env.ue4_host_platform),
                                  project, build_platform, configuration],
                                  cwd=env.ue4_dir) == 0

def _ue4_build_game_legacy(env, solution, vs_version):
    if not _ue4_build_project(env, solution, env.game, env.ue4_platform,
                            env.ue4_config, vs_version, 'Build'):
        logging.error("Could not build game project")
        return False

    return True

def _ue4_build_editor_legacy(env, solution, vs_version):
    game = env.game if hasattr(env, 'game') else 'UE4'
    if env.platform in ['linux', 'mac']:
        project = game + 'Editor'
        config = env.ue4_config
    else:
        project = game
        config = env.ue4_config + ' Editor'

    if not _ue4_build_project(env, solution, project, env.ue4_platform,
                            config, vs_version, 'Build'):
        logging.error("Could not build editor project")
        return False

    return True

def _ue4_build_common_tools_legacy(env, solution, vs_version):
    need_shipping = ['CrashReportClient', 'UnrealCEFSubProcess']
    for tool in _ue4_list_common_tools_legacy(env):
        if not _ue4_build_project(env, solution, tool,
                                  env.ue4_host_platform,
                                  'Shipping' if tool in need_shipping else 'Development',
                                  vs_version, 'Build'):
            logging.error("Could not build %s", tool)
            return False
    return True

def _ue4_build_extra_tools_legacy(env, solution, vs_version):
    # This moved from 'AnyCPU' to 'x64' in UE4.20.
    sln = env.format('{ue4_dir}/Engine/Source/Programs/NetworkProfiler/NetworkProfiler.sln')
    if not nimp.build.vsbuild(sln, 'Any CPU', 'Development',
                              vs_version=vs_version, target='Build') and \
       not nimp.build.vsbuild(sln, 'x64', 'Development',
                              vs_version=vs_version, target='Build'):
        logging.error("Could not build NetworkProfiler")
        return False

    if env.platform != 'win64':
        # On Windows this is part of the main .sln, but not on Linux…
        if not nimp.build.vsbuild(env.format('{ue4_dir}/Engine/Source/Programs/AutomationTool/AutomationTool_Mono.sln'),
                                  'Any CPU', 'Development',
                                  vs_version=vs_version,
                                  target='Build'):
            logging.error("Could not build AutomationTool")
            return False

    if env.platform != 'mac':

        # This also builds AgentInterface.dll, needed by SwarmInterface.sln
        # This used to compile on Linux but hasn't been revisited for a while
        sln1 = env.format('{ue4_dir}/Engine/Source/Programs/UnrealSwarm/UnrealSwarm.sln')
        sln2 = env.format('{ue4_dir}/Engine/Source/Programs/UnrealSwarm/SwarmAgent.sln')
        if not nimp.build.vsbuild(sln1, 'Any CPU', 'Development',
                                  vs_version=vs_version, target='Build') and \
           not nimp.build.vsbuild(sln2, 'Any CPU', 'Development',
                                  vs_version=vs_version, target='Build'):
            logging.error("Could not build UnrealSwarm")
            return False

    # These tools seem to be Windows only for now
    if env.platform == 'win64':
        if not nimp.build.vsbuild(env.format('{ue4_dir}/Engine/Source/Editor/SwarmInterface/DotNET/SwarmInterface.sln'),
                                  'Any CPU', 'Development',
                                  vs_version=vs_version,
                                  target='Build'):
            logging.error("Could not build SwarmInterface")
            return False

        if not _ue4_build_project(env, solution, 'BootstrapPackagedGame',
                                  'Win64', 'Shipping', vs_version, 'Build'):
            logging.error("Could not build BootstrapPackagedGame")
            return False

        tmp = env.format('{ue4_dir}/Engine/Source/Programs/XboxOne/XboxOnePackageNameUtil/XboxOnePackageNameUtil.sln')
        if os.path.exists(nimp.system.sanitize_path(tmp)):
            if not nimp.build.vsbuild(tmp, 'x64', 'Development',
                                      vs_version=vs_version,
                                      target='Build'):
                logging.error("Could not build XboxOnePackageNameUtil")
                return False

    return True

def _ue4_list_common_tools_legacy(env):
    # List of tools to build
    tools = [ 'UnrealHeaderTool' ]

    # Some tools are necessary even when not building tools...
    need_ps4devkitutil = False
    need_ps4mapfileutil = env.platform == 'ps4'
    need_ps4symboltool = env.platform == 'ps4'
    need_xboxonepdbfileutil = env.platform == 'xboxone'

    if env.target == 'tools':

        tools += [ 'UnrealFrontend',
                   'UnrealFileServer',
                   'ShaderCompileWorker',
                   'UnrealPak',
                   'CrashReportClient' ]

        if env.platform != 'mac':
            tools += [ 'UnrealLightmass', ] # doesn’t build (yet?)

        # No longer needed in UE 4.16
        if env.platform == 'linux' and env.ue4_minor < 16:
            tools += [ 'CrossCompilerTool', ]

        if os.path.exists(nimp.system.sanitize_path(env.format('{ue4_dir}/Engine/Source/Programs/DNEAssetRegistryQuery/DNEAssetRegistryQuery.Build.cs'))):
            tools += [ 'DNEAssetRegistryQuery', ]

        if env.platform == 'win64':
            tools += [ 'DotNETUtilities',
                       'AutomationTool',
                       'UnrealCEFSubProcess',
                       'SymbolDebugger' ]
            need_ps4devkitutil = True
            need_ps4mapfileutil = True
            need_ps4symboltool = True
            need_xboxonepdbfileutil = True

    # Some tools are necessary even when not building tools...
    if need_ps4devkitutil and os.path.exists(nimp.system.sanitize_path(env.format('{ue4_dir}/Engine/Source/Programs/PS4/PS4DevKitUtil/PS4DevKitUtil.csproj'))):
        tools += [ 'PS4DevKitUtil' ]

    if need_ps4mapfileutil and os.path.exists(nimp.system.sanitize_path(env.format('{ue4_dir}/Engine/Source/Programs/PS4/PS4MapFileUtil/PS4MapFileUtil.Build.cs'))):
        tools += [ 'PS4MapFileUtil' ]

    if need_ps4symboltool and os.path.exists(nimp.system.sanitize_path(env.format('{ue4_dir}/Engine/Source/Programs/PS4/PS4SymbolTool/PS4SymbolTool.csproj'))):
        tools += [ 'PS4SymbolTool' ]

    if need_xboxonepdbfileutil and os.path.exists(nimp.system.sanitize_path(env.format('{ue4_dir}/Engine/Source/Programs/XboxOne/XboxOnePDBFileUtil/XboxOnePDBFileUtil.Build.cs'))):
        tools += [ 'XboxOnePDBFileUtil' ]

    return tools

