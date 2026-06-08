# Configuracion en GitHub

## 1. Crear repositorio

Crear un repositorio privado en GitHub, por ejemplo:

```text
alertas-inteligentes-sucursales
```

Luego subir este proyecto al repositorio.

Nota de seguridad: en el proyecto viejo `presis-alertas` se detecto un token de GitHub embebido en `.git/config`. No usarlo ni copiarlo. Conviene revocarlo/rotarlo desde GitHub y configurar el remote sin token en la URL.

## 2. Cargar GitHub Secrets

Ir a:

```text
Settings > Secrets and variables > Actions > New repository secret
```

Para la primera prueba en `dry-run`, el unico secret obligatorio es:

```text
DB_PASSWORD=valor_real_no_documentar
```

El workflow ya trae valores por defecto para base, destinatarios y reglas. Si luego se quiere sobreescribir algo desde GitHub, crear estos secrets opcionales:

```text
DB_TYPE=mariadb
DB_SERVER=mexreplica.epresis.com
DB_NAME=mex_lv
DB_USER=readonly_mex
DB_PORT=3345
DB_DRIVER=pymysql

MAIL_TO=gpereyra@mailexpress.com.ar,airisarri@mailexpress.com.ar,mzera@mailexpress.com.ar
MAIL_FROM=mailexpress742@gmail.com

EMAIL_DRY_RUN=true

ENABLED_RULES=guide_due_date
GUIDE_DUE_DATE_COLUMN=fecha_vencimiento
GUIDE_LOOKAHEAD_DAYS=7
GUIDE_MAX_ROWS=1000
GUIDE_ONLY_ACTIVE=true
GUIDE_ONLY_UNFINISHED=true

ALERT_DAYS_THRESHOLD=7
ALERT_AMOUNT_THRESHOLD=100000
```

Para pruebas con `EMAIL_DRY_RUN=true`, los secrets SMTP pueden quedar cargados despues. Para enviar mails reales, agregar:

```text
SMTP_SERVER=servidor_smtp_real
SMTP_PORT=587
SMTP_USER=usuario_smtp_real
SMTP_PASSWORD=password_smtp_real
SMTP_USE_TLS=true
EMAIL_DRY_RUN=false
```

Si se reutilizan los secrets del proyecto viejo `presis-alertas`, tambien sirven estos nombres:

```text
SMTP_HOST=smtp.gmail.com        # equivalente a SMTP_SERVER
SMTP_PASS=valor_real_no_documentar  # equivalente a SMTP_PASSWORD
REPORT_EMAILS=destinatarios     # equivalente a MAIL_TO
```

Para el proyecto viejo se detecto esta configuracion no sensible:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=mailexpress742@gmail.com
SMTP_SECURE=false
```

En este proyecto usar:

```text
SMTP_USE_TLS=true
MAIL_FROM=mailexpress742@gmail.com
```

## 3. Destinatarios por sucursal

Como `config/sucursal_recipients.json` no se sube a Git por seguridad, cargar este secret:

```text
SUCURSAL_RECIPIENTS_JSON={"1123":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEX CASA CENTRAL":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"1":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEX DORREGO":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"44":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXSR":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"527":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEX VILLAMARIA":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"42":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXRIOIV":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"49":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXSF":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"50":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXROSARIO":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"43":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXPARANA":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"47":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXSL":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"130":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXMALARGUE":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"128":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"],"MEXGALVEAR":["gpereyra@mailexpress.com.ar","airisarri@mailexpress.com.ar","mzera@mailexpress.com.ar"]}
```

`SUCURSAL_GROUPS_JSON` es opcional si `config/sucursal_groups.json` esta subido al repositorio.

## 4. Primera prueba

En GitHub:

```text
Actions > Alertas Inteligentes > Run workflow
```

Elegir:

```text
email_dry_run=true
```

Si aparecen alertas, descargar el artifact:

```text
email-previews
```

Cuando el preview este validado y el SMTP este configurado, ejecutar manualmente con:

```text
email_dry_run=false
```

## 5. Red y acceso a la base

Si GitHub Actions no puede conectarse a `mexreplica.epresis.com:3345`, usar un self-hosted runner dentro de la red con acceso a la base, o ejecutar el proceso en un servidor/cloud con conectividad permitida.

Los runners hospedados de GitHub pueden no tener permiso de red para entrar a la base. En ese caso el error esperado es similar a:

```text
Can't connect to MySQL server on 'mexreplica.epresis.com' (timed out)
```

Para que la primera prueba no quede bloqueada por conectividad, el workflow hace esto:

- Si `email_dry_run=true` y la base no responde, genera un preview de muestra y sube el artifact `email-previews`.
- Si `email_dry_run=false`, el workflow falla. Eso es correcto, porque no se puede enviar una alerta real sin consultar la base.

Para produccion hay dos caminos:

- Instalar un self-hosted runner en una maquina/servidor que tenga acceso a `mexreplica.epresis.com:3345`.
- Pedir a infraestructura que permita el acceso desde GitHub Actions a la base o publicar un endpoint intermedio seguro.
