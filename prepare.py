from collections import defaultdict
import csv
import os
from typing import TypedDict, List, Dict, DefaultDict, cast
from itertools import product
from enum import Enum
from os import path


class GcjFileSolution(Enum):
    SMALL = '0'
    LARGE = '1'


class GcjFile(TypedDict):
    full_path: str
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


# task mapping 6254486
TASK_MAPPING: Dict[str, GcjMapping] = {
    '5634697451274240': {
        'name': "Qualification Round -- Revenge of the Pancakes",
        'java_small_files': defaultdict(lambda: []),
        'java_large_files': defaultdict(lambda: []),
        'c_small_files': defaultdict(lambda: []),
        'c_large_files': defaultdict(lambda: [])
    }
}


def cleanse_line(line: str) -> str:
    return line.replace('\n', '\\n')


def load_csv(file: str) -> List[GcjFile]:
    with open(file, 'r', encoding='utf-8') as csv_file:
        reader = csv.DictReader((line.replace('\0', '') for line in csv_file),
                                delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        return cast(List[GcjFile], list(reader))


def __is_known_java(file: GcjFile) -> bool:
    return file['task'] in TASK_MAPPING and file['full_path'].endswith('.java')


def __usable_java(file: GcjFile) -> bool:
    # we restrict ourselves to files that use system.in and system.out
    return 'System.in' in file['flines'] and 'System.out' in file['flines']


def __is_known_c(file: GcjFile) -> bool:
    return file['task'] in TASK_MAPPING and file['full_path'].endswith('.c')


def __usable_c(file: GcjFile) -> bool:
    # do not redirect but read
    return 'scan' in file['flines'] and 'print' in file['flines'] and 'freopen' not in file['flines']


def assign_csv(files: List[GcjFile]):
    for file in files:
        suffix = 'small' if file['solution'] == '0' else 'large'
        if __is_known_java(file) and __usable_java(file):
            TASK_MAPPING[file['task']
                         ][f'java_{suffix}_files'][file['username']].append(file)
        elif __is_known_c(file) and __usable_c(file):
            TASK_MAPPING[file['task']
                         ][f'c_{suffix}_files'][file['username']].append(file)


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
    file_combs = [["java", "c"], [
        GcjFileSolution.SMALL, GcjFileSolution.LARGE]]
    for combs in product(*file_combs):
        extract_file(prefix, value, combs[0], combs[1])


def extract_file(prefix: str, value: GcjMapping, file_type: str, solution: GcjFileSolution):
    assert file_type == "java" or file_type == "c"
    solution_string = "small" if solution == GcjFileSolution.SMALL else "large"
    prefix = path.join(prefix, file_type + "-" + solution_string)
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    for user, files in value[f'{file_type}_{solution_string}_files'].items():
        user_prefix = path.join(prefix, user)
        os.makedirs(user_prefix, exist_ok=True, mode=0o777)
        for_file(user_prefix, 1, files, file_type == 'c')
        for_file(user_prefix, 0, files, file_type == 'c')


def for_file(path_prefix: str, solution: int, files: List[GcjFile], kill_space: bool = False) -> None:
    for file in filter(lambda f: f['solution'] == str(solution), files):
        target = os.path.join(
            path_prefix, 'large' if file['solution'] == '1' else 'small')
        os.makedirs(target, exist_ok=True)
        filename = os.path.basename(file['full_path'])
        if kill_space:  # spaces are a problem. some tools like cccd do not allow them
            filename = filename.replace(' ', '-')
        with open(os.path.join(target, ), 'w') as f:
            f.write(file['flines'])


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        exit(f'{sys.argv[0]} <file>')
    print(f'loading by {sys.argv[0]} for {sys.argv[1]}')
    csvs = load_csv(sys.argv[1])
    assign_csv(csvs)
    print(f'loaded with {len(csvs)} entries')
    process_task_mapping()
