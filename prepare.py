from collections import defaultdict
import csv
import os
from typing import TypedDict, List, Dict, DefaultDict, cast, Union
from enum import Enum
from os import path

class GcjFileSolution(Enum):
    SMALL = 0
    LARGE = 1


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
    java_files: DefaultDict[Username, List[GcjFile]]
    c_files: DefaultDict[Username, List[GcjFile]]


# task mapping 6254486
TASK_MAPPING: Dict[str, GcjMapping] = {
    '5634697451274240': {
        'name': "Qualification Round -- Revenge of the Pancakes",
        'java_files': defaultdict(lambda: []),
        'c_files': defaultdict(lambda: [])
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
        # file['solution'] == '0' TODO: separate solution
        if __is_known_java(file) and __usable_java(file):
            TASK_MAPPING[file['task']]['java_files'][file['username']].append(file)
        elif __is_known_c(file) and __usable_c(file):
            TASK_MAPPING[file['task']]['c_files'][file['username']].append(file)


def for_file(path_prefix: str, solution: int, files: List[GcjFile]) -> None:
    for file in filter(lambda f: f['solution'] == str(solution), files):
        target = os.path.join(
            path_prefix, 'large' if file['solution'] == '1' else 'small')
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, os.path.basename(file['full_path'])), 'w') as f:
            f.write(file['flines'])


def interactive_search() -> None:
    """Old Test method I used for searching through the solutions and identify first patterns
    """
    while True:
        phrase = input()
        print(f'searching user or phrase "{phrase}"')
        results = list(filter(lambda elem: elem[0].lower() == phrase.lower(
        ), TASK_MAPPING['5634697451274240']['java_files'].items()))
        if len(results) == 0:
            print('no users. Searching for file content')
            results = list(
                filter(
                    lambda xs: any(
                        phrase.lower() in x['flines'].lower() for x in xs[1]),
                    TASK_MAPPING['5634697451274240']['java_files'].items()
                )
            )
        print(f'found {len(results)}')
        input()
        for x in results:
            for ls in x[1]:
                print(ls['flines'])


def process_task_mapping() -> None:
    for key, value in TASK_MAPPING.items():
        print(f'  * {value["name"]}')
        print(f'    - [java] {len(value["java_files"])} users')
        print(f'    - [c]    {len(value["c_files"])} users')
        extract_task(value)


# todo: allow to configure output path relative to start
def extract_task(value: GcjMapping) -> None:
    prefix = path.join("gcj", value["name"])
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    extract_file(prefix, value, "java")
    extract_file(prefix, value, "c")


def extract_file(prefix: str, value: GcjMapping, file_type: str):
    assert file_type == "java" or file_type == "c"
    prefix = path.join(prefix, file_type)
    os.makedirs(prefix, exist_ok=True, mode=0o777)
    for user, files in value[f'{file_type}_files'].items():
        user_prefix = path.join(prefix, user)
        os.makedirs(user_prefix, exist_ok=True, mode=0o777)
        for_file(user_prefix, 1, files)
        for_file(user_prefix, 0, files)


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        exit(f'{sys.argv[0]} <file>')
    print(f'loading by {sys.argv[0]} for {sys.argv[1]}')
    csvs = load_csv(sys.argv[1])
    assign_csv(csvs)
    print(f'loaded with {len(csvs)} entries')
    process_task_mapping()

    try:
        interactive_search()
    except EOFError:
        print('interaction session disabled')
