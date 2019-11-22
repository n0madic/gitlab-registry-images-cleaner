# Gitlab registry images cleaner

## Introduction
*gitlab-registry-images-cleaner* is a tool for deleting Docker images in Gitlab Docker registry.
Tested on Python 3 and Gitlab 11.10.

## Usage

### Command Line Interface
```
usage: gricleaner.py [-h] [-i FILE] [-j URL] [-u NAME] [-p SECRET] [-g URL]
                     [-r namespace/project] [-t SNAPSHOT] [-mr] [-mn] [-m X]
                     [-d X] [--clean-latest] [--clean-all] [--single-tag]
                     [--dry-run] [-z] [-v] [--debug]

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
  -mr, --match-regex    match tags by regex
  -mn, --match-negate   negate matched tags (tag should NOT match)
  -m X, --minimum X     minimum allowed number of images in repository (overrides INI value)
  -d X, --days X        delete images older than this time (overrides INI value)
  --clean-latest        also clean 'latest' tags (by default they're excluded from removal)
  --clean-all           delete all images in repository (DANGER!)
  --single-tag          only delete images with one tag (no 'co-tag' delete)
  --preserve-tags       preserve images used by given tags (example --preserve-tags=master,prod,staging,latest)
  --dry-run             not delete actually
  -z, --insecure        disable SSL certificate verification
  -v, --verbose         verbose mode
  --debug               debug output

To work requires settings in the INI file or environment variables
```

### Final disk cleanup

`gitlab-registry-images-cleaner` only "soft" deletes the images. Their data (image layers) are still stored.
To delete those, you must run Docker registry GC. With GitLab omnibus package, it's possible with the following commands:

```bash
sudo gitlab-ctl registry-garbage-collect -m
```

### Use Docker image

```
docker pull n0madic/gricleaner:latest
docker run --rm -e GITLAB_REGISTRY -e GITLAB_JWT_URL -e GITLAB_USER -e GITLAB_PASSWORD n0madic/gricleaner:latest -r group/project ...
```
