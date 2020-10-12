resource "aws_ecr_repository" "opendatacube_ows" {
  name = "opendatacube/ows"
  tags = {
    upstream-image = "opendatacube/ows",
    upstream-tags  = "1.8.1-9+/latest",
  }
}
