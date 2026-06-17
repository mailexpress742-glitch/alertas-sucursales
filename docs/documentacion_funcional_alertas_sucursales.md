# Documentacion funcional - Alertas inteligentes por sucursal

## 1. Objetivo

El objetivo del desarrollo es detectar guias/retiros con fecha pactada proxima o vencida, clasificarlas por prioridad operativa y enviar un correo consolidado por sucursal.

La alerta permite que cada sucursal visualice rapidamente que guias requieren gestion inmediata, seguimiento preventivo o planificacion semanal.

## 2. Alcance funcional

El sistema contempla:

- Consulta automatica a la base de datos de Presis/MailExpress.
- Lectura de guias desde la tabla `retiro`.
- Asociacion de cada guia con su sucursal desde la tabla `sucursal`.
- Clasificacion por semaforo segun la fecha pactada.
- Consolidacion de alertas por sucursal.
- Envio de correos a destinatarios configurados.
- Ejecucion manual o programada desde GitHub Actions.
- Modo de prueba con previews HTML y correo de muestra.

Fuera del alcance actual:

- Gestion manual de guias desde el sistema.
- Modificacion de datos en la base.
- Confirmacion de lectura del correo.
- Persistencia avanzada del historial en una tabla externa.

## 3. Fuente de datos

La alerta principal consulta la tabla `retiro` y la relaciona con `sucursal`.

La consulta base toma los siguientes datos funcionales:

| Dato funcional | Origen actual |
| --- | --- |
| Guia | `retiro.id` |
| Sucursal | `retiro.sucursal_id` |
| Codigo de sucursal | `sucursal.codigo_sucursal` |
| Nombre/descripcion de sucursal | `sucursal.descripcion` |
| Mail de sucursal | `sucursal.mail` |
| Fecha pactada | Columna configurable de `retiro` |
| Estado | Campo de estado disponible en la fila consultada |

La guia que se muestra en el correo sale de:

```sql
r.id AS record_reference
```

Por ejemplo, para una guia consultada asi:

```sql
SELECT * FROM retiro WHERE id = '103842782'
```

el valor mostrado en la columna `Guia` debe ser:

```text
103842782
```

## 4. Fecha pactada configurable

La fecha usada para semaforizar se configura con la variable:

```text
GUIDE_DUE_DATE_COLUMN
```

Valor actual por defecto:

```text
fechaplanilla
```

Columnas permitidas:

| Columna |
| --- |
| `fecha_retiro` |
| `fecha_vencimiento` |
| `fechaplanilla` |
| `fecha_hora` |
| `fechaUltimoEstado` |
| `fecha_hora_entrega` |
| `fechaRepactacion` |

## 5. Regla de semaforizacion

Cada guia se clasifica segun la diferencia entre la fecha pactada y la fecha de ejecucion.

| Categoria | Criterio | Accion esperada |
| --- | --- | --- |
| Critico | Fecha pactada hoy o vencida | Gestion inmediata y rendicion prioritaria |
| Proximas 48 horas | Fecha pactada dentro de 1 a 2 dias | Seguimiento preventivo |
| Proxima semana | Fecha pactada entre 3 y 7 dias | Planificacion operativa semanal |

Las guias con fecha pactada a mas de 7 dias no se incluyen en la alerta.

Para evitar consultas pesadas sobre todo el historico, las guias vencidas se buscan dentro de una ventana configurable hacia atras. Valor por defecto:

```text
GUIDE_LOOKBACK_DAYS=15
```

## 6. Consolidacion por sucursal

El sistema no envia un correo por cada guia.

El comportamiento funcional esperado es:

- Un correo por sucursal.
- Una alerta consolidada por sucursal.
- Dentro del correo se muestran las categorias del semaforo.
- Cada categoria muestra hasta 30 guias.
- El titulo de cada categoria indica cuantos registros se muestran sobre el total de esa categoria.

Ejemplo:

```text
CRITICO (Hoy o vencidas) - Mostrando 30 de 35 registros
PROXIMAS 48 HORAS - Mostrando 30 de 33 registros
PROXIMA SEMANA - Mostrando 30 de 31 registros
```

## 7. Formato del correo

### Asunto

El asunto del correo usa el nombre operativo de la sucursal:

```text
Sucursal General Alvear - Alertas (1)
```

El numero `(1)` representa una alerta consolidada, no la cantidad de guias.

### Encabezado

El encabezado muestra:

- Nombre de la sucursal.
- Fecha y hora de ejecucion.
- Resumen ejecutivo.

Ejemplo:

```text
Se detecto 1 alerta consolidada con 99 detalle(s) que requieren revision.
```

### Columnas del detalle

La tabla funcional de guias muestra:

| Columna | Descripcion |
| --- | --- |
| Guia | Numero de guia tomado de `retiro.id` |
| Cliente | Cliente, remitente o destinatario si la consulta lo entrega |
| Pactada | Fecha pactada usada para la semaforizacion |
| Estado | Estado disponible en la fila consultada |

La columna `Remito` no se muestra en el correo para evitar confusion con el numero de guia.

## 8. Destinatarios

Los destinatarios se resuelven por sucursal en este orden:

1. Archivo local `config/sucursal_recipients.json`.
2. Variable/secret `SUCURSAL_RECIPIENTS_JSON`.
3. Campo `sucursal.mail` si viene desde la base y `USE_DATABASE_RECIPIENTS=true`.
4. Lista general `MAIL_TO`.

Para pruebas se puede usar una lista general de destinatarios.

## 9. Agrupacion de sucursales

El titulo del correo se resuelve con `config/sucursal_groups.json`.

Mapa funcional actual:

| Identificador | Nombre operativo |
| --- | --- |
| `1123`, `MEX CASA CENTRAL`, `1`, `MEX DORREGO`, `336`, `SUC DHL-(MEX MZA)` | Sucursal Mendoza |
| `44`, `MEXSR` | Sucursal San Rafael |
| `527`, `MEX VILLAMARIA`, `42`, `MEXRIOIV` | Sucursal Cba |
| `49`, `MEXSF` | Sucursal Santa Fe |
| `50`, `MEXROSARIO` | Sucursal Rosario |
| `43`, `MEXPARANA` | Sucursal Parana |
| `47`, `MEXSL` | Sucursal San Luis |
| `130`, `MEXMALARGUE` | Sucursal Malargue |
| `128`, `MEXGALVEAR` | Sucursal General Alvear |

Si una sucursal no esta mapeada, se usa el codigo, descripcion o ID disponible en la base.

## 10. Ejecucion

### Ejecucion programada

El workflow de GitHub Actions esta configurado con cron:

```text
15 11 * * 1-5
```

Equivale aproximadamente a las 08:15 de Argentina, de lunes a viernes.

### Ejecucion manual

Desde GitHub:

```text
Actions > Alertas Inteligentes > Run workflow
```

Opciones disponibles:

| Opcion | Uso |
| --- | --- |
| `email_dry_run` | Si es `true`, genera preview y no envia alertas reales |
| `allow_sample_preview_on_db_failure` | Si la base no responde, permite generar muestra |
| `send_sample_email_on_db_failure` | Envia un correo de muestra durante el dry-run |

Para probar formato sin enviar alertas reales:

```text
email_dry_run = true
allow_sample_preview_on_db_failure = true
send_sample_email_on_db_failure = true
```

Para envio real:

```text
email_dry_run = false
```

## 11. Runner self-hosted

El workflow corre sobre un runner self-hosted con etiquetas:

```text
self-hosted, Windows, X64
```

Si GitHub muestra:

```text
Waiting for a runner to pick up this job
```

significa que el runner de la PC/servidor no esta activo.

Debe estar corriendo el proceso:

```text
Runner.Listener.exe
```

## 12. Modo de prueba

El sistema permite generar datos de muestra para validar formato visual.

Script:

```powershell
python scripts/generate_sample_alert_preview.py
```

Con dry-run genera archivos HTML/EML en:

```text
data/email_previews
```

Con envio real de muestra:

```powershell
$env:SAMPLE_PREVIEW_EMAIL_DRY_RUN='false'
python scripts/generate_sample_alert_preview.py
```

La muestra no representa datos reales de la base. Sirve solo para validar formato del correo.

## 13. Historial y duplicados

El sistema usa un historial local para evitar reenviar alertas ya enviadas.

Archivo:

```text
data/alert_history.json
```

Comportamiento:

- Registra alertas detectadas.
- Filtra alertas ya enviadas.
- Evita duplicados mientras el archivo exista.

Consideracion: para produccion, conviene migrar este historial a una tabla o storage persistente.

## 14. Seguridad y permisos

El sistema solo ejecuta consultas de lectura.

La conexion bloquea comandos como:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `TRUNCATE`

Recomendaciones:

- Usar usuario de base read-only.
- No subir `.env` al repositorio.
- Configurar passwords en GitHub Secrets.
- No imprimir contrasenas en logs.

## 15. Variables funcionales principales

| Variable | Descripcion |
| --- | --- |
| `DB_TYPE` | Tipo de base: `mariadb`, `mysql`, `mssql`, `sqlserver` o `sqlite` |
| `DB_SERVER` | Host/IP de base |
| `DB_NAME` | Nombre de base |
| `DB_USER` | Usuario read-only |
| `DB_PASSWORD` | Password de base |
| `DB_PORT` | Puerto de conexion |
| `MAIL_FROM` | Remitente del correo |
| `MAIL_TO` | Destinatarios generales |
| `USE_DATABASE_RECIPIENTS` | Habilita usar `sucursal.mail` como fallback |
| `EMAIL_DRY_RUN` | Modo preview sin envio real |
| `GUIDE_DUE_DATE_COLUMN` | Columna de fecha pactada |
| `GUIDE_LOOKAHEAD_DAYS` | Dias futuros a incluir |
| `GUIDE_LOOKBACK_DAYS` | Dias vencidos hacia atras a consultar |
| `GUIDE_MAX_ROWS` | Maximo de filas leidas para calcular totales |
| `SUCURSAL_RECIPIENTS_JSON` | Destinatarios por sucursal en GitHub |
| `SUCURSAL_GROUPS_JSON` | Nombres operativos por sucursal en GitHub |

## 16. Criterios de aceptacion funcional

El desarrollo se considera correcto cuando:

- El workflow puede ejecutarse manualmente desde GitHub.
- El runner self-hosted toma el job.
- La consulta trae guias desde `retiro`.
- La columna `Guia` del correo muestra `retiro.id`.
- No se muestra columna `Remito`.
- Cada sucursal recibe su correo consolidado.
- El asunto del correo muestra el nombre operativo de la sucursal.
- Las guias se separan en Critico, Proximas 48 horas y Proxima semana.
- Cada categoria muestra hasta 30 registros.
- Cada categoria informa cuantos registros muestra sobre el total.
- Los destinatarios se resuelven segun la configuracion por sucursal.

## 17. Pendientes recomendados

- Confirmar si la consulta real debe agregar cliente desde otra tabla.
- Confirmar si el estado debe mostrarse como descripcion y no como ID.
- Completar sucursales faltantes en el mapa funcional.
- Definir destinatarios finales por sucursal.
- Migrar historial de alertas a almacenamiento persistente.
- Instalar el runner como servicio de Windows para que quede activo luego de reinicios.
