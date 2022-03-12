# GCJ-Prepare

Preparation script to extract folders containing separated solutions for each task and solution size.

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
