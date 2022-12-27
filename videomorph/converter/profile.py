# -*- coding: utf-8 -*-
#
# File name: profile.py
#
#   VideoMorph - A PyQt6 frontend to ffmpeg.
#   Copyright 2016-2018 VideoMorph Development Team

#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""This module provides the Profile class."""

import re
from collections import OrderedDict
from shutil import copy2
from os import makedirs
from os.path import exists, getsize
from os.path import getmtime
from os.path import join as join_path
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from . import BASE_DIR
from . import SYS_PATHS
from . import VM_PATHS
from . import VALID_VIDEO_EXT
from . import XML_FILES
from .exceptions import ProfileBlankNameError
from .exceptions import ProfileBlankParamsError
from .exceptions import ProfileBlankPresetError
from .exceptions import ProfileExtensionError


class Profile:
    """Base class for a Conversion Profile."""

    def __init__(self):
        """Class initializer."""
        self._xml_profile = _XMLProfile(xml_files=XML_FILES)
        self._quality = None
        self.extension = None
        self.params = None

    def __getattr__(self, attr):
        """Delegate to manage the _XMLProfile object."""
        return getattr(self._xml_profile, attr)

    def update(self, new_quality):
        """Set the target Quality and other parameters needed to get it."""
        self._quality = new_quality
        # Update the params and extension when the target quality change
        self.params = self._xml_profile.get_xml_profile_attr(
            target_quality=self._quality,
            attr_name='preset_params')
        self.extension = self._xml_profile.get_xml_profile_attr(
            target_quality=self._quality,
            attr_name='file_extension')

    @property
    def quality_tag(self):
        """Generate a tag from profile quality string."""
        tag_regex = re.compile(r'[A-Z][0-9]?')
        tag = ''.join(tag_regex.findall(self._quality))

        if not tag:
            tag = ''.join(word[0] for word in self._quality.split()).upper()

        return '[' + tag + ']-'


class _XMLProfile:
    """Class to manage the xml profiles file."""

    def __init__(self, xml_files):
        """Class initializer."""
        # Create xml files.
        self._xml_files = xml_files
        self._create_xml_files()

    def restore_default_profiles(self):
        """Restore default profiles."""
        self._copy_xml_file(file_name=self._xml_files.customized)

    def add_xml_profile(self, profile_name, preset, params, extension):
        """Add a conversion profile."""
        if not profile_name:
            raise ProfileBlankNameError

        profile_name = profile_name.upper()

        if not preset:
            raise ProfileBlankPresetError

        if not params:
            raise ProfileBlankParamsError

        if not extension.startswith('.') or extension not in VALID_VIDEO_EXT:
            raise ProfileExtensionError('Invalid video file extension')

        extension = extension.lower()

        xml_profile = ElementTree.Element(profile_name)

        xml_preset = self._create_xml_preset(preset, params, extension)

        self._insert_xml_elements(xml_profile=xml_profile,
                                  xml_preset=xml_preset,
                                  xml_root=self._get_xml_root(
                                      self._xml_files.customized))

    def export_xml_profiles(self, dst_dir):
        """Export a file with the conversion profiles."""
        # Raise PermissionError if user doesn't have write permission
        try:
            copy2(src=self._user_xml_file_path(
                file_name=self._xml_files.customized),
                  dst=dst_dir)
        except OSError:
            raise PermissionError

    def import_xml_profiles(self, src_file):
        """Import a conversion profile file."""
        try:
            dst_directory = self._user_xml_file_path(
                self._xml_files.customized)
            copy2(src=src_file, dst=dst_directory)
        except OSError:
            raise PermissionError

    def get_xml_profile_attr(self, target_quality, attr_name='preset_params'):
        """Return a param of Profile."""
        param_map = {'preset_name': 0,
                     'preset_params': 1,
                     'file_extension': 2,
                     'preset_name_es': 3}

        for xml_file in self._xml_files:
            for element in self._get_xml_root(xml_file_name=xml_file):
                for item in element:
                    if (item[0].text == target_quality or
                            item[3].text == target_quality):
                        return item[param_map[attr_name]].text

        raise ValueError('Wrong quality or param.')

    def get_xml_profile_qualities(self, locale):
        """Return a list of available Qualities per conversion profile."""
        qualities_per_profile = OrderedDict()

        for xml_file in self._xml_files:
            for element in self._get_xml_root(xml_file):
                qualities = self._get_qualities(element, locale)
                if element.tag not in qualities_per_profile:
                    qualities_per_profile[element.tag] = qualities
                else:
                    qualities_per_profile[element.tag] += qualities

        return qualities_per_profile

    @staticmethod
    def _get_qualities(element, locale):
        qualities = []
        for item in element:
            if locale == 'es_ES':
                qualities.append(item[3].text)
            else:
                qualities.append(item[0].text)
        return qualities

    def _user_xml_file_path(self, file_name):
        """Return the path to the profiles file."""
        return join_path(self._user_xml_files_directory(), file_name)

    def _insert_xml_elements(self, xml_profile, xml_preset, xml_root):
        """Insert an xml element into an xml root."""
        for i, elem in enumerate(xml_root[:]):
            if elem.tag == xml_profile.tag:
                xml_root[i].insert(0, xml_preset)
                self._save_xml_tree(xml_tree=xml_root)
                break
        else:
            xml_profile.insert(0, xml_preset)
            xml_root.insert(0, xml_profile)
            self._save_xml_tree(xml_tree=xml_root)

    def _save_xml_tree(self, xml_tree):
        """Save the xml tree."""
        xml_profiles_path = self._user_xml_file_path(
            self._xml_files.customized)

        with open(xml_profiles_path, 'wb') as xml_file:
            ElementTree.ElementTree(xml_tree).write(xml_file,
                                                    xml_declaration=True,
                                                    encoding='UTF-8')

    def _create_xml_files(self):
        """Create a xml file with the conversion profiles."""
        makedirs(self._user_xml_files_directory(), exist_ok=True)

        for xml_file in self._xml_files:
            if not self._xml_file_is_correct(xml_file):
                self._copy_xml_file(file_name=xml_file)

    def _copy_xml_file(self, file_name):
        """Copy profiles xml file."""
        xml_file_sys_path = self._sys_xml_file_path(file_name)
        xml_file_user_path = self._user_xml_file_path(file_name)

        copy2(src=xml_file_sys_path, dst=xml_file_user_path)

    def _xml_file_is_correct(self, file_name):
        """Validate xml files in user config directory."""
        xml_file_user_path = self._user_xml_file_path(file_name)
        xml_file_sys_path = self._sys_xml_file_path(file_name)

        if not exists(xml_file_user_path) or not getsize(xml_file_user_path):
            return False

        if getmtime(xml_file_sys_path) > getmtime(xml_file_user_path):
            return False

        return True

    def _get_xml_root(self, xml_file_name):
        """Return the xml root."""
        path = self._user_xml_file_path(file_name=xml_file_name)
        try:
            tree = ElementTree.parse(path)
        except ParseError:
            self.restore_default_profiles()
            tree = ElementTree.parse(path)
        return tree.getroot()

    @staticmethod
    def _user_xml_files_directory():
        """Return the user xml directory path."""
        return join_path(SYS_PATHS.config, 'profiles')

    @staticmethod
    def _sys_xml_file_path(file_name):
        """Return the path to xml profiles file in the system."""
        file_path = join_path(SYS_PATHS.profiles, file_name)
        if exists(file_path):
            # if VideoMorph is installed
            return file_path

        # if not installed
        return join_path(BASE_DIR, VM_PATHS.profiles, file_name)

    @staticmethod
    def _create_xml_preset(preset, params, extension):
        """Return a xml preset."""
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

        return xml_preset
