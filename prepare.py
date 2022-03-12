import csv
import os
from collections import defaultdict
from enum import Enum
from itertools import product
from os import path
import random
from typing import TypedDict, List, Dict, DefaultDict, cast, Tuple, Union
import yaml


class GcjFileSolution(Enum):
    """We use this to decode several solution types"""
    SMALL = '0'
    LARGE = '1'
    OTHER = '_'


def decode_solution(sol: GcjFileSolution) -> str:
    """convenience method to stay compatible with different google code jam formats"""
    if sol == GcjFileSolution.SMALL:
        return 'small'
    elif sol == GcjFileSolution.LARGE:
        return 'large'
    else:
        return str(sol)


class GcjFile(TypedDict):
    full_path: str
    file: str  # e.g., for 2019
    username: str
    flines: str
    year: str
    task: str
    round: str
    solution: GcjFileSolution


Username = str
RoundName = str


class GcjMapping(TypedDict):
    name: RoundName
    java_small_files: DefaultDict[Username, List[GcjFile]]
    java_large_files: DefaultDict[Username, List[GcjFile]]
    java_other_files: DefaultDict[Username, List[GcjFile]]
    c_small_files: DefaultDict[Username, List[GcjFile]]
    c_large_files: DefaultDict[Username, List[GcjFile]]
    c_other_files: DefaultDict[Username, List[GcjFile]]


def __build_file_id(fs: GcjFile) -> str:
    return f"{fs['round']}::{fs['task']}"


# round | task | name
def __make_mapping(sources: List[Tuple[Union[int, str], Union[int, str], RoundName]]) -> Dict[str, GcjMapping]:
    ret: Dict[str, GcjMapping] = {}
    for mapping in sources:
        ret[f"{mapping[0]}::{mapping[1]}"] = GcjMapping(name=mapping[2], java_small_files=defaultdict(lambda: []),
                                                        java_large_files=defaultdict(lambda: []),
                                                        java_other_files=defaultdict(lambda: []),
                                                        c_small_files=defaultdict(lambda: []),
                                                        c_large_files=defaultdict(lambda: []),
                                                        c_other_files=defaultdict(lambda: []))
    return ret


def load_task_mapping(configuration_file: str) -> Dict[str, GcjMapping]:
    with open(configuration_file, 'r') as f:
        raw_mapping = yaml.safe_load(f)
        # use the old-school mapping stuff
        mapping = []
        for rm, rk in raw_mapping['problems'].items():
            mapping.append((rk['round'], rk['task'], rm))
        return __make_mapping(mapping)


# task mapping
TASK_MAPPING: Dict[str, GcjMapping]


def cleanse_line(line: str) -> str:
    return line.replace('\n', '\\n')


def load_csv(csv_file: str) -> List[GcjFile]:
    with open(csv_file, 'r', encoding='utf-8') as csv_file:
        reader = csv.DictReader((line.replace('\0', '') for line in csv_file), delimiter=',', quotechar='"',
                                quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        return cast(List[GcjFile], list(reader))


def __is_java(name: str) -> bool:
    return name.lower().endswith('.java')


def __is_known_java(java_file: GcjFile) -> bool:
    return __build_file_id(java_file) in TASK_MAPPING and (
            __is_java(java_file['full_path']) or __is_java(java_file['file']))


__usable_java = __is_known_java


# OLD: we restrict ourselves to files that use system.in and system.out


def __is_c(name: str) -> bool:
    return name.lower().endswith(('.c', '.cpp', '.h', '.hpp'))


def __is_known_c(c_file: GcjFile) -> bool:
    return __build_file_id(c_file) in TASK_MAPPING and (__is_c(c_file['full_path']) or __is_c(c_file['file']))


__usable_c = __is_known_c


def assign_csv(files: List[GcjFile]):
    for f in files:
        suffix = 'small' if f['solution'] == '0' else 'large' if f['solution'] == '1' else 'other'
        if __usable_java(f):
            TASK_MAPPING[__build_file_id(f)][f'java_{suffix}_files'][f['username']].append(f)  # type: ignore
        elif __usable_c(f):
            TASK_MAPPING[__build_file_id(f)][f'c_{suffix}_files'][f['username']].append(f)  # type: ignore


def __dump_task_mapping(m: GcjMapping, lang: str) -> str:
    f = "_files"  # suppressing 'too long lines :)
    return f'{len(m[lang + "_small" + f])}/{len(m[lang + "_large" + f])}/{len(m[lang + "_other" + f])}'  # type: ignore


def process_task_mapping() -> None:
    for key, value in TASK_MAPPING.items():
        print(f'  * {value["name"]}')
        print(f'    - [java] {__dump_task_mapping(value, "java")} users  (small / large / other)')
        print(f'    - [c]    {__dump_task_mapping(value, "c")} users  (small / large / other)')
        extract_task(value)


# todo: allow to configure output path relative to start
def extract_task(value: GcjMapping) -> None:
    prefix = path.join("gcj", value["name"])
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    file_combs = (["java", "c"], [GcjFileSolution.SMALL, GcjFileSolution.LARGE, GcjFileSolution.OTHER])
    for combs in product(*file_combs):
        extract_file(prefix, value, combs[0], combs[1])


def decode_solution_string(sol: GcjFileSolution) -> str:
    if sol == GcjFileSolution.SMALL:
        return 'small'
    elif sol == GcjFileSolution.LARGE:
        return 'large'
    else:
        return 'other'


def extract_file(prefix: str, value: GcjMapping, file_type: str, solution: GcjFileSolution):
    assert file_type == "java" or file_type == "c"
    solution_string = decode_solution_string(solution)
    prefix = path.join(prefix, file_type + "-" + solution_string)
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    for user, files in value[f'{file_type}_{solution_string}_files'].items():  # type: ignore
        # NOTE: we sanitize this username to prevent problems with path injects
        user_prefix = path.join(prefix, user.replace('/', '__').replace('\\', '~~'))
        os.makedirs(user_prefix, exist_ok=True, mode=0o777)
        for_file(user_prefix, files, file_type == 'c')  # only sanitize c-files for CCCD atm


def for_file(path_prefix: str, files: List[GcjFile], sanitize: bool = False) -> None:
    # Note: because more modern GCJs supply multiple problems sizes but do no longer encode them uniformly,
    # for "other" problems we only select one solution id as they are the same most of the time
    selected_solution = random.choice(tuple(set(map(lambda x: x['solution'], files))))
    for f in filter(lambda x: x['solution'] == selected_solution, files):
        target = os.path.join(path_prefix, decode_solution(f['solution']))
        os.makedirs(target, exist_ok=True)
        filename = os.path.basename(f['full_path'] if f['full_path'] else f['file'].lower())
        if sanitize:  # spaces, braces etc. are a problem. some tools like CCCD do not allow them
            filename = filename.replace(' ', '-').replace('(', '_').replace(')', '_')
        with open(os.path.join(target, filename), 'w') as fl:
            fl.write(f['flines'])


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        exit(f'{sys.argv[0]} <configuration.yaml> <files...>')

    print("==== Loading Configuration")
    TASK_MAPPING = load_task_mapping(sys.argv[1])

    csvs = []
    print("==== Loading CSVs")
    for file in sys.argv[2:]:
        print(f'loading by {sys.argv[0]} for {file}', flush=True)
        csvs.extend(load_csv(file))

    print("==== Assigning CSVs", flush=True)
    assign_csv(csvs)
    print(f'loaded with {len(csvs)} entries', flush=True)

    print("==== Process Task Mapping", flush=True)
    process_task_mapping()
