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


"""Harvest CSV files from Google spreadsheet of OGP Toolbox and generate cards."""


import argparse
import codecs
import collections
import csv
import itertools
import json
import logging
import os
import sys
import urllib.parse

import requests
from slugify import slugify


app_name = os.path.splitext(os.path.basename(__file__))[0]
args = None
csv_url_template = 'https://docs.google.com/spreadsheets/d/{id}/export?format=csv&id={id}&gid={gid}'
image_path_by_url = {}
log = logging.getLogger(app_name)
schemas = {
    'By': dict(
        # Final Use.By -> Organization.Final Use
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Developer': dict(
        # Software.Developer -> Organization.Developer of
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Logo': dict(
        type = 'array',
        items = dict(
            type = 'string',
            format = 'uri',
            ),
        ),
    'Partner': dict(
        # Final Use.Partner -> Organization.Partner for
        # Platform.Partner -> Organization.Partner for
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Provider': dict(
        # Platform.Provider -> Organization.Provider of
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Screenshot': dict(
        type = 'array',
        items = dict(
            type = 'string',
            format = 'uri',
            ),
        ),
    'Software': dict(
        # Platform.Software -> Software.Used by
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Tool': dict(
        # Final Use.Tool -> Software.Used by
        # Final Use.Tool -> Platform.Used by
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Used by': dict(
        # Software.Used by -> Platform.Software
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    'Uses': dict(
        # Software.Uses -> Software.Used by
        type = 'array',
        items = {'$ref': '/schemas/bijective-uri-reference'},
        ),
    }
spreadsheet_id = '1Sjp9PG75Ap-5YBvOWZ-cCUGkNhN41LZlz3OL-gJ-tKU'
sheet_id_by_name = {
    "Software": '1702131855',
    "Platform": '2066765238',
    "Final Use": '1374288343',
    "Organization": '475734092',
    }
widgets = {
    'By': dict(tag = 'RatedItemOrSet'),
    'Developer': dict(tag = 'RatedItemOrSet'),
    'Logo': dict(tag = 'Image'),
    'Partner': dict(tag = 'RatedItemOrSet'),
    'Provider': dict(tag = 'RatedItemOrSet'),
    'Screenshot': dict(tag = 'Image'),
    'Software': dict(tag = 'RatedItemOrSet'),
    'Tool': dict(tag = 'RatedItemOrSet'),
    'Used by': dict(tag = 'RatedItemOrSet'),
    'Uses': dict(tag = 'RatedItemOrSet'),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('api_url', help='base URL of API server')
    parser.add_argument('-k', '--api-key', required = True, help = 'server API key')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    if not os.path.exists('cache'):
        os.mkdir('cache')
    cached_images_path = os.path.join('cache', 'images.json')
    if os.path.exists(cached_images_path):
        with open(cached_images_path) as cached_images_file:
            cached_images = json.load(cached_images_file)
        image_path_by_url.update(cached_images)

    entry_by_name = {}
    for sheet_name, sheet_id in sorted(sheet_id_by_name.items()):
        response = requests.get(
            csv_url_template.format(
                gid = sheet_id,
                id = spreadsheet_id,
                ),
            )
        response.raise_for_status()
        csv_reader = csv.reader(response.content.decode('utf-8').splitlines())
        labels = [
            label.strip()
            for label in next(csv_reader)
            ]
        name_index = labels.index("Name")
        assert name_index >= 0, (sheet_name, labels)
        for row in csv_reader:
            if all(not cell.strip() for cell in row):
                continue
            name = row[name_index].strip()
            assert name, (sheet_name, labels, name_index, row)
            if dict(zip((slugify(label) for label in labels), row)).get('delete', '').strip():
                # Row is marked as deleted => Skip it.
                # TODO: Rate it with -1 instead of ignoring it.
                continue
            entry = entry_by_name.setdefault(name, collections.OrderedDict())
            # First add sheet_name as card type.
            values = entry.setdefault('Card Type', [])
            if sheet_name not in values:
                values.append(sheet_name)
            # Add cells to card.
            for label, value in zip(labels, row):
                if slugify(label) == 'delete':
                    continue
                value = value.strip()
                if value.endswith(('[initiative]', '[service]', '[software]')):
                    value = value.rsplit(None, 1)[0].rstrip()
                if value and not value.startswith('-'):
                    values = entry.setdefault(label, [])
                    if value not in values:
                        values.append(value)

    for name, entry in entry_by_name.items():
        for label, schema in schemas.items():
            values = entry.get(label)
            if values is None:
                continue
            if schema['type'] == 'array' and schema['items'].get('$ref') == '/schemas/bijective-uri-reference':
                if label == 'By':
                    # Final Use.By -> Organization.Final Use
                    entry[label] = [
                        dict(reverseName = 'Final Use', targetId = value)
                        for value in values
                        ]
                elif label == 'Developer':
                    # Software.Developer -> Organization.Developer of
                    entry[label] = [
                        dict(reverseName = 'Developer of', targetId = value)
                        for value in values
                        ]
                elif label == 'Partner':
                    # Final Use.Partner -> Organization.Partner for
                    # Platform.Partner -> Organization.Partner for
                    entry[label] = [
                        dict(reverseName = 'Partner for', targetId = value)
                        for value in values
                        ]
                elif label == 'Provider':
                    # Platform.Provider -> Organization.Provider of
                    entry[label] = [
                        dict(reverseName = 'Provider of', targetId = value)
                        for value in values
                        ]
                elif label == 'Software':
                    # Platform.Software -> Software.Used by
                    entry[label] = [
                        dict(reverseName = 'Used by', targetId = value)
                        for value in values
                        ]
                elif label == 'Tool':
                    # Final Use.Tool -> Software.Used by
                    # Final Use.Tool -> Platform.Used by
                    entry[label] = [
                        dict(reverseName = 'Used by', targetId = value)
                        for value in values
                        ]
                elif label == 'Used by':
                    # Software.Used by -> Platform.Software
                    entry[label] = [
                        dict(reverseName = 'Software', targetId = value)
                        for value in values
                        ]
                elif label == 'Uses':
                    # Software.Uses -> Software.Used by
                    entry[label] = [
                        dict(reverseName = 'Used by', targetId = value)
                        for value in values
                        ]
            elif schema['type'] == 'array' and schema['items'].get('type') == 'string' \
                    and schema['items'].get('format') == 'uri':
                widget = widgets.get(label)
                if widget['tag'] == 'Image':
                    uploaded_images_url = [
                        image_url
                        for image_url in (
                            upload_image(value)
                            for value in values
                            )
                        if image_url is not None
                        ]
                    if uploaded_images_url:
                        entry[label] = uploaded_images_url
                    else:
                        del entry[label]

    with open(cached_images_path, 'w') as cached_images_file:
        cached_images = json.dump(image_path_by_url, cached_images_file, ensure_ascii = False, indent = 2)

    body = dict(
        key = 'Name',
        cards = list(entry_by_name.values()),
        schemas = schemas,
        widgets = widgets,
        )
    # print(json.dumps(body, ensure_ascii = False, indent = 2))
    response = requests.post(urllib.parse.urljoin(args.api_url, '/cards/bundle'),
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Retruco-API-Key': args.api_key,
            },
        json = body,
        )
    if response.status_code != requests.codes.ok:
        error_body = response.content.decode('utf-8')
        try:
            error_json = json.loads(error_body)
        except json.JSONDecodeError:
            print('Error response {}:\n{}'.format(response.status_code, error_body))
        else:
            print('Error response {}:\n{}'.format(response.status_code, json.dumps(error_json, ensure_ascii = False, indent = 2)))
        response.raise_for_status()

    data = response.json()
    print(json.dumps(data, ensure_ascii = False, indent = 2))
    return 0


def upload_image(url):
    if not url.startswith(('http://', 'https://')):
        log.warning('Ignoring invalid image URL: {}'.format(url))
        return None
    path = image_path_by_url.get(url, KeyError)
    if path is not KeyError:
        return path

    response = requests.get(url,
        headers = {
            'Accept': 'Accept:image/png,image/;q=0.8,/*;q=0.5',  # Firefox
            },
        )
    if response.status_code == 404:
        log.warning('Image not found at URL: {}'.format(url))
        image_path_by_url[url] = None
        return None
    response.raise_for_status()
    image = response.content
    response = requests.post(urllib.parse.urljoin(args.api_url, '/uploads/images'),
        files = dict(file = image),
        headers = {
            'Accept': 'application/json',
            'Retruco-API-Key': args.api_key,
            },
        )
    if response.status_code != 201:
        log.warning('Ignoring invalid image at URL: {}'.format(url))
    if not response.ok:
        log.error('Image upload failed for {}:\n{}'.format(url, response.text))
    response.raise_for_status()
    data = response.json()['data']
    log.info('Uploaded image "{}" to "{}"'.format(url, data['path']))
    path = data['path']
    image_path_by_url[url] = path
    return path


if __name__ == "__main__":
    sys.exit(main())
