# WUF Predict - documentación de arquitectura

Este directorio convierte el avance académico y el prototipo navegable en una guía de implementación. El PDF es la fuente de requisitos, historias de usuario, modelo de datos y tecnologías; `../prototipo/` es referencia visual y de navegación. Para la versión actual de HU01, el Analista importa CSV de demostración manualmente; PostgreSQL mantiene el catálogo vigente y el historial de snapshots. La carpeta/estructura descrita en `02-arquitectura.md` refleja el proyecto presente, no una estructura futura.

## Documentos

1. [Visión, alcance y requisitos](01-vision-requisitos.md): objetivos, RF, HU, roles y trazabilidad.
2. [Arquitectura y decisiones](02-arquitectura.md): tres capas, componentes, flujos, API y estructura actual.
3. [Modelo de datos](03-modelo-datos.md): diccionario físico extraído y recomendaciones de integridad.
4. [Plan de implementación por HU](04-modulos-hu.md): módulos incrementales, dependencias y criterios verificables.
5. [Estándares de desarrollo y seguridad](05-estandares.md): prácticas de código, validación, configuración, UI y operación.
6. [HU01 — Implementación de recolección](10-hu01-recoleccion.md): componentes, endpoints, migración, configuración e inicio local.
7. [Guía de inicio local](11-inicio-local.md): requisitos, instalación de dependencias y pasos para arrancar backend y frontend en Windows.

## Convenciones

- Los elementos marcados **Definido en el avance** proceden del PDF.
- Los elementos marcados **Decisión de implementación** son una propuesta para hacer ejecutable el diseño; deben conservarse trazables y revisarse si contradicen una definición formal posterior.
- El prototipo es una guía visual. Las cifras y registros utilizados por el sistema se consultan desde la base de datos.

## Orden de lectura

Leer primero visión y alcance, luego modelo de datos y arquitectura. Implementar las historias en orden de dependencia indicado en `04-modulos-hu.md`; los criterios de HU09 son transversales.
