# Servicios Systemd para BBAlert

Este directorio contiene las plantillas de los servicios systemd para ejecutar BBAlert como demonios en segundo plano.

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `bbalert-staging.service` | Servicio para el entorno de staging (rama testing) |
| `bbalert-prod.service` | Servicio para el entorno de producción (rama main) |

## Instalación

### 1. Personalizar los archivos

Antes de instalar, reemplaza `USUARIO` con tu nombre de usuario real:

```bash
# Obtener tu nombre de usuario
echo $USER

# Reemplazar en los archivos
sed -i 's/USUARIO/tu_usuario_real/g' bbalert-staging.service
sed -i 's/USUARIO/tu_usuario_real/g' bbalert-prod.service
```

### 2. Copiar los servicios al sistema

```bash
# Copiar archivos de servicio
sudo cp bbalert-staging.service /etc/systemd/system/
sudo cp bbalert-prod.service /etc/systemd/system/

# Recargar configuración de systemd
sudo systemctl daemon-reload
```

### 3. Habilitar servicios (inicio automático)

```bash
# Habilitar servicio de staging
sudo systemctl enable bbalert-staging

# Habilitar servicio de producción
sudo systemctl enable bbalert-prod
```

### 4. Iniciar servicios

```bash
# Iniciar staging
sudo systemctl start bbalert-staging

# Iniciar producción
sudo systemctl start bbalert-prod
```

## Comandos de Gestión

| Acción | Staging | Producción |
|--------|---------|------------|
| Iniciar | `sudo systemctl start bbalert-staging` | `sudo systemctl start bbalert-prod` |
| Detener | `sudo systemctl stop bbalert-staging` | `sudo systemctl stop bbalert-prod` |
| Reiniciar | `sudo systemctl restart bbalert-staging` | `sudo systemctl restart bbalert-prod` |
| Estado | `sudo systemctl status bbalert-staging` | `sudo systemctl status bbalert-prod` |
| Logs | `sudo journalctl -u bbalert-staging -f` | `sudo journalctl -u bbalert-prod -f` |

## Verificación

```bash
# Verificar que los servicios están habilitados
systemctl is-enabled bbalert-staging
systemctl is-enabled bbalert-prod

# Verificar estado
sudo systemctl status bbalert-staging
sudo systemctl status bbalert-prod

# Ver logs recientes
sudo journalctl -u bbalert-staging -n 50
sudo journalctl -u bbalert-prod -n 50
```

## Probar Reinicio Automático

```bash
# Encontrar el PID del proceso
pgrep -f "bbalert-staging.*bbalert.py"

# Matar el proceso para simular un fallo
sudo kill -9 <PID>

# Esperar 10-15 segundos y verificar que se reinició
sudo systemctl status bbalert-staging
```

## Consideraciones de Seguridad

### Permisos de archivos

```bash
# Asegurar permisos correctos en los directorios
chown -R USUARIO:USUARIO ~/bbalert-staging
chown -R USUARIO:USUARIO ~/bbalert-prod

# Proteger archivos de configuración
chmod 600 ~/bbalert-staging/bbalert/.env
chmod 600 ~/bbalert-prod/bbalert/.env
```

## Troubleshooting

| Problema | Solución |
|----------|----------|
| El servicio no inicia | Verificar permisos y rutas en el archivo .service |
| Error de Python | Verificar que el entorno virtual tiene todas las dependencias |
| El servicio se reinicia constantemente | Verificar logs con `journalctl -u <servicio> -n 50` |
| Error de permisos | Verificar que el usuario tiene acceso a todos los archivos |
