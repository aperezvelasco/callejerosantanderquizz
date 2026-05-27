# Guía de Despliegue de SantandercallejerIA

Esta guía detalla las mejores opciones **gratuitas** y de bajo costo para desplegar tu aplicación web construida con FastAPI y SQLAlchemy.

---

## Resumen de Opciones de Hosting Gratis

| Plataforma | Tipo de Hosting | Almacenamiento (SQLite) | Base de Datos Alternativa | Pros / Contras |
| :--- | :--- | :--- | :--- | :--- |
| **Render** | Contenedor PaaS (Gratis) | **Efímero** (se borra al reiniciar) | PostgreSQL externa (Neon) | + Muy fácil de usar, despliegue directo desde GitHub.<br>- La máquina "se duerme" tras 15 min de inactividad. |
| **Koyeb** | Contenedor PaaS (Gratis) | **Efímero** (se borra al reiniciar) | PostgreSQL externa (Neon) | + Excelente rendimiento, despliegue rápido desde GitHub.<br>- Requiere base de datos externa para no perder datos. |
| **Oracle Cloud** | VPS (Siempre Gratis) | **Persistente** (Disco gratuito de hasta 200GB) | SQLite local o Postgres | + 100% de control, IP pública estática gratuita.<br>- Curva de aprendizaje técnica alta (consola de comandos Linux). |
| **PythonAnywhere**| Shared Hosting (Gratis) | **Persistente** (SQLite local) | MySQL/PostgreSQL | + SQLite funciona sin perder datos.<br>- No soporta ASGI de forma nativa (requiere adaptador WSGI). |

---

## La Arquitectura Recomendada (Gratis y Robusta)

Dado que las plataformas en la nube gratuitas (como Render o Koyeb) destruyen y reconstruyen los contenedores cada vez que se reinicia el servidor o entra en reposo, **guardar el archivo de SQLite localmente hará que las puntuaciones y usuarios se borren periódicamente**.

Para solucionar esto de manera gratuita, la arquitectura ideal es:
1. **Servidor Web**: **Render** (Servicio web gratuito).
2. **Base de Datos**: **Neon (neon.tech)** (PostgreSQL administrada con capa gratuita generosa).

Como estás usando SQLAlchemy, cambiar de SQLite a PostgreSQL es sumamente sencillo y no requiere alterar la lógica de tus modelos.

---

## Paso a Paso: Despliegue con Render + Neon

### Paso 1: Crear la Base de Datos en Neon
1. Regístrate en [Neon.tech](https://neon.tech/) usando tu cuenta de GitHub.
2. Crea un nuevo proyecto. Selecciona **PostgreSQL v16** y la región más cercana (ej. `Frankfurt` o `Ireland` para España).
3. Copia la cadena de conexión (Connection String). Se verá parecida a esto:
   `postgresql://alex:password@ep-cool-water-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require`

### Paso 2: Preparar el Código en tu Repositorio
Para que FastAPI funcione con PostgreSQL en producción, añade el driver de Postgres (`psycopg2-binary`) en tus dependencias:
1. Agrega la dependencia ejecutando:
   ```bash
   pixi add psycopg2-binary
   ```
2. Asegúrate de subir tus cambios a tu repositorio de GitHub (este debe ser público o privado, Render puede conectarse a ambos).

### Paso 3: Configurar el Servidor en Render
1. Regístrate en [Render.com](https://render.com/) e inicia sesión con tu cuenta de GitHub.
2. Haz clic en **New +** y selecciona **Web Service**.
3. Conecta tu repositorio de GitHub.
4. Rellena los detalles del servicio web:
   - **Name**: `santander-callejer-ia`
   - **Region**: `Frankfurt (EU Central)`
   - **Branch**: `main` (o tu rama principal)
   - **Runtime**: **Docker** (Render detectará automáticamente el `Dockerfile` del repositorio. Esto es **obligatorio** ya que el proyecto usa librerías geoespaciales como GeoPandas y OSMnx, las cuales requieren dependencias del sistema C complejas que ya están configuradas en nuestra imagen Docker de Pixi).
   - **Instance Type**: Selecciona el plan **Free** ($0/month).

### Paso 4: Configurar Variables de Entorno en Render
En la pestaña de configuración del Web Service en Render, ve a la sección **Environment** y añade las siguientes variables:
- `DATABASE_URL`: Pega la cadena de conexión que copiaste de Neon.
  > [!WARNING]
  > Si tu cadena de conexión empieza por `postgres://`, SQLAlchemy requiere que la modifiques para usar `postgresql://` (con "ql" al final). Nuestro backend ya corrige esto automáticamente, pero es recomendable guardarlo directamente en formato `postgresql://`.
- `DAILY_QUESTIONS`: `3`
- `PORT`: `8000`

### Paso 5: Desplegar
Render compilará tu aplicación y la pondrá en línea. Te dará una URL pública tipo `https://santander-callejer-ia.onrender.com`.

---

## Opción Alternativa: Despliegue en un VPS Gratis (Oracle Cloud)

Si quieres seguir usando SQLite y tener el 100% de control sin que el servidor se duerma jamás:
1. Crea una cuenta en **Oracle Cloud**.
2. Provisiona una instancia de Computación bajo la modalidad **Siempre Gratis** (Always Free VM. Standard.A1.Flex con procesador ARM Ampere).
3. Instala Linux (Ubuntu es recomendado), Git y Pixi:
   ```bash
   curl -fsSL https://pixi.sh/install.sh | bash
   ```
4. Clona tu repositorio, descarga los datos urbanos y ejecuta la aplicación usando `systemd` para mantenerla activa en segundo plano.
5. Abre el puerto `80` o `443` en las Reglas de Entrada de la subred de Oracle para dar acceso a los usuarios.
