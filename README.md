# Alertas Inteligentes

Proyecto Python para consultar una base de datos read-only, evaluar reglas de negocio configurables y enviar alertas automaticas por mail. Esta preparado para correr manualmente en local y de forma programada desde GitHub Actions.

## Arquitectura

La solucion separa responsabilidades para evitar un script monolitico:

- `app/config.py`: lee variables de entorno y `.env` local.
- `app/database/connection.py`: crea la conexion read-only y bloquea SQL que no sea `SELECT` o `WITH`.
- `app/database/queries.py`: contiene las consultas, separadas de reglas y mail.
- `app/rules/`: reglas de negocio extensibles.
- `app/alerts/`: modelo de alerta, historial y motor de orquestacion.
- `app/email_service/`: envio SMTP y template HTML.
- `app/main.py`: punto de entrada principal.
- `tests/`: pruebas unitarias con datos simulados.
- `.github/workflows/alertas.yml`: ejecucion manual y cron desde GitHub Actions.

## Estructura

```text
alertas_inteligentes/
  app/
    main.py
    config.py
    logging_config.py
    database/
      connection.py
      queries.py
    rules/
      base_rule.py
      pending_items_rule.py
      amount_threshold_rule.py
    alerts/
      alert_model.py
      alert_engine.py
      alert_history.py
    email_service/
      email_sender.py
      templates/
        alert_email.html
    utils/
      date_utils.py
  tests/
  .github/workflows/alertas.yml
  .env.example
  requirements.txt
  run_local.bat
```

## Ejecucion local

1. Crear y activar un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3. Copiar `.env.example` a `.env` y completar valores reales. El archivo `.env` esta ignorado por Git y no debe subirse al repositorio.

4. Ejecutar tests:

```powershell
pytest
```

5. Ejecutar el proceso:

```powershell
python -m app.main
```

Tambien se puede usar:

```powershell
.\run_local.bat
```

Para probar sin enviar correos reales, dejar:

```env
EMAIL_DRY_RUN=true
```

En ese modo el sistema consulta la base, arma las alertas, separa destinatarios por sucursal y guarda previews en `data/email_previews`.

Para ver el formato del mail aunque la base no devuelva alertas, ejecutar:

```powershell
python scripts/generate_sample_alert_preview.py
```

Ese script genera alertas ficticias de ejemplo y guarda el HTML en `data/email_previews`.

## Variables de entorno

Variables principales:

- `DB_TYPE`: `mariadb`, `mysql`, `mssql`, `sqlserver` o `sqlite` para pruebas.
- `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_DRIVER`.
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`.
- `EMAIL_DRY_RUN`: si es `true`, genera preview local y no envia mails reales.
- `EMAIL_PREVIEW_DIR`: carpeta donde se guardan previews de mail en dry-run.
- `MAIL_FROM`, `MAIL_TO`.
- `USE_DATABASE_RECIPIENTS`: si es `true`, permite usar `sucursal.mail` como fallback. Por defecto `false`.
- `FORCE_SEND_ALERTS`: si es `true`, ignora el historial y reenvia las alertas detectadas en esa ejecucion. Es util para pruebas manuales desde GitHub.
- `ALERT_DAYS_THRESHOLD`, `ALERT_AMOUNT_THRESHOLD`.
- `ENABLED_RULES`: por defecto `guide_due_date`.
- `GUIDE_DUE_DATE_COLUMN`: columna de `retiro` usada como fecha pactada. Por defecto `fechaplanilla`.
- `GUIDE_LOOKAHEAD_DAYS`: dias futuros para incluir en el semaforo. Por defecto `7`.
- `GUIDE_LOOKBACK_DAYS`: dias vencidos hacia atras para incluir en el semaforo. Por defecto `15`.
- `GUIDE_MAX_ROWS`: maximo de guias a traer por ejecucion para calcular los totales por categoria. Por defecto `5000`; el cuerpo del mail muestra hasta 30 por categoria.
- `GUIDE_ONLY_ACTIVE`: si es `true`, excluye guias inactivas.
- `GUIDE_ONLY_UNFINISHED`: si es `true`, excluye guias finalizadas.
- `SUCURSAL_RECIPIENTS_FILE`: archivo local JSON para mapear sucursales a mails.
- `SUCURSAL_RECIPIENTS_JSON`: JSON equivalente para GitHub Secrets.
- `SUCURSAL_GROUPS_FILE`: archivo JSON para mapear `id` o `codigo_sucursal` al nombre operativo que aparece en el titulo del mail.
- `SUCURSAL_GROUPS_JSON`: JSON equivalente para GitHub Secrets.
- `ENVIRONMENT`: usar `local` o `github_actions`.

`MAIL_TO` acepta varios destinatarios separados por coma.

## Consultas

Las queries de `app/database/queries.py` son ejemplos. Reemplazar tablas y columnas por vistas o tablas reales de solo lectura. Las funciones devuelven listas de diccionarios:

- `get_pending_items()`
- `get_financial_movements()`
- `get_process_status()`
- `get_guides_due_for_week()`: une `retiro.sucursal_id` con `sucursal.id` y toma `sucursal.codigo_sucursal`.

La conexion central bloquea comandos como `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` y similares. Aun asi, el usuario de base debe tener permisos read-only a nivel servidor.

Para MariaDB/MySQL se usa el driver Python `PyMySQL`, por eso `DB_DRIVER` puede quedar como `pymysql`. El valor `libmariadb.dll` que aparece en algunos clientes graficos no hace falta para esta aplicacion Python.

## Alerta de guias por semaforo

La regla activa por defecto es `guide_due_date`. Consulta guias/retiros desde `retiro`, toma la sucursal desde `sucursal.codigo_sucursal` y clasifica por fecha pactada:

- `CRITICO`: fecha pactada hoy o vencida.
- `ADVERTENCIA`: fecha pactada dentro de las proximas 48 horas.
- `PROXIMOS`: fecha pactada entre 3 y 7 dias en el futuro.

La columna de fecha pactada se configura con:

```env
GUIDE_DUE_DATE_COLUMN=fechaplanilla
GUIDE_LOOKAHEAD_DAYS=7
GUIDE_LOOKBACK_DAYS=15
```

Si la fecha pactada real es otra columna de `retiro`, cambiar ese valor por una de estas columnas permitidas: `fecha_retiro`, `fecha_vencimiento`, `fechaplanilla`, `fecha_hora`, `fechaUltimoEstado`, `fecha_hora_entrega`, `fechaRepactacion`.

## Destinatarios por sucursal

Cada alerta puede enviarse a mails distintos segun la sucursal. El sistema resuelve destinatarios en este orden:

1. Archivo JSON local indicado por `SUCURSAL_RECIPIENTS_FILE`.
2. Variable `SUCURSAL_RECIPIENTS_JSON`, util para GitHub Secrets.
3. Columna `sucursal.mail` de la base, solo si `USE_DATABASE_RECIPIENTS=true`.
4. Fallback general `MAIL_TO`.

Ejemplo local en `config/sucursal_recipients.json`:

```json
{
  "336": ["operaciones-mendoza@example.com"],
  "SUC DHL-(MEX MZA)": ["operaciones-mendoza@example.com", "supervisor-mendoza@example.com"]
}
```

El archivo real `config/sucursal_recipients.json` esta ignorado por Git. Para GitHub Actions, cargar el mismo contenido como secret `SUCURSAL_RECIPIENTS_JSON`.

Cuando hay alertas para distintas sucursales, el envio se separa por lotes de destinatarios: cada grupo recibe solo las guias que le corresponden.

El titulo del mail se toma de `config/sucursal_groups.json`. Por ejemplo:

```json
{
  "44": "Sucursal San Rafael",
  "MEXSR": "Sucursal San Rafael"
}
```

Si un mismo lote de destinatarios tiene alertas de varias sucursales operativas, el sistema genera mails separados por titulo de sucursal.

## Historial de alertas

La primera version usa `data/alert_history.json`. Sirve para pruebas locales y evita reenvios mientras ese archivo exista.

Importante para GitHub Actions: los runners hospedados son temporales. El historial local no persiste entre ejecuciones salvo que se guarde en un almacenamiento externo, se publique como artifact, se persista en el repositorio privado o se reemplace por una tabla/base auxiliar. Para produccion, lo recomendable es usar una tabla externa de historial o storage persistente.

## GitHub Actions

El workflow esta en `.github/workflows/alertas.yml` e incluye:

- `workflow_dispatch` para ejecucion manual.
- `schedule` con cron `15 11 * * 1-5`.
- Input manual `email_dry_run` para probar sin enviar mails.
- Input manual `force_send_alerts` para reenviar aunque el runner ya tenga historial de alertas enviadas.
- Python 3.11.
- Instalacion condicional del driver ODBC de SQL Server solo si `DB_TYPE` es SQL Server.
- Instalacion de dependencias.
- Ejecucion de tests.
- Ejecucion de `python -m app.main`.
- Publicacion de previews como artifact cuando `EMAIL_DRY_RUN=true`.

El cron de GitHub Actions usa horario UTC. Para Argentina, `11:15 UTC` equivale a `08:15` de Argentina durante UTC-3. Revisar la conversion si cambia el horario deseado.

Para configurar credenciales:

1. Ir al repositorio en GitHub.
2. Entrar en `Settings > Secrets and variables > Actions`.
3. Crear cada secret requerido: `DB_TYPE`, `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_DRIVER`, `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_DRY_RUN`, `MAIL_FROM`, `MAIL_TO`, `USE_DATABASE_RECIPIENTS`, `ALERT_DAYS_THRESHOLD`, `ALERT_AMOUNT_THRESHOLD`, `ENABLED_RULES`, `GUIDE_DUE_DATE_COLUMN`, `GUIDE_LOOKAHEAD_DAYS`, `GUIDE_LOOKBACK_DAYS`, `GUIDE_MAX_ROWS`, `GUIDE_ONLY_ACTIVE`, `GUIDE_ONLY_UNFINISHED`, `SUCURSAL_RECIPIENTS_JSON`, `SUCURSAL_GROUPS_JSON`.
4. Ejecutar manualmente desde la pestaña `Actions` o esperar el cron.

Para la primera prueba en GitHub, usar `workflow_dispatch` con `email_dry_run=true`. Si se generan alertas, descargar el artifact `email-previews` desde la corrida del workflow.

Si la base esta en una red interna que GitHub no puede alcanzar, usar una de estas alternativas:

- Self-hosted runner instalado en una maquina o servidor con acceso a la base.
- Desplegar el proceso en un servidor o cloud con conectividad a la red.
- Exponer un endpoint seguro intermedio.
- Replicar los datos necesarios a una base auxiliar accesible y read-only.

## Como agregar una regla

1. Crear un archivo nuevo en `app/rules/`, por ejemplo `process_status_rule.py`.
2. Heredar de `BaseRule`.
3. Definir `name`, `description`, `severity` y `data_key`.
4. Implementar `evaluate(data)` devolviendo una lista de `Alert`.
5. Registrar la regla en `AlertEngine`, dentro de la lista `self.rules`.

Ejemplo minimo:

```python
class ProcessStatusRule(BaseRule):
    name = "process_status"
    description = "Detecta procesos con estado inesperado."
    severity = "critical"
    data_key = "process_status"

    def evaluate(self, data):
        alerts = []
        for row in data:
            if row["current_status"] != row["expected_status"]:
                alerts.append(...)
        return alerts
```

## Cambiar destinatarios

Modificar `MAIL_TO` en `.env` local o en GitHub Secrets:

```text
MAIL_TO=operaciones@example.com,gerencia@example.com
```

## Seguridad

- No subir `.env`.
- No hardcodear credenciales.
- Usar GitHub Secrets para Actions.
- Usar usuario de base con permisos read-only.
- No imprimir passwords en logs.
- Separar queries, reglas, historial y mail.
- Mantener tests para cada nueva regla.

## Limitaciones conocidas

- Las consultas son ejemplos y deben adaptarse a la base real.
- El historial JSON local no persiste en runners hospedados de GitHub.
- SQL Server desde GitHub requiere conectividad de red y driver ODBC.
- Si el SMTP requiere reglas especiales de seguridad, se deben configurar app passwords, IP allowlist o relay autorizado.

## Proximos pasos recomendados

- Reemplazar queries de ejemplo por vistas reales read-only.
- Confirmar conectividad desde el entorno de ejecucion elegido.
- Crear una tabla externa de historial de alertas.
- Agregar reglas especificas por proceso de negocio.
- Agregar alertas por severidad y destinatarios por area.
- Sumar un modo de dry-run si se quiere validar sin enviar mails.
