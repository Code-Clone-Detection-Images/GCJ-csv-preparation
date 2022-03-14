import csv
import multiprocessing
import multiprocessing.managers
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
    'multithreading-poolsize': 2 * multiprocessing.cpu_count()
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
JAVA_EXTRACT_CLASSNAMES = re.compile(r"class\s+(?P<name>[$_A-Za-z][$_A-Za-z0-9]*)")


def random_class_name(length):
    assert length > 0
    letters = string.ascii_letters + string.digits
    # ensure the first one is a valid uppercase letter, we do not use dollar or underscore for that matter
    return random.choice(string.ascii_uppercase) + ''.join(random.choice(letters) for _ in range(length - 1))


def __replace_class_name(match, cls_name) -> str:
    return f"{match.group(1)}{cls_name}{match.group(2)}"


ClassNameMapping = Dict[str, str]
FileNameMapping = Dict[str, str]


class JavaFileHasInvalidClassesException(Exception):
    pass


def __create_java_filename_mapping(java_files: List[GcjFile]) -> Tuple[FileNameMapping, ClassNameMapping]:
    file_name_mapping: FileNameMapping = {}
    class_name_mapping: ClassNameMapping = {}
    for java_file in java_files:
        # why not find all? it returns strings...
        all_classes = list(JAVA_EXTRACT_CLASSNAMES.finditer(java_file['flines']))
        if len(all_classes) == 0:
            raise JavaFileHasInvalidClassesException
        for i, c in enumerate(all_classes):
            new_name = random_class_name(25)
            if i == 0:  # use first
                file_name_mapping[java_file['file']] = new_name
            class_name_mapping[all_classes[0]['name']] = new_name

    return file_name_mapping, class_name_mapping


def __apply_java_file_mapping(java_files: List[GcjFile], mappings: Tuple[FileNameMapping, ClassNameMapping]) -> None:
    for java_file in java_files:
        # update file name
        java_file['file'] = mappings[0][java_file['file']] + ".java"
        # update all classes
        for map_from, map_to in mappings[1].items():
            java_file['flines'] = re.sub(f"([^A-Za-z0-9]){map_from}([^A-Za-z0-9])",
                                         lambda m: __replace_class_name(m, map_to), java_file['flines'])


def __run_java(java_files: List[GcjFile]) -> bool:
    """Return true only if the java program can be compiled without extra work"""
    # produce a temporary file, but keep the name of the file
    # create a mapping from old to new unique class names
    try:
        fln_mapping = __create_java_filename_mapping(java_files)
    except JavaFileHasInvalidClassesException:
        return False

    __apply_java_file_mapping(java_files, fln_mapping)
    if not CONFIGURATION['do-compile']:
        return True

    with tempfile.TemporaryDirectory() as tmpdir:
        for file in java_files:
            # write file for temp compile
            with open(os.path.join(tmpdir, file['file']), 'w') as fl:
                fl.write(file['flines'])
        filenames = list(map(lambda x: os.path.join(tmpdir, x['file']), java_files))
        try:
            subprocess.check_call(['/usr/bin/env', 'bash', '/check_compile_java.sh'] +
                                  filenames, stdout=sys.stdout, stderr=sys.stderr)
            print(f"Accepted {filenames}", flush=True)
            return True
        except subprocess.CalledProcessError:
            # call did fail
            print(f"Can not compile {filenames} skipping", flush=True)
            return False


__usable_java = __is_known_java

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
    for f in files:
        __assign_single(f)


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


def __process_for_file(lock, remaining, prefix: str, file_type: str, user: Username, files: List[GcjFile]) -> None:
    if remaining.value <= 0:
        return
    user_prefix = path.join(prefix, user.replace('/', '__').replace('\\', '~~'))
    result = for_file(user_prefix, files, file_type == 'c')
    if remaining.value > 0 and result:
        with lock:
            remaining.value -= 1


def extract_file(prefix: str, value: GcjMapping, file_type: str, solution: GcjFileSolution):
    assert file_type == "java" or file_type == "c"
    solution_string = decode_solution_string(solution)
    prefix = path.join(prefix, file_type + "-" + solution_string)
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    # instead of random.choices we use one shuffle and pick from the start, this is faster than iterated random perm.
    users = list(value[f'{file_type}_{solution_string}_files'].items())  # type: ignore
    random.shuffle(users)
    # well...
    manager = multiprocessing.Manager()
    remaining = manager.Value('remaining', CONFIGURATION['pick-random'])
    lock = manager.Lock()
    pool = multiprocessing.Pool(processes=CONFIGURATION['multithreading-poolsize'])

    args = list(map(lambda u: (lock, remaining, prefix, file_type, u[0], u[1]), users))
    pool.starmap(__process_for_file, args)
    pool.close()
    pool.join()


update_java_files_for_final = __run_java


def for_file(path_prefix: str, files: List[GcjFile], is_c_file: bool = False) -> bool:
    """Returns true, iff it is either a c file or a java file that is configured to 'must' compile and does"""
    # Note: because more modern GCJs supply multiple problems sizes but do no longer encode them uniformly,
    # for "other" problems we only select one solution id as they are the same most of the time
    selected_solution = random.choice(tuple(set(map(lambda x: x['solution'], files))))
    important_files = list(filter(lambda x: x['solution'] == selected_solution, files))
    if not is_c_file and not update_java_files_for_final(important_files):
        return False  # unwanted java file

    os.makedirs(path_prefix, exist_ok=True, mode=0o777)
    for f in important_files:
        target = os.path.join(path_prefix, decode_solution(f['solution']))
        os.makedirs(target, exist_ok=True)
        filename = os.path.basename(f['file'])
        if is_c_file:  # spaces, braces etc. are a problem. some tools like CCCD do not allow them
            filename = filename.replace(' ', '-').replace('(', '_').replace(')', '_')
        with open(os.path.join(target, filename), 'w') as fl:
            fl.write(f['flines'])
    return True


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
