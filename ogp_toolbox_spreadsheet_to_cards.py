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
log = logging.getLogger(app_name)
spreadsheet_id = '1Sjp9PG75Ap-5YBvOWZ-cCUGkNhN41LZlz3OL-gJ-tKU'
sheet_id_by_name = {
    "Software": '1702131855',
    "Platform": '2066765238',
    "Usage": '1374288343',
    "Organization": '475734092',
    }
csv_url_template = 'https://docs.google.com/spreadsheets/d/{id}/export?format=csv&id={id}&gid={gid}'


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
            for label, value in zip(labels, row):
                if slugify(label) == 'delete':
                    continue
                value = value.strip()
                if value and not value.startswith('-'):
                    values = entry.setdefault(label, [])
                    if value not in values:
                        values.append(value)

    body = dict(
        key = 'Name',
        cards = list(entry_by_name.values()),
        )
    # print(json.dumps(body, ensure_ascii = False, indent = 2))
    request = urllib.request.Request(
        data = json.dumps(body, ensure_ascii = False, indent = 2).encode('utf-8'),
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Retruco-API-Key': args.api_key,
            },
        url = urllib.parse.urljoin(args.api_url, '/cards-bundle'),
        )
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        print('Error response {}:\n{}'.format(e.code, e.read().decode('utf-8')))
        raise
    data = json.loads(response.read().decode('utf-8'))
    print(data)

    return 0


if __name__ == "__main__":
    sys.exit(main())