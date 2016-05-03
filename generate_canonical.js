'use strict';

const co = require('co');
const fs = require('mz/fs');
const minimatch = require('minimatch');
const path = require('path');
const program = require('commander');
const yaml = require('js-yaml');

var fileExists = fs.existsSync || function existsSync(filePath) {
  try {
    fs.statSync(filePath);
  } catch (err) {
    if (err.code === 'ENOENT') {
      return false;
    }
  }
  return true;
};

var get = (obj, keyString) => {
  return keyString.split('.').reduce((o, key) => {
    return (typeof o === 'undefined' || o === null || key === '') ? o : o[key];
  }, obj);
};

var set = (obj, keyString, value) => {
  return keyString.split('.').reduce((o, key, index, array) => {
    if (index === array.length - 1) {
      o[key] = value;
      return o[key];
    }

    if (typeof o[key] === 'undefined' || o[key] === null) {
      o[key] = {};
    }

    return o[key];
  }, obj);
};

var updateFromPriorities = (destData, defaultPrioritiesList, customPrioritiesList, sourceData) => {
  // on which property path are we working
  var propertyPath = [];

  var updateKey = propertyString => {
    var keyPriorities = get(defaultPrioritiesList, propertyString);
    keyPriorities =
      (propertyString && customPrioritiesList &&
      get(customPrioritiesList, propertyString)) ||
      keyPriorities;

    if (Array.isArray(keyPriorities)) {
      // if the object in priorities is an array, we have a list of property
      // to look for in the source data
      var length = keyPriorities.length;
      for (var i = 0; i < length; i++) {
        var value = get(sourceData, keyPriorities[i]);
        if (typeof value !== 'undefined') {
          var source = keyPriorities[i].split('.')[0];
          if (propertyString.match(/\[\]$/)) {
            let current = get(destData, propertyString.replace(/\[|]$/, ''));
            current = (current || []).concat(
              Array.isArray(value) ?
              value.map(elem => ({value: elem, source})) : // eslint-disable-line no-loop-func
              {value, source}
            );
            set(destData, propertyString.replace(/\[\]$/, ''), current);
            continue;
          }
          set(destData, propertyString, {value, source});
          break;
        }
      }
    } else {
      // if the object in priotitiesList for this propertyPath is not an array,
      // we have sub-properties and we apply the function recursively on it
      Object.keys(keyPriorities).forEach(subProperty => {

        propertyPath.push(subProperty);
        updateKey(propertyPath.join('.'));
        propertyPath.pop();
      });
    }
  };

  updateKey('');
};

var updateFile = co.wrap(function *(fileName) {
  var data = yaml.safeLoad(yield fs.readFile(fileName));
  data.canonical = {};

  var defaultPriorities = yaml.safeLoad(
    yield fs.readFile('./priorities/_default.yaml'));
  var customPrioritiesFileName = path.join(
    './priorities', fileName.split('/')[fileName.split('/').length - 1]
  );
  var customPriorities = fileExists(customPrioritiesFileName) &&
    yaml.safeLoad(yield fs.readFile(customPrioritiesFileName));

  updateFromPriorities(data.canonical, defaultPriorities, customPriorities,
    data);

  yield fs.writeFile(fileName, data);

  var sortKeys = function(a, b) {
    if (a === '_source') {
      return -1;
    }

    if (a === 'name') {
      return b === '_source' ? 1 : -1;
    }

    if (a === 'canonical') {
      return b === 'name' || b === '_source' ? 1 : -1;
    }

    if (b === '_source' || b === 'name' || b === 'canonical') {
      return (sortKeys(b, a)) * -1;
    }

    if (a < b) {
      return -1;
    }

    if (a > b) {
      return 1;
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

  yield files.map(co.wrap(function *(fileName) {
    try {
      yield updateFile(fileName);
    } catch (e) {
      console.log(e);
    }
  }));

  console.log('Updated ' + files.length + ' files');
}).catch(err => {
  console.error(err);
});
