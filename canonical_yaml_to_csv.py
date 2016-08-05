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


"""Convert directory of YAML files containing canonical informations to a single CSV file (with only canonical data)."""


import argparse
import collections
import csv
import logging
import os
import sys

import yaml, yaml.constructor, yaml.parser, yaml.scanner


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
log = logging.getLogger(app_name)


def get_path(item, path, default=None):
    if item is None:
        return default
    if not path:
        return item
    split_path = path.split('.', 1)
    key = split_path[0]
    if key.isdigit():
        if not isinstance(item, (list, tuple)):
            return default
        index = int(key)
        value = item[index] if 0 <= index < len(item) else None
    else:
        if not isinstance(item, dict):
            return default
        value = item.get(key)
    if len(split_path) <= 1:
        return value if value is not None else default
    return get_path(value, split_path[1], default=default)


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
                try:
                    yield yaml_file_path, yaml.load(yaml_file)
                except (UnicodeDecodeError, yaml.constructor.ConstructorError, yaml.parser.ParserError,
                        yaml.scanner.ScannerError):
                    log.warning("Invalid syntax in YAML file {}".format(yaml_file_path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', help='path of YAML data directory')
    parser.add_argument('target_dir', help='name of directory containing generated CSV file')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    if not os.path.exists(args.target_dir):
        os.makedirs(args.target_dir)

    # PROJECTS

    projects_csv_path = os.path.join(args.target_dir, 'projects.csv')
    entries = []
    tagsCount = 0
    toolsCount = 0
    for project_path, project in iter_yaml_files(os.path.join(args.source_dir, 'projects')):
        canonical = project['canonical']
        tags = [
            tag['value']
            for tag in get_path(canonical, 'tags.en', [])
            ]
        tools = [
            tool['value']
            for tool in get_path(canonical, 'tools', [])
            ]
        entries.append(dict(
            longDescription = get_path(canonical, 'longDescription.en.value'),
            name = get_path(canonical, 'name.value'),
            tags = tags,
            tools = tools,
            website = get_path(canonical, 'website.value'),
            ))
        if len(tags) > tagsCount:
            tagsCount = len(tags)
        if len(tools) > toolsCount:
            toolsCount = len(tools)

    with open(projects_csv_path, 'w') as target_file:
        csv_writer = csv.writer(target_file)
        csv_writer.writerow([
            'Name',
            'Description',
            'Website',
            ] + ['Tag'] * tagsCount + ['Tool'] * toolsCount)
        entries.sort(key = lambda entry: entry['name'] or '')
        for entry in entries:
            if entry['name'] is None:
                print('Skipping entry without name: {}'.format(entry))
                continue
            tags = entry['tags']
            tools = entry['tools']
            row = [
                entry['name'] or '',
                entry['longDescription'] or '',
                entry['website'] or '',
                ] + tags + [''] * (tagsCount - len(tags)) + tools + [''] * (toolsCount - len(tools))
            csv_writer.writerow(row)

    # TOOLS

    tools_csv_path = os.path.join(args.target_dir, 'tools.csv')
    entries = []
    tagsCount = 0
    for tool_path, tool in iter_yaml_files(os.path.join(args.source_dir, 'tools')):
        canonical = tool['canonical']
        tags = [
            tag['value']
            for tag in get_path(canonical, 'tags.en', [])
            ]
        entries.append(dict(
            bugTracker = get_path(canonical, 'bugTracker.value'),
            license = get_path(canonical, 'license.value'),
            longDescription = get_path(canonical, 'longDescription.en.value'),
            name = get_path(canonical, 'name.value'),
            screenshot = get_path(canonical, 'screenshot.value'),
            sourceCode = get_path(canonical, 'sourceCode.value'),
            stackexchangeTag = get_path(canonical, 'stackexchangeTag.value'),
            tags = tags,
            ))
        if len(tags) > tagsCount:
            tagsCount = len(tags)

    with open(tools_csv_path, 'w') as target_file:
        csv_writer = csv.writer(target_file)
        csv_writer.writerow([
            'Name',
            'Description',
            'License',
            'Source Code URL',
            'Bug Tracker URL',
            'Screenshot URL',
            'StackExchange Tag',
            ] + ['Tag'] * tagsCount)
        entries.sort(key = lambda entry: entry['name'] or '')
        for entry in entries:
            if entry['name'] is None:
                print('Skipping entry without name: {}'.format(entry))
                continue
            tags = entry['tags']
            row = [
                entry['name'] or '',
                entry['longDescription'] or '',
                entry['license'] or '',
                entry['sourceCode'] or '',
                entry['bugTracker'] or '',
                entry['screenshot'] or '',
                entry['stackexchangeTag'] or '',
                ] + tags + [''] * (tagsCount - len(tags))
            csv_writer.writerow(row)

    return 0


if __name__ == "__main__":
    sys.exit(main())
