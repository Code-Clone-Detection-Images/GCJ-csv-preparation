import csv
import multiprocessing.dummy
import os
import random
import string
import re
import subprocess
import tempfile
from collections import defaultdict
from enum import Enum
from itertools import product
from os import path
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


def load_task_mapping(configuration_file: str) -> Tuple[Dict[str, GcjMapping], Dict[str, Union[int, bool]]]:
    with open(configuration_file, 'r') as f:
        raw_mapping = yaml.safe_load(f)
        # use the old-school mapping stuff
        mapping = []
        for rm, rk in raw_mapping['problems'].items():
            mapping.append((rk['round'], rk['task'], rm))
        return __make_mapping(mapping), {
            'pick-random': int(raw_mapping['pick-random']),
            'do-compile': bool(raw_mapping['do-compile']),
            'multithreading-poolsize': int(raw_mapping['multithreading-poolsize']),
        }


# task mapping
TASK_MAPPING: Dict[str, GcjMapping]
CONFIGURATION = {
    'pick-random': 100,
    'do-compile': True,
    'multithreading-poolsize': 15
}


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


# exclude line terminators, as they ar not part of the name :)
JAVA_EXTRACT_FILENAME = re.compile(r"class\s+(?P<name>[$_A-Za-z][$_A-Za-z0-9]*)")


def random_class_name(length):
    assert length > 0
    letters = string.ascii_letters + string.digits
    # ensure the first one is a valid uppercase letter, we do not use dollar or underscore for that matter
    return random.choice(string.ascii_uppercase) + ''.join(random.choice(letters) for _ in range(length - 1))


def __replace_class_name(match, cls_name) -> str:
    return f"{match.group(1)}{cls_name}{match.group(2)}"


def __run_java(java_file: GcjFile) -> bool:
    """Return true only if the java program can be compiled without extra work"""
    # produce a temporary file, but keep the name of the file
    fln = JAVA_EXTRACT_FILENAME.search(java_file['flines'])
    if not fln:
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        fname = random_class_name(25)
        java_file['file'] = f"{fname}.java"
        # update the class name
        java_file['flines'] = re.sub(f"([^A-Za-z0-9]){fln.group('name')}([^A-Za-z0-9])",
                                     lambda m: __replace_class_name(m, fname), java_file['flines'])
        with open(os.path.join(tmpdir, fname + '.java'), 'w') as fl:
            fl.write(java_file['flines'])
            try:
                subprocess.check_call(['/usr/bin/env', 'bash', '/check_compile_java.sh', fl.name], stdout=sys.stdout,
                                      stderr=sys.stderr)
                return True
            except subprocess.CalledProcessError:
                # call did fail
                print(f"Can not compile {java_file['file']} skipping", flush=True)
                return False


def __usable_java(java_file: GcjFile) -> bool:
    """To be usable, a java file must only contain import statements that are part of the standard.
       We may permit package declarations and remove them if necessary with each tool."""
    return __is_known_java(java_file) and (not CONFIGURATION['do-compile'] or __run_java(java_file))


# OLD: we restrict ourselves to files that use system.in and system.out


def __is_c(name: str) -> bool:
    return name.lower().endswith(('.c', '.cpp', '.h', '.hpp'))


def __is_known_c(c_file: GcjFile) -> bool:
    return __build_file_id(c_file) in TASK_MAPPING and (__is_c(c_file['full_path']) or __is_c(c_file['file']))


__usable_c = __is_known_c


def __assign_single(f: GcjFile) -> None:
    suffix = 'small' if f['solution'] == '0' else 'large' if f['solution'] == '1' else 'other'
    if __usable_c(f):  # if we check c first, we may avoid some compiles if methods change
        # NOTE: we adapt the filename for we have consistent usage with the java renaming strategy for agec
        f['file'] = os.path.basename(f['full_path'] if f['full_path'] else f['file'].lower())
        TASK_MAPPING[__build_file_id(f)][f'c_{suffix}_files'][f['username']].append(f)  # type: ignore
    elif __usable_java(f):
        TASK_MAPPING[__build_file_id(f)][f'java_{suffix}_files'][f['username']].append(f)  # type: ignore


def assign_csv(files: List[GcjFile]) -> None:
    pool = multiprocessing.dummy.Pool(CONFIGURATION['multithreading-poolsize'])
    pool.map(__assign_single, files)
    pool.close()
    pool.join()


def __dump_task_mapping(m: GcjMapping, lang: str) -> str:
    f = "_files"  # suppressing 'too long lines :)
    return f'{len(m[lang + "_small" + f])}/{len(m[lang + "_large" + f])}/{len(m[lang + "_other" + f])}'  # type: ignore


def process_task_mapping() -> None:
    for key, value in TASK_MAPPING.items():
        print(f'  * {value["name"]}', flush=True)
        print(f'    - [java] {__dump_task_mapping(value, "java")} users  (small / large / other)', flush=True)
        print(f'    - [c]    {__dump_task_mapping(value, "c")} users  (small / large / other)', flush=True)
        extract_task(value)


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
    # instead of random.choices we use one shuffle and pick from the start, this is faster than iterated random perm.
    users = list(value[f'{file_type}_{solution_string}_files'].items())  # type: ignore
    random.shuffle(users)
    for user, files in users[0:CONFIGURATION['pick-random']] if CONFIGURATION['pick-random'] != 0 else users:
        # NOTE: we sanitize this username to prevent problems with path injects
        user_prefix = path.join(prefix, user.replace('/', '__').replace('\\', '~~'))
        os.makedirs(user_prefix, exist_ok=True, mode=0o777)
        for_file(user_prefix, files, file_type == 'c')  # only sanitize c-files for CCCD atm


def for_file(path_prefix: str, files: List[GcjFile], sanitize_name: bool = False) -> None:
    # Note: because more modern GCJs supply multiple problems sizes but do no longer encode them uniformly,
    # for "other" problems we only select one solution id as they are the same most of the time
    selected_solution = random.choice(tuple(set(map(lambda x: x['solution'], files))))
    for f in filter(lambda x: x['solution'] == selected_solution, files):
        target = os.path.join(path_prefix, decode_solution(f['solution']))
        os.makedirs(target, exist_ok=True)
        filename = os.path.basename(f['file'])
        if sanitize_name:  # spaces, braces etc. are a problem. some tools like CCCD do not allow them
            filename = filename.replace(' ', '-').replace('(', '_').replace(')', '_')
        with open(os.path.join(target, filename), 'w') as fl:
            fl.write(f['flines'])


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        exit(f'{sys.argv[0]} <configuration.yaml> <files...>')

    print("==== Loading Configuration")
    TASK_MAPPING, CONFIGURATION = load_task_mapping(sys.argv[1])
    print('mapping: ', TASK_MAPPING)
    print('configuration: ', CONFIGURATION)

    csvs = []
    print("==== Loading CSVs")
    for file in sys.argv[2:]:
        print(f'loading by {sys.argv[0]} for {file}', flush=True)
        csvs.extend(load_csv(file))

    print("==== Assigning CSVs (this may take a while, compiling...)", flush=True)
    assign_csv(csvs)
    print(f'loaded with {len(csvs)} entries', flush=True)

    print(f"==== Process Task Mapping [Pick: {CONFIGURATION['pick-random']}]", flush=True)
    process_task_mapping()
