# merge-open-software-base-yaml

Merge YAML files describing software products harvested from various open data sources.
Generate an open database of software (in YAML format).

## Usage

### Step 1: merge sources to YAML files

```bash
git clone https://git.framasoft.org/codegouv/merge-open-software-base-yaml.git
cd merge-open-software-base-yaml
./merge_open_software_base_yaml.py -v ../mim-to-yaml/data/ specificities/ ../udd-to-yaml/yaml/ ../open-software-base-yaml/
```

### Step 2: clean data and merge canonical data

This step build the `canonical` key aggregates data from the various present sources. You need node.js to run this step.

```bash
npm install
node generate_canonical.js ../open-software-base-yaml
```

# Open Sofware Base

The generated database is the [Open Sofware Base (in YAML format)](https://git.framasoft.org/codegouv/open-software-base-yaml).
