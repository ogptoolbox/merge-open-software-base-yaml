# merge-open-software-base-yaml

Merge [YAML files describing software products](https://framagit.org/groups/codegouv)
harvested from various open data sources. Generate an open database of software (in YAML
format).

Each set of YAML file is stored in a git repository and updated by a
dedicated script. For instance the [nuit-debout-yaml](https://framagit.org/codegouv/nuit-debout-yaml)
YAML files are generated by the [nuit-debout-to-yaml](https://framagit.org/codegouv/nuit-debout-to-yaml)
script. The semantic of the YAML is specific to each source and no attempt is made to unify them.

## Usage

Step 1 and step 2 must be applied both before commiting, in order to preserve history.

```bash
git clone https://git.framasoft.org/codegouv/merge-open-software-base-yaml.git
cd merge-open-software-base-yaml
```

### Step 0: Install dependencies

```bash
pip install -r requirements.txt
```

> Use `--user` option if relevant, or work in a [virtual env](https://github.com/berdario/pew).

### Step 1: merge YAML files

```bash
./merge.py all ../ merged-yaml/
```

### Step 2: Add canonical attributes

```bash
./generate_canonical.py merged-yaml/ ../open-software-base-yaml/
```

### Optional Step 3: generate CSV files from YAML files

```bash
./canonical_yaml_to_csv.py ../open-software-base-yaml/ ./
```

# Open Sofware Base

The generated database is the [Open Sofware Base (in YAML format)](https://git.framasoft.org/codegouv/open-software-base-yaml).

