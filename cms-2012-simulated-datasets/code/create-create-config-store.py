#!/usr/bin/env python


"""
Create `create-config-store.sh` script to download configuration files for MC 2012 records.

# tibor@laptop> ./code/create-create-config-store.sh > ./outputs/create-config-store.sh
# cernapcms@lxplus> mkdir tibor
# tibor@laptop> scp outputs/create-config-store.sh cernapcms@lxplus.cern.ch:tibor
# cernapcms@lxplus> cd tibor
# cernapcms@lxplus> voms-proxy-init --voms cms
# cernapcms@lxplus> source ./create-config-store.sh
# tibor@laptop> mkdir -p ./inputs/config-store
# tibor@laptop> scp -r cernapcms@lxplus.cern.ch:tibor/config-store/* ./inputs/config-store
"""

import subprocess
import sys

from create_dataset_records import \
    get_from_deep_json, \
    get_das_store_json

from create_eos_file_indexes import \
    get_dataset_index_file_base


def get_conffile_ids(dataset):
    """Return location of the configuration files for the dataset."""
    ids = {}
    output = get_from_deep_json(get_das_store_json(dataset, 'config'),
                                'byoutputdataset')
    if output:
        for someid in output:
            ids[someid] = 1
    return list(ids.keys())


def main():
    "Do the job."

    dataset_full_names = []
    for line in open('./inputs/mc-datasets.txt', 'r').readlines():
        dataset_full_name = line.strip()
        dataset_index_file_base = get_dataset_index_file_base(dataset_full_name)
        if subprocess.call('ls ./inputs/eos-file-indexes/ | grep -q ' + dataset_index_file_base, shell=True):
            print('[ERROR] Missing EOS information, ignoring dataset ' + dataset_full_name,
                  file=sys.stderr)
        else:
            dataset_full_names.append(dataset_full_name)

    conffile_ids = []
    for dataset_full_name in dataset_full_names:
        for conffile_id in get_conffile_ids(dataset_full_name):
            if conffile_id not in conffile_ids:
                conffile_ids.append(conffile_id)

    print('mkdir -p config-store')
    for conffile_id in conffile_ids:
        print("curl -s -o ./config-store/%(conffile_id)s.configFile -k --key /tmp/x509up_u102955 --cert /tmp/x509up_u102955 https://cmsweb.cern.ch/couchdb/reqmgr_config_cache/%(conffile_id)s/configFile" % {'conffile_id': conffile_id})


if __name__ == '__main__':
    main()
