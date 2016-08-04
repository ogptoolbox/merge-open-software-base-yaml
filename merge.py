#! /usr/bin/env python3


# merge-open-software-base-yaml -- Merge YAML files describing software
# By: Emmanuel Raviart <emmanuel.raviart@data.gouv.fr>
#
# Copyright (C) 2015, 2016 Etalab
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


def create_dest(dest_dir, source_dir, source_name):
    for source_data_path, source_data in iter_yaml_files(source_dir):
        name = os.path.splitext(os.path.basename(source_data_path))[0]

        specificity_path = os.path.join(args.specificities_dir, '{}.yaml'.format(name))
        if os.path.exists(specificity_path):
            with open(specificity_path) as specificity_file:
                name = yaml.load(specificity_file).get(source_name, {'name': name}).get('name')

        data_path = os.path.join(dest_dir, '{}.yaml'.format(name))

        if not os.path.exists(data_path):
            if not args.yes:
                print("\n")
                print(yaml.dump(source_data))
                msg = 'File for ' + name + ' does not exist. Create it ? '
            if args.yes or input("%s (y/N) " % msg).lower() == 'y':
                with open(data_path, 'w') as new_file:
                    data = {'name': name}
                    yaml.dump(data, new_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)


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
    parser.add_argument('source_name', help='source name (among the ones known by this merge tool)')
    parser.add_argument('source_dir', help='path of source data directory')
    parser.add_argument('target_dir', help='path of target directory for generated YAML files')
    parser.add_argument('-c', '--create', action='store_true', default=False,
        help='by default, the script only add information to existing files. With --create, when a program does not' \
            ' have a file, the user is asked if they want to create the file.')
    parser.add_argument('--specificities-dir', default='./specificities', dest='specificities_dir',
        help='path of directory containing merge particularities in YAML files')
    parser.add_argument('-y', '--yes', action='store_true', default=False, help='dont ask for confirmation on creation')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    if not os.path.exists(args.target_dir):
        os.makedirs(args.target_dir)

    if args.source_name == 'civic-tech-field-guide':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'civic-tech-field-guide')
        merge_source(args.target_dir, args.source_dir, 'civic-tech-field-guide', {
            'name': 'civic-tech-field-guide',
            'url': 'https://git.framasoft.org/codegouv/civic-tech-field-guide-yaml',
            'description': 'http://bit.ly/organizecivictech',
            })

    elif args.source_name == 'civicstack':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'civicstack')
        merge_source(args.target_dir, args.source_dir, 'civicstack', {
            'name': 'civicstack',
            'url': 'https://git.framasoft.org/codegouv/civicstack-yaml',
            'description': 'http://www.civicstack.org/',
            })

    elif args.source_name == 'debian-appstream':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'debian_appstream')
        merge_source(args.target_dir, args.source_dir, 'debian_appstream', {
            'name': 'Debian Appstream',
            'url': 'https://git.framasoft.org/codegouv/appstream-debian-yaml',
            'description': 'https://wiki.debian.org/AppStream',
            })

    elif args.source_name == 'mim':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'mim')
        print('Merging from mim not implemented.')

    elif args.source_name == 'nuit-debout':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'nuit-debout')
        merge_source(args.target_dir, args.source_dir, 'nuit-debout', {
            'name': 'nuit-debout',
            'url': 'https://git.framasoft.org/codegouv/nuit-debout-yaml',
            'description': "https://wiki.nuitdebout.fr/wiki/Ressources/Liste_d'outils_numériques",
            })

    elif args.source_name == 'ogptoolbox-framacalc':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'ogptoolbox-framacalc')
        merge_source(args.target_dir, args.source_dir, 'ogptoolbox-framacalc', {
            'name': 'OGP Toolbox Framacalc',
            'url': 'https://git.framasoft.org/codegouv/ogptoolbox-framacalc-yaml',
            'description': "https://framacalc.org/ogptoolbox",
            })

    elif args.source_name == 'participatedb':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'participatedb')
        merge_source(args.target_dir, args.source_dir, 'participatedb', {
            'name': 'ParticipateDB',
            'url': 'https://git.framasoft.org/codegouv/participatedb-yaml',
            'description': "http://www.participatedb.com/",
            })

    elif args.source_name == 'tech-plateforms':
        if args.create:
            create_dest(args.target_dir, args.source_dir, 'tech-plateforms')
        merge_source(args.target_dir, args.source_dir, 'tech-plateforms', {
            'name': 'Tech Plateforms for Civic Participations',
            'url': 'https://git.framasoft.org/codegouv/tech-plateforms-yaml',
            'description': 'https://docs.google.com/spreadsheets/d/1YBZLdNsGohGBjO5e7yrwOQx78IzCA6SNW6T14p15aKU',
            })

    elif args.source_name == 'udd':
        if args.create:
            print('Creating from Debian UDD not implemented.')
        merge_source(args.target_dir, args.source_dir, 'debian', {
            'name': 'Universal Debian Database',
            'url': 'https://git.framasoft.org/codegouv/udd-yaml',
            'description': 'https://wiki.debian.org/UltimateDebianDatabase',
            }, read_source_data_debian)

    elif args.source_name == 'wikidata':
        if args.create:
            print('Creating from Wikidata not implemented.')
        merge_source(args.target_dir, args.source_dir, 'wikidata', {
            'name': 'Wikidata',
            'url': 'https://git.framasoft.org/codegouv/wikidata-yaml',
            'description': 'http://wikidata.org/',
            })

    else:
        print('No valid sources selected: use --help to get more information.')

    return 0


def merge_source(dest_dir, source_dir, source_name, source_desc, read_source_data=None):
    if read_source_data is None:
        read_source_data = read_source_data_default

    for data_path, data in iter_yaml_files(dest_dir):
        name = data['name']

        # find if there is specific name in this source
        specificity_path = os.path.join(args.specificities_dir, '{}.yaml'.format(name))
        if os.path.exists(specificity_path):
            with open(specificity_path) as specificity_file:
                alt_name = yaml.load(specificity_file).get(source_name, {'name': name}).get('name')
                print('Using ' + alt_name + ' instead of ' + name + ' in source ' + source_name)
                name = alt_name

        source_data = read_source_data(source_dir, name)

        # find source file
        if source_data is not None:
            source_data['_source'] = source_desc
            data[source_name] = source_data
            with open(data_path, 'w') as yaml_file:
                yaml.dump(data, yaml_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)
        else:
            print(name + ' not found in source ' + source_name + ': skipping.')


def read_source_data_debian(source_dir, debian_name):
    apt_pkg.init()

    debian_package_path = os.path.join(
        source_dir,
        'packages',
        debian_name[:4] if debian_name.startswith('lib') else debian_name[0],
        '{}.yaml'.format(debian_name)
    )
    if os.path.exists(debian_package_path):
        with open(debian_package_path) as debian_package_file:
            debian_package = yaml.load(debian_package_file)
    else:
        debian_package = None

    debian_source_path = os.path.join(
        source_dir,
        'sources',
        debian_name[:4] if debian_name.startswith('lib') else debian_name[0],
        '{}.yaml'.format(debian_name)
    )
    if os.path.exists(debian_source_path):
        with open(debian_source_path) as debian_source_file:
            debian_source = yaml.load(debian_source_file)
    else:
        debian_source = None

    if debian_package is None and debian_source is None:
        debian = None
    else:
        debian = collections.OrderedDict()
        debian['name'] = debian_name

        if debian_package is not None:
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
                debian['description'] = descriptions_by_architecture.get('all') or \
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
                debian['screenshot'] = collections.OrderedDict([
                    ('large_image_url', screenshot['large_image_url']),
                    ('screenshot_url', screenshot['screenshot_url']),
                    ('small_image_url', screenshot['small_image_url']),
                ])

        if debian_source is not None:
            security_issues = debian_source.get('security_issues')
            if security_issues:
                debian['security_issues'] = security_issues

    if debian:
        return debian

    return None


def read_source_data_default(source_dir, name):
    source_path = os.path.join(source_dir, '{}.yaml'.format(name))
    source_path_alt = os.path.join(source_dir, name[0], '{}.yaml'.format(name))

    if os.path.exists(source_path):
        with open(source_path) as source_file:
            return yaml.load(source_file)
    elif os.path.exists(source_path_alt):
        with open(source_path_alt) as source_file:
            return yaml.load(source_file)
    else:
        return None


if __name__ == "__main__":
    sys.exit(main())
