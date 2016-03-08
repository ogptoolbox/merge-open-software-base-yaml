'use strict';

const co = require('co');
const fs = require('mz/fs');
const minimatch = require('minimatch');
const path = require('path');
const program = require('commander');
const yaml = require('js-yaml');

var updateFile = co.wrap(function *(fileName) {
  var data = yaml.safeLoad(yield fs.readFile(fileName));

  data.canonical = {};

  if (data.debian_appstream) {
    data.canonical.canonicalName = {
      value: data.debian_appstream.Name.C,
      source: 'debian_appstream'
    };
  }
  if (data.debian) {
    data.canonical.longDescription = (() => {
      var description = {};

      Object.keys(data.debian.description).forEach(locale => {
        description[locale] = {
          value: data.debian.description[locale].long_description,
          source: 'debian'
        };
      });

      return description;
    })();

    if (data.debian.screenshot) {
      data.canonical.screenshot = {
        value: data.debian.screenshot.large_image_url,
        source: 'debian'
      };
    }
  }

  var sortKeys = function(a, b) {
    if (a === 'name') {
      return -1;
    }

    if (a === 'canonical') {
      return b === 'name' ? 1 : -1;
    }

    if (b === 'name' || b === 'canonical') {
      return (sortKeys(b, a)) * -1;
    }

    return 0;
  };

  data = yaml.safeDump(data, {
    indent: 2,
    sortKeys: sortKeys,
    lineWidth: 120
  });
  yield fs.writeFile(fileName, data);
});

co(function *() {
  var dataDir;

  program
    .version(require('./package.json').version)
    .usage('<outputDir>')
    .arguments('<outputDir>')
    .action(outputDir => {
      dataDir = outputDir;
    })
    .parse(process.argv);

  if (typeof dataDir === 'undefined') {
    console.error('No output directory given.');
    process.exit(1);
  }

  var stats;
  try {
    stats = yield fs.stat(dataDir);
  } catch (e) {
    if (e.code === 'ENOENT') {
      console.error('Output directory does not exists.');
      process.exit(1);
    }
  }

  if (!stats.isDirectory()) {
    console.error(dataDir + ' is not a directory.');
    process.exit(1);
  }

  var files = (yield fs.readdir(dataDir))
    .filter(filename => (minimatch(filename, '*.+(yaml|yml)')))
    .map(fileName => (path.join(dataDir, fileName)));
  files.forEach(co.wrap(function *(fileName) {
    try {
      yield updateFile(fileName);
    } catch (e) {
      console.log(e);
      process.exit(1);
    }
  }));
  console.log('Updated ' + files.length + ' files');
}).catch(console.log);
