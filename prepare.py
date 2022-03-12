from collections import defaultdict
import csv
import os
from itertools import product
from enum import Enum
from typing import TypedDict, List, Dict, DefaultDict, cast, Tuple, Union
from os import path


class GcjFileSolution(Enum):
    SMALL = '0'
    LARGE = '1'


class GcjFile(TypedDict):
    full_path: str
    file: str  # for 2019
    username: str
    flines: str
    year: str
    task: str
    round: str
    solution: GcjFileSolution  # 1 large; 0 small


Username = str


class GcjMapping(TypedDict):
    name: str
    java_small_files: DefaultDict[Username, List[GcjFile]]
    java_large_files: DefaultDict[Username, List[GcjFile]]
    c_small_files: DefaultDict[Username, List[GcjFile]]
    c_large_files: DefaultDict[Username, List[GcjFile]]


def __build_file_id(file: GcjFile) -> str:
    return f"{file['round']}::{file['task']}"


# round | task | name
def __make_mapping(sources: List[Tuple[Union[int, str], Union[int, str], str]]) -> Dict[str, GcjMapping]:
    ret: Dict[str, GcjMapping] = {}
    for mapping in sources:
        ret[f"{mapping[0]}::{mapping[1]}"] = {
            'name': mapping[2],
            'java_small_files': defaultdict(lambda: []),
            'java_large_files': defaultdict(lambda: []),
            'c_small_files': defaultdict(lambda: []),
            'c_large_files': defaultdict(lambda: [])
        }
    return ret


# task mapping
TASK_MAPPING: Dict[str, GcjMapping] = __make_mapping([
    (6254486, 5634697451274240, '2016 Qualification Round -- Revenge of the Pancakes'),
    (4304486, 5631989306621952, '2016 Round 1A -- The Last Word'),
    (6254486, 5652388522229760, '2016 Qualification Round -- Counting Sheep'),
    (4314486, 5753053697277952, '2016 Round 1C -- Senate Evacuation'),
    (3224486, 5125089213284352, '2016 Round 3 -- Forest University'),
    (7234486, 5751639981948928, '2016 Finals -- Family Hotel'),
    ('000000000019fd74', '00000000002b1353', '2020 Round 1A -- Pattern Matching'),
    ('0000000000051705', '00000000000881da', '2019 Qualification Round -- You Can Go Your Own Way'),
    ('000000000019fd27', '000000000020993c', '2020 Qualification Round -- Vestigium (only one problem set)')
])


def cleanse_line(line: str) -> str:
    return line.replace('\n', '\\n')


def load_csv(file: str) -> List[GcjFile]:
    with open(file, 'r', encoding='utf-8') as csv_file:
        reader = csv.DictReader((line.replace('\0', '') for line in csv_file),
                                delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        return cast(List[GcjFile], list(reader))


def __is_known_java(file: GcjFile) -> bool:
    return __build_file_id(file) in TASK_MAPPING and (file['full_path'].lower().endswith('.java') or file['file'].lower().endswith('.java'))


def __usable_java(file: GcjFile) -> bool:
    # OLD: we restrict ourselves to files that use system.in and system.out
    return True  # 'System.in' in file['flines'] and 'System.out' in file['flines']


def __is_known_c(file: GcjFile) -> bool:
    return __build_file_id(file) in TASK_MAPPING and ((
            # well...
            file['full_path'].lower().endswith('.c') or
            file['full_path'].lower().endswith('.cpp') or
            file['full_path'].lower().endswith('.h ') or
            file['full_path'].lower().endswith('.hpp'))
            or
            (
            # well...
            file['file'].lower().endswith('.c') or
            file['file'].lower().endswith('.cpp') or
            file['file'].lower().endswith('.h ') or
            file['file'].lower().endswith('.hpp'))
    )


def __usable_c(file: GcjFile) -> bool:
    # do not redirect but read
    return True  # 'scan' in file['flines'] and 'print' in file['flines'] and 'freopen' not in file['flines']


def assign_csv(files: List[GcjFile]):
    for file in files:
        suffix = 'small' if file['solution'] == '0' else 'large'
        if __is_known_java(file) and __usable_java(file):
            TASK_MAPPING[__build_file_id(file)][f'java_{suffix}_files'][file['username']].append(file)  # type: ignore
        elif __is_known_c(file) and __usable_c(file):
            TASK_MAPPING[__build_file_id(file)][f'c_{suffix}_files'][file['username']].append(file)  # type: ignore


def process_task_mapping() -> None:
    for key, value in TASK_MAPPING.items():
        print(f'  * {value["name"]}')
        print(
            f'    - [java] {len(value["java_small_files"])} / {len(value["java_large_files"])} users  (small / large)')
        print(
            f'    - [c]    {len(value["c_small_files"])} / {len(value["c_large_files"])} users  (small / large')
        extract_task(value)


# todo: allow to configure output path relative to start
def extract_task(value: GcjMapping) -> None:
    prefix = path.join("gcj", value["name"])
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    file_combs = (["java", "c"], [
        GcjFileSolution.SMALL, GcjFileSolution.LARGE])
    for combs in product(*file_combs):
        extract_file(prefix, value, combs[0], combs[1])


def extract_file(prefix: str, value: GcjMapping, file_type: str, solution: GcjFileSolution):
    assert file_type == "java" or file_type == "c"
    solution_string = "small" if solution == GcjFileSolution.SMALL else "large"
    prefix = path.join(prefix, file_type + "-" + solution_string)
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    for user, files in value[f'{file_type}_{solution_string}_files'].items():  # type: ignore
        user_prefix = path.join(prefix, user.replace('/', '__').replace('\\', '~~'))  # NOTE: we sanitize this username to prevent problems with path injects
        os.makedirs(user_prefix, exist_ok=True, mode=0o777)
        for_file(user_prefix, 1, files, file_type == 'c')
        for_file(user_prefix, 0, files, file_type == 'c')
# TODO: separate small and large solutions


def for_file(target: str, solution: int, files: List[GcjFile], sanitize: bool = False) -> None:
    for file in files:
        os.makedirs(target, exist_ok=True)
        filename = os.path.basename(file['full_path'] if file['full_path'] else file['file'].lower())
        if sanitize:  # spaces, braces etc are a problem. some tools like cccd do not allow them
            filename = filename.replace(' ', '-').replace('(', '_').replace(')', '_')
        with open(os.path.join(target, filename), 'w') as f:
            f.write(file['flines'])


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        exit(f'{sys.argv[0]} <files...>')
    csvs = []
    for file in sys.argv[1:]:
        print(f'loading by {sys.argv[0]} for {file}')
        csvs.extend(load_csv(file))
    assign_csv(csvs)
    print(f'loaded with {len(csvs)} entries')
    process_task_mapping()


# TODO: iterate over all 'solutions' as they are different => we have to collect all of them.