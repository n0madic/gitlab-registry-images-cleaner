# Gitlab registry images cleaner

## Introduction
*gitlab-registry-images-cleaner* is a tool for deleting Docker images in Gitlab Docker registry.
Tested on Python 3 and Gitlab 11.10.

## Usage

### Command Line Interface
```
usage: gricleaner.py [-h] [-i FILE] [-j URL] [-u NAME] [-p SECRET] [-g URL]
                     [-r namespace/project] [-t SNAPSHOT] [-mr] [-mn] [-m X]
                     [-d X] [--clean-all] [--dry-run] [-v] [-z] [--debug]

Utility to remove Docker images from the Gitlab registry

optional arguments:
  -h, --help            show this help message and exit
  -i FILE, --ini FILE   use this INI file (default: gricleaner.ini)
  -j URL, --jwt URL     Gitlab JWT authentication url. Or use $GITLAB_JWT_URL. (overrides INI value)
  -u NAME, --user NAME  Gitlab admin username. Or use $GITLAB_USER. (overrides INI value)
  -p SECRET, --password SECRET
                        Gitlab admin password. NOT SAFE! Or use $GITLAB_PASSWORD. (overrides INI value)
  -g URL, --registry URL
                        Gitlab docker registry url. Or use $GITLAB_REGISTRY. (overrides INI value)
  -r namespace/project, --repository namespace/project
                        scan only these repositories (one or more)
  -t SNAPSHOT, --tag-match SNAPSHOT
                        only consider tags containing the string or regex (with --match-regex flag)
  -mr, --match-regex    Match tags by regex
  -mn, --match-negate   Negate matched tags (tag should NOT match)
  -m X, --minimum X     minimum allowed number of images in repository (overrides INI value)
  -d X, --days X        delete images older than this time (overrides INI value)
  --clean-all           delete all images in repository (DANGER!)
  --dry-run             not delete actually
  -v, --verbose         verbose mode
  -z, --insecure        disable SSL certificate verification
  --debug               debug output

To work requires settings in the INI file or environment variables
```

### Final disk cleanup

`gitlab-registry-images-cleaner` only "soft" deletes the images. Their data (image layers) are still stored.
To delete those, you must run Docker registry GC. With GitLab omnibus package, it's possible with the following commands:

```bash
sudo gitlab-ctl registry-garbage-collect
```