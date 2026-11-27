output "database_url" {
  description = "String de conexão do PostgreSQL. Copie para DATABASE_URL no .env."
  value       = aiven_pg.fomento.service_uri
  sensitive   = true
}

output "host" {
  value = aiven_pg.fomento.service_host
}

output "port" {
  value = aiven_pg.fomento.service_port
}
