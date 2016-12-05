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
    'By': 'schema:bijective-card-references-array',
        # Final Use.By -> Organization.Final Use
    'Description': 'schema:localized-strings-array',
    'Developer': 'schema:bijective-card-references-array',
        # Software.Developer -> Organization.Developer of
    'Logo': 'schema:uris-array',
    'Partner': 'schema:bijective-card-references-array',
        # Final Use.Partner -> Organization.Partner for
        # Platform.Partner -> Organization.Partner for
    'Provider': 'schema:bijective-card-references-array',
        # Platform.Provider -> Organization.Provider of
    'Screenshot': 'schema:uris-array',
    'Software': 'schema:bijective-card-references-array',
        # Platform.Software -> Software.Used by
    'Tool': 'schema:bijective-card-references-array',
        # Final Use.Tool -> Software.Used by
        # Final Use.Tool -> Platform.Used by
    'Software': 'schema:bijective-card-references-array',
        # Platform.Software -> Software.Used by
    'Types': 'schema:value-ids-array',
    'Used by': 'schema:bijective-card-references-array',
        # Software.Used by -> Platform.Software
    'Uses': 'schema:bijective-card-references-array',
        # Software.Uses -> Software.Used by
    }
spreadsheet_id = '1Sjp9PG75Ap-5YBvOWZ-cCUGkNhN41LZlz3OL-gJ-tKU'
sheet_id_by_name = {
    "Software": '1702131855',
    "Platform": '2066765238',
    "Final Use": '1374288343',
    "Organization": '475734092',
    }
type_symbol_by_sheet_name = {
    "Software": 'software',
    "Platform": 'platform',
    "Final Use": 'use-case',
    "Organization": 'organization',
    }
widgets = {
    'By': dict(tag = 'RatedItemOrSet'),
    'Description': dict(
        tag = 'textarea',
        ),
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
            repair_label(label)
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
            values = entry.setdefault('Types', [])
            type_symbol = type_symbol_by_sheet_name[sheet_name]
            if type_symbol not in values:
                values.append(type_symbol)

            # Merge descriptions in different languages.
            description_by_language = {}
            for label, language in (
                    ('Description-EN', 'en'),
                    ('Description-FR', 'fr'),
                    ):
                if label in labels:
                    index = labels.index(label)
                    localization = (row[index] or '').strip()
                    if localization.startswith('-'):
                        continue
                    description_by_language[language] = localization

            clean_labels = []
            clean_row = []
            for label, value in zip(labels, row):
                if label in ('Description-EN', 'Description-FR'):
                    continue
                clean_labels.append(label)
                clean_row.append(value)
            if description_by_language:
                clean_labels.append('Description')
                clean_row.append(description_by_language)

            # Add cells to card.
            for label, value in zip(clean_labels, clean_row):
                if slugify(label) == 'delete':
                    continue
                if isinstance(value, str):
                    if value.lstrip().startswith('-'):
                        continue
                    fragments = value.split(',') if label == 'Location' else [value]
                    for fragment in fragments:
                        fragment = fragment.strip()
                        if fragment.endswith(('[initiative]', '[service]', '[software]',
                                '(initiative)', '(service)', '(software)')):
                            fragment = fragment.rsplit(None, 1)[0].rstrip()
                        if not fragment:
                            continue
                        values = entry.setdefault(label, [])
                        if fragment not in values:
                            values.append(fragment)
                else:
                    if not value:
                        continue
                    values = entry.setdefault(label, [])
                    if value not in values:
                        values.append(value)

    for name, entry in entry_by_name.items():
        for label, schema in schemas.items():
            values = entry.get(label)
            if values is None:
                continue
            if schema == 'schema:bijective-card-references-array':
                if label == 'By':
                    # Final Use.By -> Organization.Final Use
                    entry[label] = [
                        dict(reverseKeyId = 'Final Use', targetId = value)
                        for value in values
                        ]
                elif label == 'Developer':
                    # Software.Developer -> Organization.Developer of
                    entry[label] = [
                        dict(reverseKeyId = 'Developer of', targetId = value)
                        for value in values
                        ]
                elif label == 'Partner':
                    # Final Use.Partner -> Organization.Partner for
                    # Platform.Partner -> Organization.Partner for
                    entry[label] = [
                        dict(reverseKeyId = 'Partner for', targetId = value)
                        for value in values
                        ]
                elif label == 'Provider':
                    # Platform.Provider -> Organization.Provider of
                    entry[label] = [
                        dict(reverseKeyId = 'Provider of', targetId = value)
                        for value in values
                        ]
                elif label == 'Software':
                    # Platform.Software -> Software.Used by
                    entry[label] = [
                        dict(reverseKeyId = 'Used by', targetId = value)
                        for value in values
                        ]
                elif label == 'Tool':
                    # Final Use.Tool -> Software.Used by
                    # Final Use.Tool -> Platform.Used by
                    entry[label] = [
                        dict(reverseKeyId = 'Used by', targetId = value)
                        for value in values
                        ]
                elif label == 'Used by':
                    # Software.Used by -> Platform.Software
                    entry[label] = [
                        dict(reverseKeyId = 'Software', targetId = value)
                        for value in values
                        ]
                elif label == 'Uses':
                    # Software.Uses -> Software.Used by
                    entry[label] = [
                        dict(reverseKeyId = 'Used by', targetId = value)
                        for value in values
                        ]
            elif schema == 'schema:uris-array':
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
        language = 'en',  # Language used by default by the cards (for example, for the keys of their attributes)
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


def repair_label(label):
    label = label.strip()
    return {
        "Tag": "Tags",
        "Tag-Usage": "Tags",
        }.get(label, label)


def upload_image(url):
    if not url.startswith(('http://', 'https://')) and not os.path.exists(os.path.join('images', url)):
        log.warning('Ignoring invalid image URL: {}'.format(url))
        return None
    if os.path.exists(os.path.join('images', url)):
        with open(os.path.join('images', url), 'rb') as image:
            return upload_image2(url, image)
    else:
        path = image_path_by_url.get(url, KeyError)
        if path is not KeyError:
            return path

        try:
            response = requests.get(url,
                headers = {
                    'Accept': 'Accept:image/png,image/;q=0.8,/*;q=0.5',  # Firefox
                    },
                )
        except requests.exceptions.SSLError:
            log.exception('SSL error when retrieving image at URL: {}'.format(url))
            image_path_by_url[url] = None
            return None
        if response.status_code == 403:
            log.warning('Image access forbidden at URL: {}'.format(url))
            image_path_by_url[url] = None
            return None
        if response.status_code == 404:
            log.warning('Image not found at URL: {}'.format(url))
            image_path_by_url[url] = None
            return None
        response.raise_for_status()
        image = response.content
        return upload_image2(url, image)


def upload_image2(url, image):
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
        if response.status_code == 400:
            image_path_by_url[url] = None
            return None

    response.raise_for_status()
    data = response.json()['data']
    log.info('Uploaded image "{}" to "{}"'.format(url, data['path']))
    path = data['path']
    image_path_by_url[url] = path
    return path


if __name__ == "__main__":
    sys.exit(main())
