# Changelog

Todas las versiones notables de este proyecto serán documentadas en este archivo.

## [Unreleased]

## [1.0.0] - 2026-02-24

### ✨ Nuevas Funcionalidades

- **Flujo de Trabajo Git**: Implementación completa del flujo de trabajo Git con ramas `dev`, `testing` y `main` para un desarrollo más organizado.

- **Script de Gestión Mejorado (mbot.sh)**: El anterior `bbalertv3.sh` ha sido renombrado y mejorado con nuevas funcionalidades para gestión de entornos staging y producción.

- **Actualización Automática de Versión**: El bot ahora ejecuta automáticamente `update_version.py` al iniciar o reiniciar, manteniendo el número de versión actualizado.

- **Plantillas de Servicios Systemd**: Nuevas plantillas para despliegue en staging y producción (`bbalert-staging.service`, `bbalert-prod.service`).

- **Scripts de Despliegue**: Nuevos scripts `deploy-staging.sh` y `deploy-prod.sh` para facilitar el despliegue en diferentes entornos.

- **Plantilla de Pull Request**: Nueva plantilla estandarizada para Pull Requests en `.github/PULL_REQUEST_TEMPLATE.md`.

### 🔧 Mejoras

- **Simplificación del Flujo de Trabajo**: Se unificó la rama `desarrollo` en `dev` para simplificar el flujo de trabajo.

- **Configuración de Admin**: Corregido el tipo de `ADMIN_CHAT_IDS` y eliminado código duplicado.

### 🐛 Correcciones

- **Importaciones Faltantes**: Agregadas importaciones faltantes de `logger` y `add_log_line` en varios módulos.

- **Trading - Comando de Precio**: Corregido el manejo de consultas de callback en el comando de precio.

### 📦 Dependencias

- Actualizado `requirements.txt` con las dependencias necesarias.

### 🗂️ Archivos Nuevos

- `update_version.py` - Script para actualización automática de versión
- `version.txt` - Archivo con la versión actual del proyecto
- `scripts/deploy-prod.sh` - Script de despliegue a producción
- `scripts/deploy-staging.sh` - Script de despliegue a staging
- `systemd/bbalert-prod.service` - Servicio systemd para producción
- `systemd/bbalert-staging.service` - Servicio systemd para staging
- `systemd/README.md` - Documentación de los servicios systemd
- `plans/git-workflow-plan.md` - Plan detallado del flujo de trabajo Git
- `plans/code-improvement-plan.md` - Plan de mejoras de código
- `plans/update-version-fix-plan.md` - Plan para la corrección de actualización de versión

---

## Notas de Versión

### Cómo Interpretar Este Changelog

- **✨ Nuevas Funcionalidades**: Características completamente nuevas
- **🔧 Mejoras**: Mejoras a funcionalidades existentes
- **🐛 Correcciones**: Correcciones de bugs
- **📦 Dependencias**: Cambios en dependencias
- **🗂️ Archivos Nuevos**: Nuevos archivos añadidos al proyecto

---

[Unreleased]: https://github.com/ersus93/bbalert/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ersus93/bbalert/releases/tag/v1.0.0
