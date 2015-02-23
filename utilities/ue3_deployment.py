# -*- coding: utf-8 -*-

from utilities.deployment import *
from utilities.ue3        import *


#---------------------------------------------------------------------------
def ue3_publish_binaries(publisher):
    platform      = get_binaries_platform(publisher.platform)
    configuration = publisher.configuration

    if (platform == 'Win32' or platform == 'Win64'):
        if configuration == 'Release' or configuration is None:
            publisher.add("Binaries\\{platform}\\{game}.exe")
            publisher.add("Binaries\\{platform}\\{game}.exe.config")
            publisher.add("Binaries\\{platform}\\{game}.config")
            publisher.add("Binaries\\{platform}\\{game}.com")
            publisher.add("Binaries\\Xbox360\\Interop.XDevkit.1.0.dll")
            publisher.add("Binaries\\PS3\\PS3Tools_x64.dll")
            publisher.add("Binaries\\Xbox360\\Xbox360Tools_x64.dll")
            publisher.add("Binaries\\Orbis\\OrbisTools_x64.dll")
            publisher.add("Binaries\\Dingo\\DingoTools_x64.dll")

            publisher.add("Binaries\\Win64\\Microsoft.VC90.CRT", ['*.*'])
            publisher.add("Binaries\\{platform}", ['*.dll'], recursive = False )
            publisher.add("Binaries\\", ['*.xml', '*.bat', '*.dll', '*.exe.config', '*.exe'], recursive = False)
            publisher.add("Binaries\\Win64\\Editor\\Release", ['*.*'], recursive = False)
            publisher.add("Binaries\\{platform}", ['{game}.*'], ['*.pdb', '*.map', '*.lib'], recursive = False)

        if configuration != 'Release':
            publisher.add("Binaries\\{platform}\\", ['{game}-{platform}-{configuration}.*'], ['*.pdb', '*.map', '*.lib'])

    if (platform != 'Win32' and platform != 'Win64'):
        if configuration is None:
            publisher.add("Binaries\\{platform}\\", ['{game}*-*.*'], ['*.pdb', '*.map', '*.lib'])
        else:
            publisher.add("Binaries\\{platform}\\", ['{game}-{platform}-{configuration}.*'], ['*.pdb', '*.map', '*.lib'])

    return True

#---------------------------------------------------------------------------
def ue3_publish_version(publisher):
    for configuration in publisher.configurations:
        if not publish(publisher,
                       ue3_publish_binaries,
                       publisher.destination,
                       platform      = get_binaries_platform(publisher.platform),
                       configuration = configuration):
            return False

    if publisher.platform.lower() == 'win64':
        publisher.add("{game}\\Script\\", ['*.*'])
        publisher.add("{game}\\ScriptFinalRelease\\", ['*.*'])

    return True

#---------------------------------------------------------------------------
def ue3_publish_patch(publisher):
    if not publish(publisher, ue3_publish_binaries, publisher.destination, configuration = 'Test'):
        return False

    if not publish(publisher, ue3_publish_binaries, publisher.destination, configuration = 'Final'):
        return False

    if not publish(publisher, ue3_publish_cook, publisher.destination, configuration = "Final"):
        return False

    return True

#---------------------------------------------------------------------------
def ue3_publish_cook(publisher):
    cook_directory = get_cook_directory(publisher.project, publisher.dlc, publisher.platform, publisher.configuration)
    publisher.add(cook_directory)

    return True
