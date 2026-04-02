# Agendamento no VPS (Cron)

## 1) Ajuste o caminho do projeto
Edite o arquivo `ops/cron/run_automacao.sh` e confirme o valor:

`PROJECT_DIR="/opt/icms_sergipe"`

## 2) Dê permissão de execução
```bash
chmod +x /opt/icms_sergipe/ops/cron/run_automacao.sh
```

## 3) Instale a regra no crontab
```bash
crontab /opt/icms_sergipe/ops/cron/logtudo.cron
```

## 4) Verifique a regra instalada
```bash
crontab -l
```

Regra configurada:

`0 8 * * * /bin/bash /opt/icms_sergipe/ops/cron/run_automacao.sh`

## 5) Logs
Saída da execução diária:

`/opt/icms_sergipe/logs/cron.log`
