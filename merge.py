#! /usr/bin/env python3


# merge-open-software-base-yaml -- Merge YAML files describing software
# By: Emmanuel Raviart <emmanuel.raviart@data.gouv.fr>
#
# Copyright (C) 2015, 2016 Etalab
# https://git.framasoft.org/codegouv/merge-open-software-base-yaml
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


# YAML directories iterators


def iter_udd_yaml_dir(dir, canonical_name_by_name, entity_by_canonical_name, update_only):
    assert os.path.exists(dir), "Directory doesn't exist: {}".format(dir)

    apt_pkg.init()

    tools_name = set()
    for part in ('packages', 'sources'):
        for sub_dir, dirs_name, filenames in os.walk(os.path.join(dir, part)):
            for dir_name in dirs_name[:]:
                if dir_name.startswith('.'):
                    dirs_name.remove(dir_name)
            for filename in filenames:
                if not filename.endswith(".yaml"):
                    continue
                name = os.path.splitext(filename)[0]
                tools_name.add(name)

    for name in tools_name:
        canonical_name = canonical_name_by_name.get(name, name)
        entity = entity_by_canonical_name.get(canonical_name)
        if entity is None and update_only:
            continue

        package_path = os.path.join(
            dir,
            'packages',
            name[:4] if name.startswith('lib') else name[0],
            '{}.yaml'.format(name),
            )
        if os.path.exists(package_path):
            with open(package_path) as package_file:
                package = yaml.load(package_file)
        else:
            package = None

        source_path = os.path.join(
            dir,
            'sources',
            name[:4] if name.startswith('lib') else name[0],
            '{}.yaml'.format(name)
            )
        if os.path.exists(source_path):
            with open(source_path) as source_file:
                source = yaml.load(source_file)
        else:
            source = None

        debian = collections.OrderedDict()
        debian['name'] = name
        if package is not None:
            descriptions_by_architecture = {}
            release_by_name = package.get('releases', {})
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
            if descriptions_by_architecture:
                debian['description'] = descriptions_by_architecture.get('all') or \
                    descriptions_by_architecture.get('amd64') or list(descriptions_by_architecture.values())[0]

            screenshots = package.get('screenshots')
            screenshot = extract_latest_debian_screenshot(*screenshots) if screenshots is not None else None
            versions = package.get('versions')
            if versions is not None:
                for version in versions.values():
                    screenshots = version.get('screenshots')
                    if screenshots is not None:
                        screenshot = extract_latest_screenshot(screenshot, *screenshots)
            if screenshot:
                debian['screenshot'] = collections.OrderedDict([
                    ('large_image_url', screenshot['large_image_url']),
                    ('screenshot_url', screenshot['screenshot_url']),
                    ('small_image_url', screenshot['small_image_url']),
                ])

        if source is not None:
            security_issues = source.get('security_issues')
            if security_issues:
                debian['security_issues'] = security_issues

        if not debian:
            continue
        yield canonical_name, debian


def make_yaml_dir_iter(entity_relative_dir=None):
    def iter_yaml_dir(dir, canonical_name_by_name, entity_by_canonical_name, update_only):
        if entity_relative_dir is not None:
            dir = os.path.join(dir, entity_relative_dir)
        assert os.path.exists(dir), "Directory doesn't exist: {}".format(dir)
        for sub_dir, dirs_name, filenames in os.walk(dir):
            for dir_name in dirs_name[:]:
                if dir_name.startswith('.'):
                    dirs_name.remove(dir_name)
            for filename in filenames:
                if not filename.endswith(".yaml"):
                    continue
                name = os.path.splitext(filename)[0]
                canonical_name = canonical_name_by_name.get(name, name)
                entity = entity_by_canonical_name.get(canonical_name)
                if entity is None and update_only:
                    continue
                yaml_path = os.path.join(sub_dir, filename)
                with open(yaml_path) as yaml_file:
                    yield canonical_name, yaml.load(yaml_file)
    return iter_yaml_dir


#


app_name = os.path.splitext(os.path.basename(__file__))[0]
args = None
debian_stable_release_name = 'jessie'
log = logging.getLogger(app_name)
source_config_by_name = {
    # Sources that are allowed to create new entities
    'civic-graph': dict(
        actors_iter = make_yaml_dir_iter(),
        data_repository_url = 'https://git.framasoft.org/codegouv/civic-graph-yaml',
        dir = 'civic-graph-yaml',
        name = 'Civic Graph',
        source_url = 'http://civicgraph.io/',
        ),
    'civic-tech-field-guide': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/civic-tech-field-guide-yaml',
        dir = 'civic-tech-field-guide-yaml',
        name = 'Civic Tech Field Guide',
        source_url = 'http://bit.ly/organizecivictech',
        tools_iter = make_yaml_dir_iter(),
        ),
    'civicstack': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/civicstack-yaml',
        dir = 'civicstack-yaml',
        name = 'CivicStack',
        source_url = 'http://www.civicstack.org/',
        tools_iter = make_yaml_dir_iter(),
        ),
    'harnessing-collaborative-technologies': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/harnessing-collaborative-technologies-yaml',
        dir = 'harnessing-collaborative-technologies-yaml',
        name = 'Harnessing Collaborative Technologies report',
        source_url = 'http://collaboration.grantcraft.org/',
        tools_iter = make_yaml_dir_iter(),
        ),
    'mim': dict(
        disabled = True,
        data_repository_url = 'TODO',
        dir = 'TODO',
        name = 'TODO',
        source_url = 'http://pcll.ac-dijon.fr/mim/',
        tools_iter = make_yaml_dir_iter(),
        ),
    'nuit-debout': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/nuit-debout-yaml',
        dir = 'nuit-debout-yaml',
        name = 'Nuit Debout',
        source_url = "https://wiki.nuitdebout.fr/wiki/Ressources/Liste_d'outils_numériques",
        tools_iter = make_yaml_dir_iter(),
        ),
    'ogptoolbox-framacalc': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/ogptoolbox-framacalc-yaml',
        dir = 'ogptoolbox-framacalc-yaml',
        name = 'OGP Toolbox Framacalc',
        source_url = 'https://framacalc.org/ogptoolbox',
        tools_iter = make_yaml_dir_iter(),
        ),
    'participatedb': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/participatedb-yaml',
        dir = 'participatedb-yaml',
        name = 'ParticipateDB',
        projects_iter = make_yaml_dir_iter('projects'),
        source_url = 'http://www.participatedb.com/',
        tools_iter = make_yaml_dir_iter('tools'),
        ),
    'tech-plateforms': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/tech-plateforms-yaml',
        dir = 'tech-plateforms-yaml',
        name = 'Tech Plateforms for Civic Participations',
        source_url = 'https://docs.google.com/spreadsheets/d/1YBZLdNsGohGBjO5e7yrwOQx78IzCA6SNW6T14p15aKU',
        tools_iter = make_yaml_dir_iter(),
        ),
    
    # Sources that are not allowed to create new entities (update_only)
    'debian-appstream': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/appstream-debian-yaml',
        dir = 'appstream-debian-yaml',
        name = 'Debian Appstream',
        source_url = 'https://wiki.debian.org/AppStream',
        tools_iter = make_yaml_dir_iter(),
        update_only = True,
        ),
    'udd': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/udd-yaml',
        dir = 'udd-yaml',
        name = 'Universal Debian Database',
        source_url = 'https://wiki.debian.org/UltimateDebianDatabase',
        tools_iter = iter_udd_yaml_dir,
        update_only = True,
        ),
    'wikidata': dict(
        data_repository_url = 'https://git.framasoft.org/codegouv/wikidata-yaml',
        dir = 'wikidata-yaml',
        name = 'WikiData',
        source_url = 'http://wikidata.org/',
        tools_iter = make_yaml_dir_iter(),
        update_only = True,
        ),
    }
sources_name = sorted(source_config_by_name.keys())


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_name', choices=['all'] + sources_name, help='source name ("all" to merge all sources)')
    parser.add_argument('source_dir', help='path of directory containing source data directories')
    parser.add_argument('target_dir', help='path of target directory for generated YAML files')
    parser.add_argument('--specificities-dir', default='./specificities', dest='specificities_dir',
        help='path of directory containing merge particularities in YAML files')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    assert os.path.exists(args.source_dir)
    if not os.path.exists(args.target_dir):
        os.makedirs(args.target_dir)

    canonical_name_by_name_by_source = {}
    for filename in os.listdir(args.specificities_dir):
        if not filename.endswith(".yaml"):
            continue
        canonical_name = os.path.splitext(filename)[0]
        yaml_path = os.path.join(args.specificities_dir, filename)
        with open(yaml_path) as yaml_file:
            specificities = yaml.load(yaml_file)
            for source_name, source_specificities in specificities.items():
                if source_specificities is None:
                    continue
                assert source_name in sources_name, 'Invalid source "{}" in specificities file "{}"'.format(
                    source_name, yaml_path)
                name = source_specificities.get('name')
                if name:
                    canonical_name_by_name_by_source.setdefault(source_name, {})[name] = canonical_name

    if args.source_name == 'all':
        entity_by_canonical_name_by_type = {}
        for source_name, source_config in sorted(source_config_by_name.items(),
                key = lambda name_config_couple: name_config_couple[1].get('update_only', False)):
            if source_config.get('disabled', False):
                print('Skipping disabled source {}.'.format(source_name))
                continue
            print('Merging source {}...'.format(source_name))
            canonical_name_by_name = canonical_name_by_name_by_source.get(source_name, {})
            update_only = source_config.get('update_only', False)
            for entity_type in ('actors', 'projects', 'tools'):
                entities_iter = source_config.get('{}_iter'.format(entity_type))
                if entities_iter is None:
                    continue
                entity_by_canonical_name = entity_by_canonical_name_by_type.setdefault(entity_type, {}) 
                for canonical_name, source_entity in entities_iter(
                        os.path.join(args.source_dir, source_config['dir']),
                        canonical_name_by_name,
                        entity_by_canonical_name,
                        update_only,
                        ):
                    source_entity['_source'] = dict(
                        data_repository_url = source_config['data_repository_url'],
                        name = source_config['name'],
                        source_url = source_config['source_url'],
                        )
                    entity = entity_by_canonical_name.get(canonical_name)
                    if entity is None:
                        entity_by_canonical_name[canonical_name] = entity = {}
                    entity[source_name] = source_entity

        for entity_type, entity_by_canonical_name in entity_by_canonical_name_by_type.items():
            type_dir = os.path.join(args.target_dir, entity_type)
            if not os.path.exists(type_dir):
                os.makedirs(type_dir)
            for canonical_name, entity in entity_by_canonical_name.items():
                entity_path = os.path.join(type_dir, '{}.yaml'.format(canonical_name))
                with open(entity_path, 'w') as entity_file:
                    yaml.dump(entity, entity_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)
    # else:
    #     TODO
    #     source_config = source_config_by_name[args.source_name]
    #     if not source_config.get('disabled', False):
    #         update_only = source_config.get('update_only', False)
    #     entity_by_canonical_name_by_type = {}
    #     for entity_type in os.listdir(args.target_dir):
    #         if entity_type.startswith('.'):
    #             continue
    #         entity_by_canonical_name = entity_by_canonical_name_by_type.setdefault(entity_type, {})
    #         for filename in os.listdir(os.path.join(args.source_name, entity_type)):
    #             if not filename.endsswith('.yaml'):
    #                 continue
    #             canonical_name = os.path.splitext(filename)[0]
    #             with open(os.path.join(os.path.join(args.source_name, entity_type, filename))) as entity_file:
    #                 entity = yaml.load(entity_file)
    #             with open()
    #             entity_by_canonical_name[canonical_name] = yaml.load(yaml_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
