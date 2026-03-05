# 🔐 Issue #002 — Sistema de Autenticación JWT

**Fase**: 1 — Backend API  
**Prioridad**: 🔴 Alta  
**Etiquetas**: `backend`, `auth`, `seguridad`  
**Rama**: `feature/webapp-fase-1-auth`  
**Depende de**: #001

---

## 📋 Descripción

Implementar un sistema de autenticación basado en **JSON Web Tokens (JWT)** que restrinja el acceso al panel web exclusivamente a los administradores definidos en `apit.env` (`ADMIN_CHAT_IDS`).

El flujo será: el admin introduce usuario y contraseña en el frontend → el backend valida y devuelve un JWT → el frontend incluye el JWT en cada petición posterior.

---

## 🎯 Objetivos

- Endpoint `POST /api/auth/login` que valide credenciales y devuelva JWT
- Endpoint `GET /api/auth/me` que devuelva los datos del admin autenticado
- Middleware/dependencia `get_current_admin` reutilizable en todos los routers protegidos
- Configuración de usuario/contraseña admin en `apit.env` (hashed con bcrypt)
- Expiración configurable del token (default: 24h)

---

## 🔑 Variables de Entorno a Añadir

```env
# En apit.env
WEBAPP_ADMIN_USER="admin"
WEBAPP_ADMIN_PASSWORD_HASH="$2b$12$..."   # bcrypt hash
WEBAPP_SECRET_KEY="clave-secreta-aleatoria-larga"
WEBAPP_TOKEN_EXPIRE_HOURS=24
```

> ⚠️ Generar el hash con: `python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('tu_password'))"`

---

## 💻 Implementación

### `routers/auth.py`
```python
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import os

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SECRET_KEY = os.getenv("WEBAPP_SECRET_KEY")
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401)
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    admin_user = os.getenv("WEBAPP_ADMIN_USER")
    admin_hash = os.getenv("WEBAPP_ADMIN_PASSWORD_HASH")
    
    if form_data.username != admin_user or not pwd_context.verify(form_data.password, admin_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    expire_hours = int(os.getenv("WEBAPP_TOKEN_EXPIRE_HOURS", 24))
    token = create_access_token(
        data={"sub": form_data.username},
        expires_delta=timedelta(hours=expire_hours)
    )
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
async def me(current_admin: str = Depends(get_current_admin)):
    return {"username": current_admin, "role": "admin"}
```

---

## ✅ Criterios de Aceptación

- [ ] `POST /api/auth/login` devuelve JWT con credenciales correctas
- [ ] `POST /api/auth/login` devuelve 401 con credenciales incorrectas
- [ ] El JWT expira según `WEBAPP_TOKEN_EXPIRE_HOURS`
- [ ] Todos los endpoints de otros routers que usen `Depends(get_current_admin)` rechazan peticiones sin token válido con 401
- [ ] La contraseña **nunca** se almacena en texto plano
- [ ] El `SECRET_KEY` se lee desde variable de entorno, nunca hardcodeado

---

## 🔗 Dependencias

- Issue #001 (setup base del proyecto)

---

## 📝 Notas de Seguridad

- Rotar el `WEBAPP_SECRET_KEY` cada 90 días
- En producción, el token debe transmitirse solo por HTTPS (Issue #013)
- Considerar añadir refresh tokens en una versión futura
