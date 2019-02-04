#!/usr/bin/env python

import re
import logging
import json
import requests
import cachetools.func


class GitlabRegistryClient(object):
    """Client for Gitlab registry"""

    def __init__(self, auth, jwt, registry, requests_verify=True, dry_run=False):
        """ Initializing arguments """
        self.auth = auth
        self.jwt = jwt.rstrip('//')
        self.registry = registry.rstrip('//')
        self.requests_verify = requests_verify
        self.dry_run = dry_run

    @cachetools.func.ttl_cache(maxsize=100, ttl=10 * 60)
    def get_bearer(self, scope):
        """Return bearer token from Gitlab jwt"""
        url = "{}/?service=container_registry&scope={}:*".format(self.jwt, scope)
        response = requests.get(url, auth=self.auth, verify=self.requests_verify)
        response.raise_for_status()
        token = response.json()
        return token["token"]

    def get_json(self, path, scope):
        """Return JSON from registry"""
        headers = {"Authorization": "Bearer " + self.get_bearer(scope)}
        response = requests.get(self.registry + path, headers=headers, verify=self.requests_verify)
        if response.status_code == 200 or response.status_code == 404:
            json_r = response.json()
            if "errors" in json_r:
                if json_r["errors"][0]["message"] != "manifest unknown":
                    logging.error(json_r["errors"][0]["message"])
            return json_r
        else:
            response.raise_for_status()

    def get_catalog(self):
        """Return catalog of repositories from registry"""
        return self.get_json("/v2/_catalog", "registry:catalog")["repositories"]

    def get_tags(self, repo):
        """Return tags of repository from registry"""
        return self.get_json("/v2/{}/tags/list".format(repo),
                             "repository:" + repo)

    def get_manifest(self, repo, tag):
        """Return manifest of tag from registry"""
        return self.get_json("/v2/{}/manifests/{}".format(repo, tag),
                             "repository:" + repo)

    def get_image(self, repo, tag):
        """Return image by manifest from registry"""
        manifest = self.get_manifest(repo, tag)
        if "errors" in manifest:
            if tag != 'latest':
                logging.warning("Image {}:{} not found or already deleted: {}".format(
                    repo, tag, manifest["errors"][0]["message"]))
            return {}
        else:
            return json.loads(manifest["history"][0]["v1Compatibility"])

    def get_digest(self, repo, tag):
        """Return digest for manifest from registry"""
        path = "/v2/{}/manifests/{}".format(repo, tag)
        headers = {
            "Authorization": "Bearer " + self.get_bearer("repository:" + repo),
            "Accept": "application/vnd.docker.distribution.manifest.v2+json"
        }
        response = requests.head(self.registry + path, headers=headers, verify=self.requests_verify)
        if response.status_code == 404:
            logging.info("- Not found")
            return None

        return response.headers["Docker-Content-Digest"]

    def delete_image(self, repo, tag):
        """Delete image by tag from registry"""
        digest = self.get_digest(repo, tag)
        if digest == None:
            return False

        url = "/v2/{}/manifests/{}".format(repo, digest)
        logging.debug("Delete URL: {}{}".format(self.registry, url))
        if self.dry_run:
            logging.warning("~ Dry Run!")
        else:
            headers = {
                "Authorization": "Bearer " + self.get_bearer("repository:" + repo)
            }
            response = requests.delete(self.registry + url, headers=headers, verify=self.requests_verify)
            if response.status_code == 202:
                logging.info("+ OK")
            else:
                logging.error(response.text)

        return True

if __name__ == "__main__":
    import argparse
    import configparser
    import datetime
    import dateutil.parser
    import os
    import sys

    config_name = os.path.basename(__file__).replace(".py", ".ini")
    parser = argparse.ArgumentParser(
        description="Utility to remove Docker images from the Gitlab registry",
        epilog="To work requires settings in the INI file or environment variables",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-i",
        "--ini",
        help="use this INI file (default: {})".format(config_name),
        metavar="FILE")
    parser.add_argument(
        "-j",
        "--jwt",
        help="Gitlab JWT authentication url. Or use $GITLAB_JWT_URL. (overrides INI value)",
        metavar="URL")
    parser.add_argument(
        "-u",
        "--user",
        help="Gitlab admin username. Or use $GITLAB_USER. (overrides INI value)",
        metavar="NAME")
    parser.add_argument(
        "-p",
        "--password",
        help="Gitlab admin password. NOT SAFE! Or use $GITLAB_PASSWORD. (overrides INI value)",
        metavar="SECRET")
    parser.add_argument(
        "-g",
        "--registry",
        help="Gitlab docker registry url. Or use $GITLAB_REGISTRY. (overrides INI value)",
        metavar="URL")
    parser.add_argument(
        "-r",
        "--repository",
        action='append',
        default=[],
        help="scan only these repositories (one or more)",
        metavar="namespace/project")
    parser.add_argument(
        "-t",
        "--tag-match",
        help="only consider tags containing the string",
        metavar="SNAPSHOT")
    parser.add_argument(
        "-m",
        "--minimum",
        help="minimum allowed number of images in repository (overrides INI value)",
        metavar="X",
        type=int)
    parser.add_argument(
        "-d",
        "--days",
        help="delete images older than this time (overrides INI value)",
        metavar="X",
        type=int)
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="delete all images in repository (DANGER!)")
    parser.add_argument(
        "--dry-run", action="store_true", help="not delete actually")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="verbose mode")
    parser.add_argument(
        "-z", "--insecure", action="store_true", help="disable SSL certificate verification")
    parser.add_argument("--debug", action="store_true", help="debug output")
    args = parser.parse_args()

    log_format = "[%(asctime)s] %(levelname)-8s %(message)s"
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO, format=log_format)
        logging.getLogger("requests").setLevel(logging.WARNING)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)

    if args.ini:
        config_name = args.ini

    config = configparser.ConfigParser()
    if os.path.isfile(config_name):
        config.read(config_name)
    elif args.ini:
        logging.critical("Config {} not found!".format(args.ini))
        sys.exit(1)

    if args.insecure:
        requests.packages.urllib3.disable_warnings()

    if args.user or os.getenv('GITLAB_USER') or args.password or os.getenv('GITLAB_PASSWORD'):
        authentication = (
            args.user if args.user else os.getenv('GITLAB_USER'),
            args.password if args.password else os.getenv('GITLAB_PASSWORD')
        )
    elif os.getenv('CI_JOB_TOKEN'):
        authentication = ('gitlab-ci-token', os.getenv('CI_JOB_TOKEN'))
    else:
        authentication = (config["Gitlab"]["User"], config["Gitlab"]["Password"])

    jwt_url = args.jwt if args.jwt \
        else os.getenv('GITLAB_JWT_URL', config["Gitlab"]["JWT URL"])
    registry_url = args.registry if args.registry \
        else os.getenv('GITLAB_REGISTRY', os.getenv('CI_REGISTRY', config["Gitlab"]["Registry URL"]))
    registry_url = 'https://'+registry_url if not registry_url.startswith('http') else registry_url

    GRICleaner = GitlabRegistryClient(
        auth=authentication,
        jwt=jwt_url,
        registry=registry_url,
        requests_verify=not args.insecure,
        dry_run=args.dry_run)
    minimum_images = args.minimum if args.minimum else int(config["Cleanup"]["Minimum Images"])
    retention_days = args.days if args.days else int(config["Cleanup"]["Retention Days"])

    today = datetime.datetime.today()

    if args.repository:
        catalog = args.repository
    else:
        catalog = GRICleaner.get_catalog()
        logging.debug('Fetched catalog: {}'.format(catalog))
    logging.info("Found {} repositories".format(len(catalog)))
    for repository in catalog:
        logging.info("SCAN repository: {}".format(repository))
        try:
            tags = GRICleaner.get_tags(repository)
        except requests.exceptions.HTTPError as e:
            logging.warning("Encountered a HTTP error when trying to access repository {}\n{}".format(repository, e))
            continue

        if not tags.get("tags"):
            logging.warning("No tags found for repository {}".format(repository))
            continue

        logging.debug("Tags ({}): {}".format(len(tags["tags"]), tags["tags"]))

        if args.tag_match:
            filtered_tags = [i for i in tags["tags"] if args.tag_match in i or re.search(args.tag_match, i)]
            logging.debug("Filtered Tags ({}): {}".format(len(filtered_tags), filtered_tags))
        else:
            filtered_tags = tags["tags"]

        if args.clean_all:
            logging.warning("!!! CLEAN ALL IMAGES !!!")
            for tag in filtered_tags:
                logging.warning("- DELETE: {}:{}".format(repository, tag))
                GRICleaner.delete_image(repository, tag)
        elif len(filtered_tags) > minimum_images:
            latest = GRICleaner.get_image(repository, "latest")
            if "id" in latest:
                latest_id = latest["id"]
                logging.debug("Latest ID: {}".format(latest_id))
            else:
                latest_id = ""
            for tag in list(filtered_tags):
                if len(filtered_tags) > minimum_images:
                    image = GRICleaner.get_image(repository, tag)
                    if image and image["id"] != latest_id:
                        created = dateutil.parser.parse(image["created"]).replace(tzinfo=None)
                        diff = today - created
                        logging.debug("Tag {} with image id {} days diff: {}".format(tag, image["id"], diff.days))
                        if diff.days > retention_days:
                            logging.warning("- DELETE: {}:{}, Created at {} ({} days ago)".
                                            format(repository,
                                                   tag,
                                                   created.replace(microsecond=0),
                                                   diff.days))
                            GRICleaner.delete_image(repository, tag)
                            filtered_tags.remove(tag)
