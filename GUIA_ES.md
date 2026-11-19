# Guía rápida: Notifications Service (Proyecto 4)

## Correrlo

```bash
docker compose up --build
```

Abre http://localhost:8000/docs y en otra terminal mira el worker:

```bash
docker compose logs -f worker
```

Crea una notificación con `"recipient": "down@fail.test"` y observa en los logs cómo se reintenta 5 veces con esperas cada vez más largas y al final queda en `failed`. Luego usa `POST /notifications/{id}/retry`.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Qué debes poder explicar en una entrevista

- **Procesamiento asíncrono:** por qué la API responde 202 y no espera a que se envíe el correo.
- **Colas:** qué hacen Redis (broker) y Celery (worker), y qué pasa si el worker está apagado cuando llega una notificación.
- **Reintentos:** qué es el backoff exponencial y por qué no conviene reintentar de inmediato.
- **`task_acks_late`:** qué pasa si el worker se cae a mitad de un envío.
- **MongoDB vs SQL:** por qué un documento flexible (`metadata`) encaja aquí.
- **Logs estructurados:** ventaja de los logs en JSON frente a texto plano.
- **Testing:** cómo `mongomock` y `httpx.MockTransport` permiten probar sin servicios reales.

## Retos para hacerlo tuyo

1. **Fácil:** canal `sms` simulado.
2. **Fácil:** endpoint `GET /notifications/stats` con conteo por estado (usa `aggregate` de MongoDB).
3. **Medio:** envío real de correos con SMTP (Mailtrap para pruebas).
4. **Medio:** notificaciones programadas (`send_at`) usando `apply_async(eta=...)`.
5. **Avanzado:** firmar los webhooks con HMAC para que el receptor verifique el origen.
