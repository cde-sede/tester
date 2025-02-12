# shell-tester

A simple library build for recording shell commands and
testing if the output is correct.

### Usage

You start by recording a command

```
python -m tester save -a echo -a "asdf" -o echo
```

Then, to test

```
python -m tester test -s echo
```
