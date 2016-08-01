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


"""Convert a directory of YAML files to a single CSV file."""


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


def flatten(paths, flat, path, data):
    if isinstance(data, dict):
        for key, value in data.items():
            flatten(paths, flat, path + (key,), value)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            flatten(paths, flat, path + (index,), value)
    elif isinstance(data, str):
        if path:
            paths.add(path)
        flat[path] = data
    elif data is not None:
        if path:
            paths.add(path)
        flat[path] = str(data)


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
    parser.add_argument('target_path', help='name of generated CSV file')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    paths = set()
    rows = []
    for source_data_path, source_data in iter_yaml_files(args.source_dir):
        flat = {}
        flatten(paths, flat, (), source_data)
        rows.append(flat)

    labels = []
    paths = sorted(paths)
    for path in paths:
        label_fragments = []
        for path_fragment in path:
            if isinstance(path_fragment, str):
                if label_fragments:
                    label_fragments.append('.')
                label_fragments.append(path_fragment)
            else:
                assert isinstance(path_fragment, int), path_fragment
                label_fragments.append('[{}]'.format(path_fragment))
        labels.append(''.join(label_fragments))

    with open(args.target_path, 'w') as target_file:
        csv_writer = csv.writer(target_file)
        csv_writer.writerow(labels)
        for row in rows:
            csv_writer.writerow([
                row[path] if path in row else ''
                for path in paths
                ])
    return 0


if __name__ == "__main__":
    sys.exit(main())
