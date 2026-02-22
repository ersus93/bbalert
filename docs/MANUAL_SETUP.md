# Guía de Configuración Manual

Este documento contiene las instrucciones detalladas para completar las tareas manuales de configuración del proyecto BBAlert.

---

## Issue #2: Configurar Branch Protection Rules

### Ubicación
GitHub → Repositorio `ersus93/bbalert` → **Settings** → **Branches** → **Add branch protection rule**

### Rama: `main` (Producción)

1. Ir a **Settings** → **Branches** → **Add branch protection rule**
2. En "Branch name pattern" escribir: `main`
3. Configurar las siguientes opciones:

   #### Protect matching branches
   - [x] **Require a pull request before merging**
     - [x] Require approvals: `1`
     - [x] Dismiss stale pull request approvals when new commits are pushed
     - [x] Require review from Code Owners (opcional)
   
   - [x] **Require status checks to pass before merging**
     - [x] Require branches to be up to date before merging
   
   - [x] **Do not allow bypassing the above settings**
   
   #### Rules applied to everyone including administrators
   - [x] **Allow force pushes** → NO (desmarcar)
   - [x] **Allow deletions** → NO (desmarcar)

4. Click en **Create**

### Rama: `testing` (Staging)

1. **Add branch protection rule**
2. Branch name pattern: `testing`
3. Configurar:
   - [x] **Require a pull request before merging**
   - [x] **Do not allow bypassing the above settings**
   - **Allow force pushes** → NO
   - **Allow deletions** → NO
4. Click en **Create**

### Rama: `dev` (Desarrollo)

1. **Add branch protection rule**
2. Branch name pattern: `dev`
3. Configurar:
   - [x] **Require a pull request before merging**
   - [x] **Do not allow bypassing the above settings**
   - **Allow force pushes** → NO
4. Click en **Create**

### Verificación

```bash
# Verificar las reglas configuradas
gh api repos/ersus93/bbalert/branches/main/protection
```

---

## Issue #3: Preparar Entornos Staging y Producción en VPS

### Prerrequisitos
- Acceso SSH al VPS
- Python 3.10+ instalado
- Git instalado

### Paso 1: Conectar al VPS

```bash
ssh usuario@tu-vps-ip
```

### Paso 2: Crear estructura de directorios

```bash
# Crear directorios principales
mkdir -p ~/bbalert-staging
mkdir -p ~/bbalert-prod
mkdir -p ~/scripts

# Verificar creación
ls -la ~ | grep bbalert
```

### Paso 3: Configurar entorno de Staging

```bash
# Clonar repositorio
cd ~/bbalert-staging
git clone https://github.com/ersus93/bbalert.git

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
cd bbalert
pip install -r requirements.txt

# Verificar instalación
python -c "import telegram; print('OK')"

# Cambiar a rama testing
git checkout testing
git pull origin testing

# Desactivar entorno virtual
deactivate
```

### Paso 4: Configurar entorno de Producción

```bash
# Clonar repositorio
cd ~/bbalert-prod
git clone https://github.com/ersus93/bbalert.git

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
cd bbalert
pip install -r requirements.txt

# Verificar instalación
python -c "import telegram; print('OK')"

# Asegurar estar en rama main
git checkout main
git pull origin main

# Desactivar entorno virtual
deactivate
```

### Paso 5: Configurar archivos .env

#### Staging
```bash
# Copiar ejemplo
cp ~/bbalert-staging/bbalert/apit.env.example ~/bbalert-staging/bbalert/.env

# Editar con las credenciales del bot de pruebas
nano ~/bbalert-staging/bbalert/.env
```

Contenido del `.env` para staging:
```env
BOT_TOKEN=tu_bot_token_de_pruebas
ADMIN_IDS=tu_id_de_telegram
# Otras variables según apit.env.example
```

#### Producción
```bash
# Copiar ejemplo
cp ~/bbalert-prod/bbalert/apit.env.example ~/bbalert-prod/bbalert/.env

# Editar con las credenciales del bot de producción
nano ~/bbalert-prod/bbalert/.env
```

### Paso 6: Configurar permisos

```bash
# Permisos para directorios
chown -R $USER:$USER ~/bbalert-staging
chown -R $USER:$USER ~/bbalert-prod

# Proteger archivos .env
chmod 600 ~/bbalert-staging/bbalert/.env
chmod 600 ~/bbalert-prod/bbalert/.env

# Verificar permisos
ls -la ~/bbalert-staging/bbalert/.env
ls -la ~/bbalert-prod/bbalert/.env
```

### Paso 7: Copiar scripts de despliegue

```bash
# Crear directorio de scripts si no existe
mkdir -p ~/scripts

# Copiar scripts desde el repositorio
cp ~/bbalert-staging/bbalert/scripts/deploy-staging.sh ~/scripts/
cp ~/bbalert-staging/bbalert/scripts/deploy-prod.sh ~/scripts/

# Dar permisos de ejecución
chmod +x ~/scripts/deploy-staging.sh
chmod +x ~/scripts/deploy-prod.sh

# Verificar
ls -la ~/scripts/
```

### Paso 8: Probar instalación

```bash
# Probar staging
cd ~/bbalert-staging/bbalert
source ../venv/bin/activate
python bbalert.py &
# Verificar que inicia correctamente, luego detener con Ctrl+C
deactivate

# Probar producción
cd ~/bbalert-prod/bbalert
source ../venv/bin/activate
python bbalert.py &
# Verificar que inicia correctamente, luego detener con Ctrl+C
deactivate
```

### Paso 9: Instalar servicios systemd

```bash
# Copiar archivos de servicio
sudo cp ~/bbalert-staging/bbalert/systemd/bbalert-staging.service /etc/systemd/system/
sudo cp ~/bbalert-staging/bbalert/systemd/bbalert-prod.service /etc/systemd/system/

# Reemplazar USUARIO con tu nombre de usuario real
sudo sed -i "s/USUARIO/$USER/g" /etc/systemd/system/bbalert-staging.service
sudo sed -i "s/USUARIO/$USER/g" /etc/systemd/system/bbalert-prod.service

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar servicios (inicio automático)
sudo systemctl enable bbalert-staging
sudo systemctl enable bbalert-prod

# Verificar que están habilitados
systemctl is-enabled bbalert-staging
systemctl is-enabled bbalert-prod
```

### Paso 10: Iniciar servicios

```bash
# Iniciar staging
sudo systemctl start bbalert-staging
sudo systemctl status bbalert-staging

# Si está OK, iniciar producción
sudo systemctl start bbalert-prod
sudo systemctl status bbalert-prod
```

---

## Verificación Final

### Comandos de verificación

```bash
# Verificar directorios
ls -la ~/bbalert-staging/bbalert/bbalert.py
ls -la ~/bbalert-prod/bbalert/bbalert.py

# Verificar entornos virtuales
ls -la ~/bbalert-staging/venv/bin/python
ls -la ~/bbalert-prod/venv/bin/python

# Verificar servicios
sudo systemctl status bbalert-staging
sudo systemctl status bbalert-prod

# Verificar logs
sudo journalctl -u bbalert-staging -n 20
sudo journalctl -u bbalert-prod -n 20
```

### Comandos útiles

| Acción | Comando |
|--------|---------|
| Ver estado staging | `sudo systemctl status bbalert-staging` |
| Ver estado producción | `sudo systemctl status bbalert-prod` |
| Ver logs staging | `sudo journalctl -u bbalert-staging -f` |
| Ver logs producción | `sudo journalctl -u bbalert-prod -f` |
| Reiniciar staging | `sudo systemctl restart bbalert-staging` |
| Reiniciar producción | `sudo systemctl restart bbalert-prod` |
| Actualizar staging | `~/scripts/deploy-staging.sh` |
| Actualizar producción | `~/scripts/deploy-prod.sh` |

---

## Checklist Final

### Issue #2 - Branch Protection Rules
- [ ] Rama `main` protegida con PR + 1 aprobación
- [ ] Rama `testing` protegida con PR requerido
- [ ] Rama `dev` protegida con PR requerido
- [ ] Force push deshabilitado en todas las ramas

### Issue #3 - Entornos VPS
- [ ] Directorio `~/bbalert-staging` creado
- [ ] Directorio `~/bbalert-prod` creado
- [ ] Repositorio clonado en ambos directorios
- [ ] Entornos virtuales creados
- [ ] Dependencias instaladas
- [ ] Archivos `.env` configurados
- [ ] Scripts de despliegue copiados
- [ ] Servicios systemd instalados y habilitados
- [ ] Servicios iniciados y funcionando
