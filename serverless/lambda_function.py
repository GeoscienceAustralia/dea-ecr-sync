import os
import base64
import fnmatch
import json
import boto3
import subprocess
from dataclasses import dataclass
from typing import List, Optional
from mypy_boto3_ecr import ECRClient
from concurrent.futures import ThreadPoolExecutor
from mypy_boto3_ecr.type_defs import RepositoryTypeDef


@dataclass()
class Context:
    client: ECRClient
    registry_id: str


@dataclass()
class MirroredRepo:
    upstream_image: str
    repository_uri: str
    upstream_tags: List[str]


def lambda_handler(event, context):
    client = boto3.client("ecr")
    registry_id = os.environ.get('registry_id')

    sync(client, registry_id)


def sync(client, registry_id):
    repositories = find_repositories(client, registry_id)
    copy_repositories(client, registry_id, list(repositories))


def copy_repositories(
        client: ECRClient, registry_id: str, repositories: List[MirroredRepo]):
    """
    Perform the actual, concurrent copy of the images
    """
    token = ecr_login(client, registry_id)
    print("Finding all tags to copy...")
    items = [
        (repo, tag)
        for repo in repositories
        for tag in find_tags_to_copy(repo.upstream_image, repo.upstream_tags)
    ]
    print(f"Beginning the copy of {len(items)} images")

    with ThreadPoolExecutor() as pool:
        pool.map(
            lambda item: copy_image(
                f"{item[0].upstream_image}:{item[1]}",
                f"{item[0].repository_uri}:{item[1]}",
                token,
            ),
            items,
        )


def ecr_login(client: ECRClient, registry_id: str) -> str:
    """
    Authenticate with ECR, returning a `username:password` pair
    """
    auth_response = client.get_authorization_token(registryIds=[registry_id])
    return base64.decodebytes(
        auth_response["authorizationData"][0]["authorizationToken"].encode()
    ).decode()


def copy_image(source_image, dest_image, token):
    """
    Copy a single image using Skopeo
    """
    print(f"Copying {source_image} to {dest_image}")
    args = [
        "/var/task/skopeo",
        "copy",
        f"docker://{source_image}",
        f"docker://{dest_image}",
        "--override-os=linux",
        "--insecure-policy",
    ]
    args_with_creds = args + [f"--dest-creds={token}"]
    try:
        subprocess.check_output(args_with_creds)
    except subprocess.CalledProcessError as e:
        print(f'{" ".join(args)} raised an error: {e.returncode}', fg="red")
        print(f'Last output: {e.output[100:]}', fg="red")


def find_tags_to_copy(image_name, tag_patterns):
    """
    Use Skopeo to list all available tags for an image
    """
    output = subprocess.check_output(
        ["/var/task/skopeo", "inspect",
         f"docker://{image_name}", "--override-os=linux"]
    )
    all_tags = json.loads(output)["RepoTags"]

    if not tag_patterns:
        return all_tags

    yield from (
        tag
        for tag in all_tags
        if any(fnmatch.fnmatch(tag, pattern) for pattern in tag_patterns)
    )


def find_repositories(client: ECRClient, registry_id: str):
    """
    List all ECR repositories that have an `upstream-image` tag set.
    """
    paginator = client.get_paginator("describe_repositories")
    all_repositories = [
        repo
        for result in paginator.paginate(registryId=registry_id)
        for repo in result["repositories"]
    ]

    def filter_repo(repo: RepositoryTypeDef) -> Optional[MirroredRepo]:
        tags = client.list_tags_for_resource(resourceArn=repo["repositoryArn"])
        tags_dict = {
            tag_item["Key"]: tag_item["Value"] for tag_item in tags["tags"]
        }

        if "upstream-image" in tags_dict:
            return MirroredRepo(
                upstream_image=tags_dict["upstream-image"],
                upstream_tags=tags_dict.get(
                    "upstream-tags", "").replace("+", "*").split("/"),
                repository_uri=repo["repositoryUri"],
            )

    with ThreadPoolExecutor() as pool:
        for item in pool.map(filter_repo, all_repositories):
            if item is not None:
                yield item
