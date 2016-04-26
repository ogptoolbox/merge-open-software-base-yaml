# merge-open-software-base-yaml

Merge YAML files describing software products harvested from various open data sources.
Generate an open database of software (in YAML format).

## Usage

Step 1 and step 2 must be applied both before commiting, in order to preserve history.

```bash
git clone https://git.framasoft.org/codegouv/merge-open-software-base-yaml.git
cd merge-open-software-base-yaml
```

### Step 1: merge sources to YAML files

```
$ ./merge.py --help
usage: merge.py [-h] [--specificities-dir SPECIFICITIES_DIR] [-c] [-v]
                source_name source_dir target_dir

positional arguments:
  source_name           source name among the ones known by the merger (mim,
                        udd, debian-apstream, wikidata, civicstack)
  source_dir            path of source data directory
  target_dir            path of target directory for generated YAML files

optional arguments:
  -h, --help            show this help message and exit
  --specificities-dir SPECIFICITIES_DIR
                        path of directory containing merge particularities in
                        YAML files
  -c, --create          by default, the script only add information to
                        existing files. With --create, when a program does not
                        have a file, the user is asked if they want to create
                        the file.
  -v, --verbose         increase output verbosity

 ./merge.py udd ../data/udd|yaml.git ../open

```

### Step 2: clean data and merge canonical data

This step build the `canonical` key aggregates data from the various present sources. You need node.js to run this step.

```bash
npm install
node generate_canonical.js ../open-software-base-yaml
```

# Open Sofware Base

The generated database is the [Open Sofware Base (in YAML format)](https://git.framasoft.org/codegouv/open-software-base-yaml).
