# R2R GCP Deployment Makefile
# Управление развертыванием R2R Full Mode на Google Cloud Platform

# Переменные
PROJECT_ID := r2r-full-deployment
ZONE := us-central1-a
VM_NAME := r2r-production
VM_IP := 136.119.36.216
MACHINE_TYPE := n1-standard-4
DISK_SIZE := 200
DOCKER_DIR := ~/R2R/docker

.PHONY: help
help:  ## Показать эту справку
	@echo "R2R GCP Deployment Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

## === VM Management ===

.PHONY: vm-create
vm-create:  ## Создать Compute Engine VM
	gcloud compute instances create $(VM_NAME) \
	  --project=$(PROJECT_ID) \
	  --zone=$(ZONE) \
	  --machine-type=$(MACHINE_TYPE) \
	  --create-disk=auto-delete=yes,boot=yes,device-name=$(VM_NAME),image=projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20251111,mode=rw,size=$(DISK_SIZE),type=pd-balanced \
	  --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
	  --maintenance-policy=MIGRATE \
	  --tags=r2r-server,http-server \
	  --labels=env=production,app=r2r

.PHONY: vm-delete
vm-delete:  ## Удалить VM
	gcloud compute instances delete $(VM_NAME) \
	  --zone=$(ZONE) \
	  --project=$(PROJECT_ID) \
	  --quiet

.PHONY: vm-start
vm-start:  ## Запустить остановленную VM
	gcloud compute instances start $(VM_NAME) \
	  --zone=$(ZONE) \
	  --project=$(PROJECT_ID)

.PHONY: vm-stop
vm-stop:  ## Остановить VM
	gcloud compute instances stop $(VM_NAME) \
	  --zone=$(ZONE) \
	  --project=$(PROJECT_ID)

.PHONY: vm-ssh
vm-ssh:  ## SSH подключение к VM
	gcloud compute ssh $(VM_NAME) \
	  --zone=$(ZONE) \
	  --project=$(PROJECT_ID)

.PHONY: vm-status
vm-status:  ## Проверить статус VM
	gcloud compute instances describe $(VM_NAME) \
	  --zone=$(ZONE) \
	  --project=$(PROJECT_ID) \
	  --format="table(name,status,networkInterfaces[0].accessConfigs[0].natIP)"

## === Firewall Rules ===

.PHONY: firewall-create
firewall-create:  ## Создать Firewall Rules для R2R
	gcloud compute firewall-rules create allow-r2r-services \
	  --project=$(PROJECT_ID) \
	  --direction=INGRESS \
	  --priority=1000 \
	  --network=default \
	  --action=ALLOW \
	  --rules=tcp:7272-7276,tcp:22 \
	  --source-ranges=0.0.0.0/0 \
	  --target-tags=r2r-server

.PHONY: firewall-delete
firewall-delete:  ## Удалить Firewall Rules
	gcloud compute firewall-rules delete allow-r2r-services \
	  --project=$(PROJECT_ID) \
	  --quiet

.PHONY: firewall-list
firewall-list:  ## Показать Firewall Rules
	gcloud compute firewall-rules list \
	  --project=$(PROJECT_ID) \
	  --filter="targetTags:r2r-server"

## === Docker Management ===

.PHONY: docker-install
docker-install:  ## Установить Docker на VM
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  sudo apt-get update -qq && \
	  sudo apt-get install -y -qq ca-certificates curl git && \
	  sudo install -m 0755 -d /etc/apt/keyrings && \
	  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
	  sudo chmod a+r /etc/apt/keyrings/docker.asc && \
	  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$$VERSION_CODENAME\") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null && \
	  sudo apt-get update -qq && \
	  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin && \
	  sudo usermod -aG docker $$USER && \
	  docker --version && docker compose version'

## === R2R Deployment ===

.PHONY: r2r-deploy
r2r-deploy:  ## Развернуть R2R Full Mode
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml --profile postgres up -d'

.PHONY: r2r-stop
r2r-stop:  ## Остановить R2R
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml down'

.PHONY: r2r-restart
r2r-restart:  ## Перезапустить R2R
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml down && \
	  docker compose -f compose.full.yaml --profile postgres up -d'

.PHONY: r2r-clean
r2r-clean:  ## Остановить и очистить volumes
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml down -v && \
	  docker volume prune -f'

.PHONY: r2r-redeploy
r2r-redeploy:  ## Полный рестарт с очисткой volumes
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml down -v && \
	  docker volume rm hatchet_postgres_data 2>/dev/null || true && \
	  docker volume prune -f && \
	  docker compose -f compose.full.yaml --profile postgres up -d'

## === Monitoring ===

.PHONY: status
status:  ## Показать статус всех сервисов
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml ps'

.PHONY: status-all
status-all:  ## Показать статус всех контейнеров (включая остановленные)
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml ps -a'

.PHONY: logs
logs:  ## Показать логи R2R (tail 50)
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml logs --tail=50 r2r'

.PHONY: logs-follow
logs-follow:  ## Следить за логами R2R в реальном времени
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml logs -f r2r'

.PHONY: logs-hatchet
logs-hatchet:  ## Показать логи Hatchet
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml logs --tail=50 hatchet-engine'

.PHONY: logs-all
logs-all:  ## Показать логи всех сервисов
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cd $(DOCKER_DIR) && \
	  docker compose -f compose.full.yaml logs --tail=30'

.PHONY: stats
stats:  ## Показать использование ресурсов
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"'

## === Health Checks ===

.PHONY: health
health:  ## Проверить health R2R API
	@echo "Проверка R2R API health:"
	@curl -s http://$(VM_IP):7272/v3/health || echo "API недоступен"

.PHONY: health-all
health-all:  ## Проверить все endpoints
	@echo "R2R API (7272):"
	@curl -s http://$(VM_IP):7272/v3/health | head -5 || echo "  ❌ Недоступен"
	@echo ""
	@echo "R2R Dashboard (7273):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://$(VM_IP):7273 || echo "  ❌ Недоступен"
	@echo ""
	@echo "Hatchet Dashboard (7274):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://$(VM_IP):7274 || echo "  ❌ Недоступен"

## === Configuration ===

.PHONY: config-sync
config-sync:  ## Синхронизировать конфигурацию на VM
	gcloud compute scp docker/user_configs/gemini-openai.toml \
	  $(VM_NAME):~/R2R/docker/user_configs/ \
	  --zone=$(ZONE) \
	  --project=$(PROJECT_ID)

.PHONY: config-show
config-show:  ## Показать текущую конфигурацию на VM
	gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command=' \
	  cat ~/R2R/docker/user_configs/gemini-openai.toml'

## === Quick Deploy (Full Setup) ===

.PHONY: deploy-full
deploy-full:  ## Полное развертывание с нуля
	@echo "🚀 Начало полного развертывания R2R..."
	@echo ""
	@echo "1️⃣ Создание VM..."
	@make vm-create
	@echo ""
	@echo "2️⃣ Создание Firewall Rules..."
	@make firewall-create
	@echo ""
	@echo "3️⃣ Установка Docker (подождите 2 минуты)..."
	@sleep 120
	@make docker-install
	@echo ""
	@echo "4️⃣ Клонирование R2R..."
	@gcloud compute ssh $(VM_NAME) --zone=$(ZONE) --project=$(PROJECT_ID) --command='git clone https://github.com/SciPhi-AI/R2R.git ~/R2R'
	@echo ""
	@echo "5️⃣ Синхронизация конфигурации..."
	@make config-sync
	@echo ""
	@echo "6️⃣ Запуск R2R..."
	@make r2r-deploy
	@echo ""
	@echo "✅ Развертывание завершено!"
	@echo ""
	@echo "🌐 Доступ к сервисам:"
	@echo "  R2R API:          http://$(VM_IP):7272"
	@echo "  R2R Dashboard:    http://$(VM_IP):7273"
	@echo "  Hatchet Dashboard: http://$(VM_IP):7274"

## === Cleanup ===

.PHONY: destroy-all
destroy-all:  ## Удалить все (VM + Firewall)
	@echo "⚠️  Удаление всей инфраструктуры..."
	@make vm-delete
	@make firewall-delete
	@echo "✅ Все удалено!"
