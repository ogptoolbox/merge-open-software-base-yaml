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
import urllib.parse

import requests
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
log = logging.getLogger(app_name)


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
    parser.add_argument('source_dir', help='path of source directory containing YAML files')
    parser.add_argument('server_url', help='URL of OGPToolbox Editor')
    parser.add_argument('-p', '--password', help='password of user')
    parser.add_argument('-u', '--user', help='username or email address of user')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    # Login to retrieve user API key.
    response = requests.post(urllib.parse.urljoin(args.server_url, 'login'), json = {
        "userName": args.user,
        "password": args.password,
        })
    data = response.json() 
    api_key = data['data']['apiKey']

    response = requests.get(
        urllib.parse.urljoin(args.server_url, '/tools'),
        headers = {
            "OGPToolbox-API-Key": api_key,
            },
        )
    tools_by_name = {
        tool['name']: tool
        for tool in response.json()['data']
        }

    for source_data_path, source_data in iter_yaml_files(args.source_dir):
        canonical = source_data['canonical']
        tool = dict(
            name = source_data['name'],
            )

        description_fr = canonical.get('longDescription', {}).get('fr', {}).get('value')
        if description_fr is not None:
            tool['description_fr'] = description_fr

        description_en = canonical.get('longDescription', {}).get('en', {}).get('value')
        if description_en is not None:
            tool['description_en'] = description_en

        license = canonical.get('license', {}).get('value')
        if license is not None:
            tool['license'] = license

        source_code_url = canonical.get('sourceCode', {}).get('value')
        if source_code_url is not None:
            tool['sourceCode'] = source_code_url

        bug_tracker_url = canonical.get('bugTracker', {}).get('value')
        if bug_tracker_url is not None:
            tool['bugTrackerURL'] = bug_tracker_url

        screenshot_url = canonical.get('screenshot', {}).get('value')
        if screenshot_url is not None:
            tool['screenshots'] = [screenshot_url]

        stackexchange_tag = canonical.get('stackexchangeTag', {}).get('value')
        if stackexchange_tag is not None:
            tool['stackexchangeTag'] = [stackexchange_tag]

        categories = canonical.get('categories', [])
        if categories:
            categories = [
                category['value']
                for category in categories
                if category['value']
                ]
            if categories:
                tool['otherCategories'] = categories

        technology = canonical.get('technology', {}).get('fr', {}).get('value')
        if technology is not None:
            tool['technologies'] = [technology]

        existing_tool = tools_by_name.get(tool['name'])
        if existing_tool is None:
            print('New tool: {}'.format(tool['name']))
            response = requests.post(
                urllib.parse.urljoin(args.server_url, '/tools'),
                headers = {
                    "OGPToolbox-API-Key": api_key,
                    },
                json = tool,
                )
        else:
            updated_tool = existing_tool.copy()
            changed = False
            for key, value in tool.items():
                if key not in updated_tool:
                    updated_tool[key] = value
                    changed = True
            if changed:
                print('Updated tool: {}'.format(tool['name']))
                response = requests.put(
                    urllib.parse.urljoin(args.server_url, '/tools/{}'.format(updated_tool['id'])),
                    headers = {
                        "OGPToolbox-API-Key": api_key,
                        },
                    json = updated_tool,
                    )

    return 0

if __name__ == "__main__":
    sys.exit(main())
