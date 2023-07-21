# Repository Archived - DO NOT USE

The code in this repository has some big problems and is no longer used.

`skopeo` is a poor choice for copying or syncing images from Dockerhub, because *every* sync or copy counts as a *Pull*, regardless of any data being copied. Completely defeating the entire purpose of this entier thing.


### GeoscienceAustralia Dockerhub to ECR Sync Lambda

AWS Lambda to mirror public docker images to ECR, triggered using a scheduled CloudWatch event, and based on https://pypi.org/project/ecr-mirror/

### Deploying the Lambda
Uses serverless to deploy the Lambda https://www.serverless.com/framework/docs/getting-started/


Adjust the schedule in serverless.yml

```
schedule: rate(1 day)
```
Install plugin dependencies and deploy
```python
serverless plugin install -n serverless-python-requirements
export AWS_ACCOUND_ID=123456789012
serverless deploy
```


### Setting up the ecr repositories

Create an ECR repository with the following two tags set:

* upstream-image set to a public Docker hub image, e.g opendatacube/ows
* upstream-tags set to a /-separated list of tag globs, i.e 1.6.* or just 1.2-alpine. ECR does not allow the use of the * character in tag values, so you should use + as a replacement.

You can select a range of different tags like so: 1.1[4567]* - this will match 1.14 to 1.17.

Terraform example
```python
resource "aws_ecr_repository" "opendatacube_ows" {
  name = "opendatacube/ows"
  tags = {
    upstream-image = "opendatacube/ows",
    // Mirror 1.8.1-9* and latest
    upstream-tags = "1.8.1-9+/latest",
  }
}
```

aws cli example

```python
aws ecr create-repository --repository-name opendatacube/ows --tags Key=upstream-image,Value=opendatacube/ows Key=upstream-tags,Value=1.8.1-9+/latest
```
