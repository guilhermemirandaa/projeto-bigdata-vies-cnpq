terraform {
  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = ">= 4.0.0, < 5.0.0"
    }
  }
}

provider "aiven" {
  api_token = var.aiven_api_token
}

resource "aiven_pg" "fomento" {
  project      = var.aiven_project
  service_name = var.service_name
  plan         = var.plan
}
