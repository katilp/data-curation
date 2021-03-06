import os
import sys
import subprocess
import json
import re
from utils import get_from_deep_json, \
                  get_dataset_year, \
                  get_dataset_format
from das_json_store import get_das_store_json
from eos_store import check_datasets_in_eos_dir


def mcm_downloader(prepid, dataset, mcm_dir, das_dir):
    "Query dictionary and setup script from McM database"
    # this function is so ugly... but finally works! You're welcome to refactor it though

    cmd = "curl -s -k https://cms-pdmv.cern.ch/mcm/public/restapi/requests/{query}/{prepId}"

    # As prep_id in DAS for some datasets can be found with underscores and MCM
    # takes without underscores, we need to process prep_id removing all of them
    if "_" in prepid:
        print("Found some underscores in prep_id: " + prepid + ", removing...")
        prepid = prepid.replace("_", "")

    mcm_dict = subprocess.run(cmd.format(query="get", prepId=prepid),
                              shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    mcm_script = subprocess.run(cmd.format(query="get_setup", prepId=prepid),
                                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    mcm_dict_out = str(mcm_dict.stdout.decode("utf-8"))
    mcm_script_out = str(mcm_script.stdout.decode("utf-8"))

    # check if results are not empty
    if mcm_dict_out == '{"results": {}}\n':
        print("[ERROR] Empty McM dict (get) for {ds}".format(ds=dataset),
              file=sys.stderr)
    else:
        outfile = mcm_dir + "/dict/" + dataset.replace('/', '@') + ".json"
        with open(outfile, 'w') as dict_file:
                dict_file.write(mcm_dict_out)

    if mcm_script_out == '' or mcm_script_out[0] == '{':
        print("[ERROR] Empty McM script (get_setup) for {ds}".format(ds=dataset),
              file=sys.stderr)
    else:
        outfile = mcm_dir + "/scripts/" + dataset.replace('/', '@') + ".sh"
        with open(outfile, 'w') as dict_file:
                dict_file.write(mcm_script_out)

    # same thing for "input_dataset": hopefully the GEN-SIM step
    dataset_json = get_das_store_json(dataset, 'mcm', das_dir)
    input_dataset = get_from_deep_json(dataset_json, 'input_dataset')  # /bla/ble/GEN-SIM
    if input_dataset:
        mcm_dict = subprocess.run(cmd.format(query="produces", prepId=input_dataset[1:]),
                                 shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mcm_out = str(mcm_dict.stdout.decode("utf-8"))
        # check if results are not empty
        if mcm_out == '{"results": {}}' or mcm_out == '{"results": {}}\n':
            print("[ERROR] Empty McM dict (get) for {ds}".format(ds=input_dataset),
                  file=sys.stderr)
        else:
            outfile = mcm_dir + "/dict/" + input_dataset.replace('/', '@') + ".json"
            with open(outfile, 'w') as dict_file:
                    dict_file.write(mcm_out)

            prepid = get_prepid_from_mcm(input_dataset, mcm_dir)
            if prepid != None:
                mcm_script = subprocess.run(cmd.format(query="get_setup", prepId=prepid),
                                            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if mcm_script.stdout.decode("utf-8")[0] == '{':
                    print("[ERROR] Empty McM script (get_setup) for {ds}".format(ds=input_dataset),
                          file=sys.stderr)
                else:
                    outfile = mcm_dir + "/scripts/" + input_dataset.replace('/', '@') + ".sh"
                    with open(outfile, 'w') as dict_file:
                            dict_file.write(mcm_script.stdout.decode("utf-8"))
            else:
                print("[ERROR] No prep_id in McM Store for record {ds}".format(ds=input_dataset),
                      file=sys.stderr)
    else:
        print("[ERROR] No input_dataset in das_store/mcm for record {ds}".format(ds=dataset),
              file=sys.stderr)


def create(datasets, mcm_dir, das_dir, eos_dir, ignore_eos_store=False):
    "Get information from McM about each dataset"

    # create dirs
    for path in [mcm_dir + "/dict", mcm_dir + "/scripts"]:
        if not os.path.exists(path):
            os.makedirs(path)

    # only for datasets with EOS file information
    if ignore_eos_store:
        eos_datasets = datasets.copy()
    else:
        eos_datasets = check_datasets_in_eos_dir(datasets, eos_dir)

    total = len(eos_datasets)
    i = 1
    for dataset in eos_datasets:
        print("McM Storing ({i}/{N}) {ds}".format(i=i, N=total, ds=dataset))

        prepid = get_prepId_from_das(dataset, das_dir)
        if prepid != None:
            # query McM rest API for dictionary and setup script
            mcm_downloader(prepid, dataset, mcm_dir, das_dir)
        else:
            print("[ERROR] No prep_id for record {ds}".format(ds=dataset),
                  file=sys.stderr)

        i += 1


def get_mcm_dict(dataset, mcm_dir):
    """Return cached McM dictionary of dataset in json format"""

    filepath = mcm_dir + '/dict/' + dataset.replace('/', '@') + '.json'
    if os.path.exists(filepath) and os.stat(filepath).st_size != 0:
        with open(filepath, 'r') as filestream:
            return json.load(filestream)
    else:
        print('[ERROR] There is no McM JSON store dict for dataset ' + dataset,
              file=sys.stderr)
        return json.loads('{}')


def get_prepId_from_das(dataset, das_dir):
    "get prepid for dataset"

    # get prepid from das/dataset
    prepid = get_from_deep_json(get_das_store_json(dataset, 'dataset', das_dir), 'prep_id')

    if prepid == None:
        # try to get from das/mcm:
        prepid = get_from_deep_json(get_das_store_json(dataset, 'mcm', das_dir), 'prepid')
        # todo also try different queries from the json. prep_id?

    return prepid


def get_prepid_from_mcm(dataset, mcm_dir):
    "get prepid for dataset from McM store"

    # get prepid from das/dataset
    prepid = get_from_deep_json(get_mcm_dict(dataset, mcm_dir), 'prep_id')

    if prepid == None:
        # try different queries from the json. prep_id?
        prepid = get_from_deep_json(get_mcm_dict(dataset, mcm_dir), 'prepid')

    return prepid


def get_global_tag(dataset, mcm_dir):
    "Get global tag from McM dictionary"
    mcm_dict = get_mcm_dict(dataset, mcm_dir)
    global_tag = get_from_deep_json(mcm_dict, 'conditions')

    if not global_tag:
        global_tag = ''

    return global_tag


def get_cmssw_version_from_mcm(dataset, mcm_dir):
    "Get CMSSW version from McM dictionary"
    mcm_dict = get_mcm_dict(dataset, mcm_dir)
    cmssw = get_from_deep_json(mcm_dict, 'cmssw_release')

    if not cmssw:
        cmssw = ''

    return cmssw


def get_cmsDriver_script(dataset, mcm_dir):
    """Return path to cmsDriver script for that dataset"""
    if dataset == None:
        return None

    script = mcm_dir + '/scripts/' + dataset.replace('/', '@') + '.sh'
    if os.path.exists(script):
        return script
    else:
        return None


def get_genfragment_url(dataset, mcm_dir, das_dir):
    "return list of url's of the genfragments used"
    url = []
    script_path = get_cmsDriver_script(dataset, mcm_dir)
    if script_path == None:
        return None

    with open(script_path, 'r') as script:
        for line in script:
            if 'curl' in line:
                curl = re.search('(?P<url>https?://[^\s]+)', line)
                if curl:
                    url.append(curl.group('url'))
    return url


def get_dataset_energy(dataset, mcm_dir):
    "Return energy of that dataset in TeV"
    mcm_dict = get_mcm_dict(dataset, mcm_dir)
    if mcm_dict:
        energy = get_from_deep_json(mcm_dict, 'energy')
        if isinstance(energy, str):
            return energy
        else:
            return str(energy).replace('.0', '') + 'TeV'

    else:
        year = get_dataset_year(dataset)
        return {
               2010:  '7TeV',
               2011:  '7TeV',
               2012:  '8TeV',
               2015: '13TeV',
               2016: '13TeV',
               }.get(year, 0)


def get_generator_name(dataset, das_dir, mcm_dir):
    "Return list of generators used for that dataset"
    generator_names = []
    mcm_dict = get_mcm_dict(dataset, mcm_dir)
    generators = get_from_deep_json(mcm_dict, 'generators')

    if generators:
        for item in generators:
            for char in ['"', '\\', '[', ']']:  # remove ", \, [, ]
                item = item.replace(char, '')
            generator = item
            if generator not in generator_names:
                generator_names.append(item)

    return generator_names


def get_parent_dataset_from_mcm(dataset, das_dir, mcm_dir):
    "Return parent dataset to given DATASET from McM."
    parent_dataset = ''
    mcm_dict = get_mcm_dict(dataset, mcm_dir)
    parent_dataset = get_from_deep_json(mcm_dict, 'input_dataset')
    return parent_dataset


def get_conffile_ids_from_mcm(dataset, das_dir, mcm_dir):
    """Return location of the configuration files for the dataset from McM."""
    config_ids = []
    mcm_dict = get_mcm_dict(dataset, mcm_dir)
    config_ids = get_from_deep_json(mcm_dict, 'config_id')
    return config_ids
