# 🗺️ SantandercallejerIA

**SantandercallejerIA** es una aplicación web interactiva diseñada para desafiar y evaluar tu conocimiento del callejero del municipio de Santander, Cantabria, España. A través de un mapa ciego interactivo y un quiz de preguntas de opción múltiple generadas de forma determinista a partir de los datos oficiales de OpenStreetMap, los jugadores ponen a prueba su orientación y geolocalización.

---

## 🌟 Características Principales

### 1. Sistema de Juego y Progresión Secuencial
La aplicación implementa una máquina de estados en el frontend que guía al usuario a través del reto diario:
1.  **Página de Inicio / Registro e Inicio de Sesión**:
    *   Explicación de las reglas del juego.
    *   Formulario de registro con doble verificación de correo electrónico y login tradicional por email/contraseña. (Acceso restringido a usuarios registrados).
2.  **Fase 1: El Mapa Ciego (10 Intentos Diarios)**:
    *   Se le presenta al usuario una calle de Santander de forma aleatoria.
    *   Debe marcar un punto en un mapa mudo interactivo (Leaflet).
    *   Se calcula la distancia exacta y se otorgan **30 puntos por acierto** (margen <= 15 metros).
3.  **Fase 2: El Quiz Diario (3 Preguntas)**:
    *   Preguntas de opción múltiple (A-B-C-D) generadas para el día actual.
    *   Tipos de pregunta:
        *   `PATH`: Secuencia correcta de calles para el trayecto más corto entre dos puntos.
        *   `INTERSECTS`: Identificar la calle que intersecta con una vía específica.
        *   `COUNT`: Número de calles secundarias que cruzan una calle dada.
    *   Cada acierto otorga **100 puntos**.
4.  **Fase 3: Clasificación**:
    *   Una vez completadas ambas fases de juego, se bloquea el acceso a nuevas partidas y se muestra la tabla de clasificación global sumando los puntos totales acumulados.

### 2. Puntuación Diaria
*   **Mapa Ciego**: 10 calles × 30 puntos = **300 puntos** máx.
*   **Quiz Diario**: 3 preguntas × 100 puntos = **300 puntos** máx.
*   **Total Diario**: **600 puntos** disponibles por usuario.

---

## 📁 Estructura del Proyecto

```text
.
├── app/
│   ├── core/              # Configuración y variables de entorno de la API
│   ├── routers/           # Controladores de FastAPI (usuarios y quiz/juego)
│   ├── services/          # Cargador del callejero y motor de generación de preguntas
│   ├── database.py        # Configuración del motor de SQLAlchemy y sesiones
│   ├── main.py            # Punto de entrada de FastAPI
│   ├── models.py          # Modelos de base de datos relacionales (SQLite/Postgres)
│   └── schemas.py         # Schemas de validación Pydantic
├── data/                  # Fronteras del municipio y archivos GeoJSON
├── static/                # Frontend SPA (HTML, CSS y JS con Leaflet)
├── tests/                 # Pruebas automatizadas de lógica y endpoints
├── pyproject.toml         # Especificación del paquete y dependencias del entorno
├── Dockerfile             # Configuración para despliegue en contenedores
└── .pre-commit-config.yaml # Configuración de herramientas de control de calidad (QA)
```

---

## ⚙️ Requisitos e Instalación

Este proyecto utiliza **Pixi** como gestor de paquetes y entornos de desarrollo, asegurando que todas las dependencias del sistema y de Python sean idénticas y reproducibles.

### 1. Clonar el repositorio
```bash
git clone git@github.com:aperezvelasco/callejerosantanderquizz.git
cd callejerosantanderquizz
```

### 2. Configurar el entorno de Pixi
Para descargar e instalar todas las dependencias de Python y del sistema, ejecuta:
```bash
pixi install
```

---

## 🚀 Ejecutar la Aplicación

Inicia el servidor de desarrollo de FastAPI utilizando Uvicorn:
```bash
export PYTHONPATH="."
pixi run -e dev python -m uvicorn app.main:app --reload
```
Una vez iniciado, abre tu navegador en [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una amplia suite de pruebas para el motor de grafos y endpoints de autenticación:
```bash
export PYTHONPATH="."
pixi run -e dev pytest
```

---

## 🛠️ Buenas Prácticas y Control de Calidad (QA)

Hemos integrado **pre-commit** para garantizar la calidad del código e impedir fugas de credenciales en el repositorio:

### Instalar los git hooks
```bash
pixi run pre-commit install
```

### Ejecutar las verificaciones manualmente
```bash
pixi run pre-commit run --all-files
```

Las herramientas ejecutadas en el hook de pre-commit son:
*   **ruff / ruff-format**: Formateo y linting de código Python rápido.
*   **mypy**: Comprobación estática de tipos con soporte para tipos ORM de SQLAlchemy.
*   **gitleaks**: Escaneo en busca de secretos, claves privadas o credenciales expuestas.
*   **Verificaciones de formato**: Limpieza de espacios en blanco y saltos de línea al final del archivo.

---

## 📦 Despliegue

La aplicación se puede empaquetar de forma nativa en un contenedor Docker utilizando el `Dockerfile` incluido, facilitando su despliegue en plataformas como Render, Heroku o Railway.
