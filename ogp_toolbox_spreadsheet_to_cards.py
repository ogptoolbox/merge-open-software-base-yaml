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
import urllib.request

from slugify import slugify


app_name = os.path.splitext(os.path.basename(__file__))[0]
csv_url_template = 'https://docs.google.com/spreadsheets/d/{id}/export?format=csv&id={id}&gid={gid}'
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
    'Partner': dict(tag = 'RatedItemOrSet'),
    'Provider': dict(tag = 'RatedItemOrSet'),
    'Software': dict(tag = 'RatedItemOrSet'),
    'Tool': dict(tag = 'RatedItemOrSet'),
    'Used by': dict(tag = 'RatedItemOrSet'),
    'Uses': dict(tag = 'RatedItemOrSet'),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('api_url', help='base URL of API server')
    parser.add_argument('-k', '--api-key', required = True, help = 'Server API key')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    entry_by_name = {}
    for sheet_name, sheet_id in sorted(sheet_id_by_name.items()):
        response = urllib.request.urlopen(csv_url_template.format(
            gid = sheet_id,
            id = spreadsheet_id,
            ))
        csv_reader = csv.reader(codecs.iterdecode(response, 'utf-8'))
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
        card_types = entry['Card Type']
        for label, schema in schemas.items():
            values = entry.get(label)
            if values is None:
                continue
            if schema['type'] == 'array' and schema['items']['$ref'] == '/schemas/bijective-uri-reference':
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

    body = dict(
        key = 'Name',
        cards = list(entry_by_name.values()),
        schemas = schemas,
        widgets = widgets,
        )
    # print(json.dumps(body, ensure_ascii = False, indent = 2))
    request = urllib.request.Request(
        data = json.dumps(body, ensure_ascii = False, indent = 2).encode('utf-8'),
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Retruco-API-Key': args.api_key,
            },
        url = urllib.parse.urljoin(args.api_url, '/cards/bundle'),
        )
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_body)
        except json.JSONDecodeError:
            print('Error response {}:\n{}'.format(e.code, error_body))
        else:
            print('Error response {}:\n{}'.format(e.code, json.dumps(error_json, ensure_ascii = False, indent = 2)))
        raise
    data = json.loads(response.read().decode('utf-8'))
    print(json.dumps(data, ensure_ascii = False, indent = 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
