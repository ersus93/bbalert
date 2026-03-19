# Plan: Mejorar botón "Añadir" del comando /prices

## Objetivo
Hacer que el botón "Añadir" del comando /prices funcione similar al de /alertas:
- Al hacer click, mostrar mensaje con el formato para añadir monedas
- El usuario puede responder de dos formas:
  - Usando comando: `/prices BTC,ETH` o `/prices add BTC,ETH`
  - Sin comando: `BTC,ETH` o `BTC ETH`
- Después de añadir, volver automáticamente a la lista de precios

## Cambios necesarios en `handlers/prices.py`

### 1. Modificar `_handle_add_button()` 
- Cambiar para mostrar mensaje con formato de ayuda (similar a alertas_create_callback)
- NO iniciar ConversationHandler
- Mostrar mensaje con las dos opciones de formato

### 2. Crear `prices_text_handler()`
- Nuevo MessageHandler para detectar texto válido
- Similar a `alertas_text_handler` en alertas.py
- Detectar formato: "BTC,ETH" o "BTC ETH" (monedas separadas por coma o espacio)
- Procesar y añadir las monedas
- Mostrar mensaje de éxito con botones para volver o añadir más

### 3. Modificar `prices_add_conversation_handler`
- Eliminar o simplificar el flujo de conversación
- Dejar solo los fallbacks (/cancel, /done)

### 4. Registrar handlers en bbalert.py
- Añadir prices_text_handler (MessageHandler)
- Verificar que los callbacks estén correctamente registrados

## Formato del mensaje de ayuda (igual a alertas)
```
➕ *Añadir monedas*
————————————————————

*Opción 1 - Comando completo:*
`/prices BTC,ETH,SOL`

*Opción 2 - Solo símbolos:*
`BTC ETH SOL`
o
`BTC,ETH,SOL`

_Envía las monedas que quieres seguir._
```

## Flujo de ejecución
1. Usuario hace click en "➕ Añadir"
2. Se muestra mensaje con formato de ayuda
3. Usuario envía texto (BTC,ETH o con comando)
4. Se detectan las monedas y se añaden
5. Se muestra mensaje de éxito con botón para volver a precios
