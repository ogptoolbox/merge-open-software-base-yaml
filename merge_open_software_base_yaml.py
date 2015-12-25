#! /usr/bin/env python3


# merge-open-software-base-yaml -- Merge YAML files describing software
# By: Emmanuel Raviart <emmanuel.raviart@data.gouv.fr>
#
# Copyright (C) 2015 Etalab
# https::#git.framasoft.org/etalab/merge-open-software-base-yaml
#
# merge-open-software-base-yaml is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# merge-open-software-base-yaml is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http:>www.gnu.org/licenses/>.


import argparse
import collections
import logging
import os
import sys

import apt_pkg
import yaml


# YAML configuration


class folded_str(str):
    pass


class literal_str(str):
    pass


def dict_constructor(loader, node):
    return collections.OrderedDict(loader.construct_pairs(node))


def dict_representer(dumper, data):
    return dumper.represent_dict(sorted(data.items()))


yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, dict_constructor)

yaml.add_representer(folded_str, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str',
    data, style='>'))
yaml.add_representer(literal_str, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str',
    data, style='|'))
yaml.add_representer(collections.OrderedDict, dict_representer)
yaml.add_representer(str, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str', data))


#


app_name = os.path.splitext(os.path.basename(__file__))[0]
args = None
debian_stable_release_name = 'jessie'
log = logging.getLogger(app_name)


def extract_latest_debian_screenshot(*screenshots):
    latest_number = -1
    latest_screenshot = None
    for screenshot in screenshots:
        if screenshot is None:
            continue
        number = int(screenshot['large_image_url'].rsplit('/', 1)[-1].split('_', 1)[0])
        if number > latest_number:
            latest_number = number
            latest_screenshot = screenshot
    return latest_screenshot


def iter_yaml_files(dir):
    assert os.path.exists(dir), "Directory doesn't exist: {}".format(dir)
    for sub_dir, dirs_name, filenames in os.walk(dir):
        for dir_name in dirs_name[:]:
            if dir_name.startswith('.'):
                dirs_name.remove(dir_name)
        for filename in filenames:
            if not filename.endswith(".yaml"):
                continue
            yaml_file_path = os.path.join(sub_dir, filename)
            with open(yaml_file_path) as yaml_file:
                yield yaml_file_path, yaml.load(yaml_file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mim_dir',
        help = 'path of source directory containing YAML files extracted from MIMx')
    parser.add_argument('specificities_dir',
        help = 'path of directory containing merge particularities in YAML files')
    parser.add_argument('udd_dir',
        help = 'path of source directory containing YAML files extracted from Universal Debian Database (UDD)')
    parser.add_argument('target_dir', help = 'path of target directory for generated YAML files')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    global args
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    if not os.path.exists(args.target_dir):
        os.makedirs(args.target_dir)

    apt_pkg.init()

    # name_by_debian_name = {}
    name_by_mim_name = {}
    specificity_by_name = {}
    for data_path, data in iter_yaml_files(args.specificities_dir):
        name = os.path.splitext(os.path.basename(data_path))[0]
        specificity_by_name[name] = data
        # debian_name = data.get('debian', {}).get('name')
        # if debian_name is not None:
        #     name_by_debian_name[debian_name] = name
        mim_name = data.get('mim', {}).get('name')
        if mim_name is not None:
            name_by_mim_name[mim_name] = name

    for mim_data_path, mim_data in iter_yaml_files(args.mim_dir):
        mim_name = os.path.splitext(os.path.basename(mim_data_path))[0]
        name = name_by_mim_name.get(mim_name, mim_name)
        specificity = specificity_by_name.get(name) or {}
        debian_specificity = specificity.get('debian', {})
        if debian_specificity is None:
            continue
        debian_name = debian_specificity.get('name', name)
        debian_package_path = os.path.join(
            args.udd_dir,
            'packages',
            debian_name[:4] if debian_name.startswith('lib') else debian_name[0],
            '{}.yaml'.format(debian_name)
            )
        if not os.path.exists(debian_package_path):
            continue
        with open(debian_package_path) as debian_package:
            debian_package = yaml.load(debian_package)

        debian_data = collections.OrderedDict()
        if debian_name != name:
            debian_data['name'] = debian_name

        descriptions_by_architecture = {}
        release_by_name = debian_package.get('releases', {})
        release = release_by_name.get(debian_stable_release_name)
        releases = release_by_name.values() if release is None else [release]
        for release in releases:
            for component in release.values():
                versions = component.get('versions')
                if versions is None:
                    continue
                latest_version_str = None
                for version_str in versions:
                    if latest_version_str is None or apt_pkg.version_compare(latest_version_str, version_str) < 0:
                        latest_version_str = version_str
                version = versions[latest_version_str]
                for architecture, package in version.get('architectures', {}).items():
                    description_md5 = package['description_md5']
                    descriptions = component.get('descriptions', {}).get(description_md5)
                    if descriptions is not None:
                        descriptions_by_architecture[architecture] = descriptions
        assert descriptions_by_architecture, debian_name
        if descriptions_by_architecture:
            debian_data['description'] = descriptions_by_architecture.get('all') or \
                descriptions_by_architecture.get('amd64') or list(descriptions_by_architecture.values())[0]

        screenshots = debian_package.get('screenshots')
        screenshot = extract_latest_debian_screenshot(*screenshots) if screenshots is not None else None
        versions = debian_package.get('versions')
        if versions is not None:
            for version in versions.values():
                screenshots = version.get('screenshots')
                if screenshots is not None:
                    screenshot = extract_latest_debian_screenshot(screenshot, *screenshots)
        if screenshot:
            debian_data['screenshot'] = collections.OrderedDict([
                ('large_image_url', screenshot['large_image_url']),
                ('screenshot_url', screenshot['screenshot_url']),
                ('small_image_url', screenshot['small_image_url']),
                ])

        data = collections.OrderedDict([
            ('name', name),
            ])
        if debian_data:
            data['debian'] = debian_data

        with open(os.path.join(args.target_dir, '{}.yaml'.format(name)), 'w') as yaml_file:
            yaml.dump(data, yaml_file, allow_unicode = True, default_flow_style = False, indent = 2, width = 120)

    return 0


if __name__ == "__main__":
    sys.exit(main())
