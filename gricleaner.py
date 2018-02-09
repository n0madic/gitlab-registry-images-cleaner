#!/usr/bin/env python

import logging
import json
import requests


class GitlabRegistryClient(object):
    """Client for Gitlab registry"""

    def __init__(self, auth, jwt, registry, dry_run=False):
        """ Initializing arguments """
        self.auth = auth
        self.jwt = jwt.rstrip('//')
        self.registry = registry.rstrip('//')
        self.dry_run = dry_run
        self.tokens = dict()  # Cache for bearer tokens

    def get_bearer(self, scope):
        """Return bearer token from Gitlab jwt"""
        if not scope in self.tokens:
            url = "{}/?service=container_registry&scope={}:*".format(
                self.jwt, scope)
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            token = response.json()
            self.tokens[scope] = token["token"]
        return self.tokens[scope]

    def get_json(self, path, scope):
        """Return JSON from registry"""
        headers = {"Authorization": "Bearer " + self.get_bearer(scope)}
        response = requests.get(self.registry + path, headers=headers)
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
        response = requests.head(self.registry + path, headers=headers)
        return response.headers["Docker-Content-Digest"]

    def delete_image(self, repo, tag):
        """Delete image by tag from registry"""
        url = "/v2/{}/manifests/{}".format(repo, self.get_digest(repo, tag))
        logging.debug("Delete URL: {}{}".format(self.registry, url))
        if self.dry_run:
            logging.info("~ Dry Run!")
        else:
            headers = {
                "Authorization":
                "Bearer " + self.get_bearer("repository:" + repo)
            }
            response = requests.delete(self.registry + url, headers=headers)
            if response.status_code == 202:
                logging.info("+ OK")
            else:
                logging.error(response.text)


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
        epilog="To work requires settings in the INI file",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-i",
        "--ini",
        help="use this INI file (default: {})".format(config_name),
        metavar="FILE")
    parser.add_argument(
        "-r",
        "--repository",
        action='append',
        default=[],
        help="scan only these repositories (one or more)",
        metavar="namespace/project")
    parser.add_argument(
        "-m",
        "--minimum",
        help=
        "minimum allowed number of images in repository (overrides INI value)",
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
        if os.path.isfile(args.ini):
            config_name = args.ini
        else:
            logging.critical("Config {} not found!".format(args.ini))
            sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_name)

    GRICleaner = GitlabRegistryClient(
        auth=(config["Gitlab"]["User"], config["Gitlab"]["Password"]),
        jwt=config["Gitlab"]["JWT URL"],
        registry=config["Gitlab"]["Registry URL"],
        dry_run=args.dry_run)
    minimum_images = args.minimum if args.minimum else int(
        config["Cleanup"]["Minimum Images"])
    retention_days = args.days if args.days else int(
        config["Cleanup"]["Retention Days"])

    today = datetime.datetime.today()

    if args.repository:
        catalog = args.repository
    else:
        catalog = GRICleaner.get_catalog()
    logging.info("Found {} repositories".format(len(catalog)))
    for repository in catalog:
        if args.repository and not repository in args.repository:
            continue
        logging.info("SCAN repository: {}".format(repository))
        tags = GRICleaner.get_tags(repository)
        logging.debug("Tags ({}): {}".format(len(tags["tags"]), tags["tags"]))
        if args.clean_all:
            logging.warning("!!! CLEAN ALL IMAGES !!!")
            for tag in tags["tags"]:
                logging.warning("- DELETE: {}:{}".format(repository, tag))
                GRICleaner.delete_image(repository, tag)
        else:
            latest = GRICleaner.get_image(repository, "latest")
            if "id" in latest:
                latest_id = latest["id"]
                if args.debug:
                    logging.debug("Latest ID: {}".format(latest_id))
            else:
                latest_id = ""
            if len(tags["tags"]) > minimum_images:
                for tag in tags["tags"]:
                    image = GRICleaner.get_image(repository, tag)
                    if image and image["id"] != latest_id:
                        created = dateutil.parser.parse(
                            image["created"]).replace(tzinfo=None)
                        diff = today - created
                        logging.debug(
                            "Tag {} with image id {} days diff: {}".format(
                                tag, image["id"], diff.days))
                        if diff.days > retention_days:
                            logging.warning(
                                "- DELETE: {}:{}, Created at {}, ({} days ago)".
                                format(
                                    repository,
                                    tag,
                                    created.replace(microsecond=0),
                                    diff.days))
                            GRICleaner.delete_image(repository, tag)
