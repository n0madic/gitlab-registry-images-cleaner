# Gitlab registry images cleaner

```
usage: gricleaner.py [-h] [-i FILE] [-r namespace/project] [-m X] [-d X]
                     [--clean-all] [--dry-run] [--debug]

Utility to remove Docker images from the Gitlab registry

optional arguments:
  -h, --help            show this help message and exit
  -i FILE, --ini FILE   use this INI file (default: gricleaner.ini)
  -r namespace/project, --repository namespace/project
                        scan only this repository
  -m X, --minimum X     minimum allowed number of images in repository (overrides INI value)
  -d X, --days X        delete images older than this time (overrides INI value)
  --clean-all           delete all images in repository (DANGER!)
  --dry-run             not delete actually
  --debug               debug output

To work requires settings in the INI file
```
