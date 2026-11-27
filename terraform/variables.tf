variable "aiven_api_token" {
  description = "Token da API da Aiven (Console > User > Tokens). Passe via TF_VAR_aiven_api_token."
  type        = string
  sensitive   = true
}

variable "aiven_project" {
  description = "Nome do projeto já existente na conta Aiven."
  type        = string
}

variable "service_name" {
  description = "Nome do serviço PostgreSQL."
  type        = string
  default     = "pg-fomento-cnpq"
}

variable "plan" {
  description = "Plano do serviço. Confira o nome do plano gratuito com: avn service plans --service-type pg"
  type        = string
  default     = "free-1-1gb"
}
