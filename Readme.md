# GCJ-Prepare

Preparation script to extract folders containing separated solutions for each task and solution size. The csvs have been taken from a [GitHub-Repository](https://github.com/Jur1cek/gcj-dataset).

**Build** using the [`makefile`](makefile).
**Run** using the [run-script](run.sh) script, supply it with the [`configuration.yaml`](configuration.yaml) defining
desired projects desired `.csv`-files.

> As only the `pwd` (current working directory) will be mounted automatically,
you can not specify files/folders located in upper levels.

Example:

```bash
make
./run.sh configuration.yaml gcj2016.csv gcj2019.csv gcj2020.csv
```

After the command, you will find all prepared folders inside of [`gcj/`](gcj).

> The requirements for the [`prepare.py`] (which is run inside the docker-container) have been created
> using [pipreqs](https://pypi.org/project/pipreqs/) with `pipreqs --print > requirements.txt`.