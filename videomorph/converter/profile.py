# -*- coding: utf-8 -*-
#
# File name: profile.py
#
#   VideoMorph - A PyQt5 frontend to ffmpeg and avconv.
#   Copyright 2016-2017 VideoMorph Development Team

#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""This module contains the PRESETS for encoding different video formats."""

import re
from collections import OrderedDict
from distutils.errors import DistutilsFileError
from distutils.file_util import copy_file
from os import sep
from os.path import expanduser, join, exists, getsize
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from videomorph import LINUX_PATHS
from videomorph import LOCALE
from videomorph import VM_PATHS
from . import VIDEO_FILTERS


class ProfileError(Exception):
    """Base Exception."""
    pass


class ProfileBlankNameError(ProfileError):
    """Exception for Profile Blank Name."""
    pass


class ProfileBlankPresetError(ProfileError):
    """Exception form Profile Blank Preset."""
    pass


class ProfileBlankParamsError(ProfileError):
    """Exception form Profile Blank Params."""
    pass


class ProfileExtensionError(ProfileError):
    """Exception form Profile Extension Error."""
    pass


class _XMLProfile:
    """Class to manage the profiles.xml file."""

    def __init__(self):
        self._xml_root = None

        # Setup the _XMLProfile to be used.
        self.create_xml_profiles_file()
        self.set_xml_root()

    def set_xml_root(self):
        """Set the XML root."""
        self._xml_root = self._get_xml_root()

    def create_xml_profiles_file(self, restore=False):
        """Create a xml file with the conversion profiles."""
        profiles_xml = self._xml_profiles_path

        if not exists(profiles_xml) or not getsize(profiles_xml) or restore:
            if exists(LINUX_PATHS['profiles'] + '/profiles.xml'):
                # if VideoMorph is installed
                copy_file(LINUX_PATHS['profiles'] + '/profiles.xml',
                          profiles_xml)
            else:
                # if not installed
                copy_file('../' + VM_PATHS['profiles'] + '/profiles.xml',
                          profiles_xml)

    def add_xml_profile(self, profile_name, preset, params, extension):
        """Add a conversion profile."""
        if not profile_name:
            raise ProfileBlankNameError

        profile_name = profile_name.upper()

        if not preset:
            raise ProfileBlankPresetError

        if not params:
            raise ProfileBlankParamsError

        if not extension.startswith('.') or extension not in VIDEO_FILTERS:
            raise ProfileExtensionError

        extension = extension.lower()

        xml_profile = ElementTree.Element(profile_name)
        regexp = re.compile(r'[A-z][0-9]?')
        preset_tag = ''.join(regexp.findall(preset))
        xml_preset = ElementTree.Element(preset_tag)
        xml_preset_name = ElementTree.Element('preset_name')
        xml_preset_name.text = preset
        xml_params = ElementTree.Element('preset_params')
        xml_params.text = params
        xml_extension = ElementTree.Element('file_extension')
        xml_extension.text = extension
        xml_preset_name_es = ElementTree.Element('preset_name_es')
        xml_preset_name_es.text = preset

        for i, elem in enumerate([xml_preset_name, xml_params,
                                  xml_extension, xml_preset_name_es]):
            xml_preset.insert(i, elem)

        for i, elem in enumerate(self._xml_root[:]):
            if elem.tag == xml_profile.tag:
                self._xml_root[i].insert(0, xml_preset)
                self._save_xml_tree()
                break
        else:
            xml_profile.insert(0, xml_preset)
            self._xml_root.insert(0, xml_profile)
            self._save_xml_tree()

    def export_xml_profiles(self, dst_dir):
        """Export a file with the conversion profiles."""
        # Raise PermissionError if user don't have write permission
        try:
            copy_file(src=self._xml_profiles_path, dst=dst_dir)
        except DistutilsFileError:
            raise PermissionError

    def import_xml_profiles(self, src_file):
        """Import a conversion profile file."""
        try:
            copy_file(src=src_file, dst=self._xml_profiles_path)
        except DistutilsFileError:
            raise PermissionError

    def get_xml_profile_attr(self, target_quality, attr_name='preset_params'):
        """Return a dict of preset/params."""
        param_map = {'preset_name': 0,
                     'preset_params': 1,
                     'file_extension': 2,
                     'preset_name_es': 3}

        for element in self._xml_root:
            for item in element:
                if (item[0].text == target_quality or
                        item[3].text == target_quality):
                    return item[param_map[attr_name]].text

    def get_xml_profile_qualities(self):
        """Return a list of available Qualities per conversion profile."""
        qualities_per_profile = OrderedDict()
        values = []

        for element in self._xml_root:
            for item in element:
                if LOCALE == 'es_ES':
                    # Create the dict with values in spanish
                    values.append(item[3].text)
                else:
                    # Create the dict with values in english
                    values.append(item[0].text)

            qualities_per_profile[element.tag] = values
            # Reinitialize values
            values = []

        return qualities_per_profile

    def _save_xml_tree(self):
        """Save xml tree."""
        with open(self._xml_profiles_path, 'wb') as xml_file:
            xml_file.write(b'<?xml version="1.0"?>\n')
            ElementTree.ElementTree(self._xml_root).write(xml_file,
                                                          encoding='UTF-8')

    @property
    def _xml_profiles_path(self):
        """Return the path to the profiles file."""
        return join(expanduser("~"), '.videomorph{0}profiles.xml'.format(sep))

    def _get_xml_root(self):
        """Return the profiles.xml root."""
        try:
            tree = ElementTree.parse(self._xml_profiles_path)
        except ParseError:
            self.create_xml_profiles_file(restore=True)
            tree = ElementTree.parse(self._xml_profiles_path)
        return tree.getroot()


class ConversionProfile:
    """Base class for a Video Profile."""

    def __init__(self, prober):
        """Class initializer."""
        self.prober = prober
        self.xml_profile = _XMLProfile()
        self.quality = None
        self.extension = None
        self.params = None

    def __getattr__(self, attr):
        """Delegate to manage the XMLProfile."""
        return getattr(self.xml_profile, attr)

    def update(self, new_quality):
        """Set the target Quality and other parameters needed to get it."""
        self.quality = new_quality
        # Update the params and extension when the target quality change
        self.params = self.xml_profile.get_xml_profile_attr(
            target_quality=self.quality,
            attr_name='preset_params')
        self.extension = self.xml_profile.get_xml_profile_attr(
            target_quality=self.quality,
            attr_name='file_extension')

    @property
    def quality_tag(self):
        """Generate a tag from profile quality string."""
        tag_regex = re.compile(r'[A-Z][0-9]?')
        tag = ''.join(tag_regex.findall(self.quality))

        return '[' + tag + ']'

