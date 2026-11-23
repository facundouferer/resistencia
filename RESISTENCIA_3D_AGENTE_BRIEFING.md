# Resistencia 3D --- Guía de inicio para agentes de IA

**Proyecto:** Resistencia 3D -- Free World\
**Documento:** Briefing técnico y plan de primeras tareas\
**Versión:** 0.1\
**Motor:** Godot 4.x\
**Lenguaje principal:** GDScript\
**Plataforma inicial:** PC (Windows, Linux y macOS)\
**Estilo visual:** Híbrido: geografía real con edificios y recursos 3D
estilizados/realistas simplificados.

------------------------------------------------------------------------

## 1. Misión del agente

Actuá como **ingeniero principal de videojuegos y agente de
implementación** del proyecto Resistencia 3D.

Tu objetivo inicial es preparar una primera versión jugable de un mundo
libre basado en un sector real de Resistencia, Chaco, Argentina. El
primer escenario estará compuesto por **cuatro manzanas en una
cuadrícula de 2 × 2**, delimitadas por:

-   Calle Remedios de Escalada.
-   Calle Bartolomé Mitre.
-   Avenida Marcelo T. de Alvear.
-   Calle Corrientes.

El jugador debe poder iniciar el juego, aparecer en el escenario y
caminar libremente con una cámara en tercera persona.

No desarrolles todavía misiones, economía, NPC, tráfico, multijugador ni
sistemas de juego que no sean necesarios para recorrer y validar el
escenario.

**Prioridad absoluta:** construir una base técnica correcta,
verificable, modular y ampliable. No simules datos geográficos ni
afirmes que el escenario representa fielmente Resistencia hasta haber
importado y validado los datos reales.

## 2. Decisiones ya tomadas

No vuelvas a consultar estas decisiones salvo que encuentres una
incompatibilidad técnica real que debas explicar:

  -----------------------------------------------------------------------
  Área                                Decisión
  ----------------------------------- -----------------------------------
  Tipo de experiencia                 Mundo libre de exploración

  Motor                               Godot 4.x estable

  Lenguaje                            GDScript

  Plataforma                          PC

  Estilo                              Híbrido

  Escenario inicial                   Cuatro manzanas, cuadrícula 2 × 2

  Ciudad                              Resistencia, Chaco, Argentina

  Fuente geográfica principal         OpenStreetMap

  Escala                              1 unidad de Godot = 1 metro real

  Proyección de trabajo               WGS 84 / UTM zona 21S, EPSG:32721

  Formato de intercambio 3D           glTF 2.0 / GLB

  Herramientas de modelado            Blender

  Procesamiento geográfico            Python, QGIS y GDAL cuando sean
                                      necesarios

  Persistencia local inicial          Archivos JSON o SQLite, según el
                                      dato

  Jugador                             Un personaje controlable

  Cámara                              Tercera persona

  Conectividad                        El prototipo debe poder ejecutarse
                                      sin conexión una vez que sus
                                      recursos estén instalados
  -----------------------------------------------------------------------

La ubicación y geometría definitivas del área deberán verificarse con
datos cartográficos. Las calles mencionadas definen el área de trabajo,
pero no se deben inventar coordenadas, dimensiones, parcelas ni
edificios.

## 3. Visión del producto

El juego será un mundo persistente y editable que utiliza la geografía
real como punto de partida.

La ciudad y el videojuego deben estar desacoplados:

1.  Los datos geográficos describen la ciudad original.
2.  Un proceso de generación transforma esos datos en recursos 3D.
3.  Godot carga y presenta esos recursos.
4.  Los cambios realizados dentro del juego se almacenan separadamente
    de los datos originales.

Esta separación permitirá ampliar el mapa, regenerar sectores y
personalizar edificios sin perder el trabajo del jugador.

## 4. Alcance del primer prototipo

### Incluido

-   Proyecto Godot organizado y ejecutable.
-   Escena principal.
-   Escenario de prueba de cuatro manzanas.
-   Calles y veredas.
-   Huellas y volúmenes de edificios.
-   Colisiones básicas.
-   Personaje en tercera persona.
-   Movimiento hacia adelante, atrás y laterales.
-   Rotación y control de cámara con mouse.
-   Caminar y correr.
-   Iluminación diurna básica.
-   Punto de aparición del jugador.
-   Controles documentados.
-   Herramientas o scripts iniciales para importar y procesar datos
    geográficos.
-   Validaciones automáticas o manuales documentadas.

### Fuera de alcance por ahora

-   NPC y peatones.
-   Vehículos y tráfico.
-   Misiones y objetivos.
-   Inventario.
-   Economía.
-   Construcción avanzada.
-   Interiores de edificios.
-   Multijugador.
-   Clima dinámico.
-   Ciclo día/noche.
-   Simulación de negocios.
-   Expansión a toda Resistencia.

No agregues funcionalidades fuera de alcance sin autorización.

## 5. Principios de implementación

### 5.1. Geografía real, no escenario inventado

OpenStreetMap será la fuente inicial de calles, edificios y elementos
urbanos. Se debe conservar la atribución correspondiente y respetar la
licencia ODbL.

No uses Google Maps como fuente de extracción de modelos, texturas o
geometrías para el juego.

Si faltan datos de altura, pisos, materiales o uso de un edificio:

-   No inventes que el dato es real.
-   Aplicá una regla de estimación configurable.
-   Marcá el dato como estimado en los metadatos.
-   Permití reemplazar el modelo posteriormente.

### 5.2. Coordenadas y escala

-   Usá EPSG:32721 para el procesamiento métrico de la zona.
-   Definí un origen local estable para el escenario.
-   Convertí las coordenadas proyectadas a coordenadas locales de Godot.
-   Mantené la escala 1:1: un metro real equivale a una unidad del
    mundo.
-   Documentá el origen, la proyección y las transformaciones.
-   Evitá usar coordenadas geográficas de gran magnitud directamente
    como posiciones 3D.

En Godot, el plano horizontal suele representarse mediante X y Z,
mientras Y representa la altura. Documentá claramente la conversión
entre ejes geográficos y ejes del motor.

### 5.3. Mundo modular

Aunque el primer escenario sea pequeño, prepará la arquitectura para que
pueda crecer.

No construyas toda la ciudad dentro de una única escena monolítica.
Separá, como mínimo:

-   Terreno.
-   Calles.
-   Veredas.
-   Edificios.
-   Vegetación y mobiliario.
-   Jugador.
-   Sistemas de mundo.

No implementes un sistema complejo de streaming si todavía no es
necesario para el escenario de cuatro manzanas. Diseñá las interfaces
para poder incorporarlo después.

### 5.4. Recursos originales y modificaciones

Nunca sobrescribas los datos originales de OpenStreetMap con
modificaciones del juego.

Cada edificio u objeto debe poder identificarse de forma persistente.
Cuando sea posible, conservá el identificador de origen y el origen del
dato.

Las modificaciones del juego deben almacenarse como una capa separada:

-   Edificios reemplazados.
-   Edificios agregados.
-   Edificios eliminados.
-   Modelos personalizados.
-   Cambios de materiales o propiedades.

## 6. Arquitectura propuesta

La siguiente estructura es una propuesta inicial. Adaptala si encontrás
una razón técnica concreta, pero documentá cualquier cambio.

``` text
resistencia-3d/
├── project.godot
├── README.md
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   ├── controls.md
│   ├── geographic-data.md
│   └── progress.md
├── scenes/
│   ├── main/
│   │   └── main.tscn
│   ├── world/
│   │   ├── resistance_world.tscn
│   │   ├── streets.tscn
│   │   ├── sidewalks.tscn
│   │   └── buildings.tscn
│   └── player/
│       └── player.tscn
├── scripts/
│   ├── world/
│   │   ├── world_manager.gd
│   │   └── geo_reference.gd
│   ├── player/
│   │   ├── player_controller.gd
│   │   └── camera_controller.gd
│   └── buildings/
│       └── building_manager.gd
├── assets/
│   ├── materials/
│   ├── buildings/
│   ├── vegetation/
│   ├── props/
│   └── characters/
├── data/
│   ├── source/
│   ├── processed/
│   └── overrides/
├── generated/
│   └── resistencia/
├── tools/
│   ├── osm_importer/
│   ├── geo_processor/
│   ├── geometry_generator/
│   └── validators/
└── tests/
```

No es obligatorio crear directorios vacíos. Creá cada carpeta cuando
exista un recurso o componente que la justifique.

## 7. Sistemas principales de Godot

### WorldManager

Responsabilidades:

-   Crear o cargar el escenario.
-   Instanciar los componentes del mundo.
-   Administrar el punto de aparición.
-   Coordinar los subsistemas.
-   Exponer información básica del mundo para depuración.

### GeoReference

Responsabilidades:

-   Conocer la proyección y el origen local.
-   Convertir coordenadas proyectadas a posiciones de Godot.
-   Convertir posiciones de Godot a coordenadas proyectadas.
-   Evitar duplicar conversiones en otros módulos.

Incluí pruebas de ida y vuelta para verificar que las conversiones no
introduzcan errores significativos.

### PlayerController

Usá `CharacterBody3D`.

Controles iniciales sugeridos:

  Acción                   Tecla
  ------------------------ ---------------
  Avanzar                  W
  Retroceder               S
  Izquierda                A
  Derecha                  D
  Correr                   Shift
  Capturar/liberar mouse   Clic / Escape

El movimiento debe ser relativo a la orientación de la cámara o del
personaje, de forma consistente y documentada.

### CameraController

-   Cámara en tercera persona.
-   Rotación horizontal y vertical con mouse.
-   Límites verticales para evitar giros incómodos.
-   Distancia configurable.
-   Evitar que la cámara atraviese paredes cuando sea viable.

### BuildingManager

-   Cargar edificios generados.
-   Asociar identificadores persistentes.
-   Aplicar modificaciones guardadas.
-   Permitir reemplazar un modelo sin alterar la fuente geográfica.

No implementes todavía un editor visual de construcción.

## 8. Pipeline geográfico

El pipeline debe poder ejecutarse fuera de Godot y generar recursos que
el motor pueda importar.

Flujo esperado:

1.  Obtener datos de OpenStreetMap del área delimitada.
2.  Guardar los datos originales sin modificarlos.
3.  Validar y limpiar geometrías.
4.  Reproyectar a EPSG:32721.
5.  Definir el origen local del escenario.
6.  Extraer calles, huellas de edificios y elementos urbanos.
7.  Generar geometría 3D básica.
8.  Exportar modelos GLB y metadatos.
9.  Importar los recursos en Godot.
10. Validar posiciones, continuidad y colisiones.

### Datos mínimos por edificio

``` json
{
  "id": "identificador_persistente",
  "source": "openstreetmap",
  "source_id": "identificador_osm_si_existe",
  "footprint": [],
  "height_m": null,
  "levels": null,
  "height_is_estimated": true,
  "building_type": "unknown",
  "model": "generic_building"
}
```

El ejemplo es ilustrativo: no lo uses como dato real ni inventes
identificadores.

### Datos mínimos del escenario

Debe existir un archivo de metadatos con:

-   Nombre del escenario.
-   Fecha de generación.
-   Fuente de datos.
-   Licencia y atribución.
-   Proyección.
-   Origen geográfico.
-   Límites geográficos.
-   Unidades.
-   Versión del generador.
-   Lista de sectores o recursos generados.
-   Advertencias sobre datos faltantes.

## 9. Plan de trabajo: primeras acciones

Trabajá en orden. No avances a la siguiente etapa si la actual no cumple
sus criterios de aceptación.

### Fase 0 --- Inspección del entorno

1.  Inspeccioná el repositorio y los archivos existentes.
2.  Identificá la versión instalada de Godot.
3.  Verificá si el proyecto inicial ya contiene escenas o scripts.
4.  No sobrescribas archivos útiles sin inspeccionarlos.
5.  Si el proyecto no existe, creá uno nuevo.
6.  Registrá el estado inicial en `docs/progress.md`.

**Criterio de aceptación:** el agente conoce el estado real del
repositorio y puede abrir/importar el proyecto.

### Fase 1 --- Base ejecutable de Godot

1.  Configurá el proyecto para PC.
2.  Definí las acciones de entrada.
3.  Creá la escena principal.
4.  Creá un escenario temporal de prueba.
5.  Implementá un personaje con `CharacterBody3D`.
6.  Implementá cámara en tercera persona.
7.  Implementá caminar y correr.
8.  Agregá colisiones básicas.
9.  Documentá los controles.

**Criterios de aceptación:**

-   El proyecto importa sin errores.
-   La escena principal se ejecuta.
-   El personaje aparece en el escenario.
-   Se puede caminar y correr.
-   La cámara responde al mouse.
-   El personaje no atraviesa las superficies de colisión.
-   Escape libera el cursor.

### Fase 2 --- Obtener y validar la geografía real

1.  Consultá OpenStreetMap y otras fuentes geográficas abiertas cuando
    sean necesarias.
2.  Identificá el perímetro exacto definido por las cuatro calles.
3.  Verificá que el área contenga las cuatro manzanas pretendidas.
4.  Obtené las geometrías de calles y edificios.
5.  Registrá la fuente, fecha y licencia.
6.  Medí las dimensiones reales.
7.  Guardá una copia inalterada de los datos originales.

**Criterios de aceptación:**

-   Se identifican las cuatro manzanas.
-   Los límites y las calles están respaldados por datos verificables.
-   Las geometrías se pueden visualizar en un SIG o herramienta
    equivalente.
-   Las coordenadas y unidades están documentadas.
-   Las entidades faltantes o dudosas están informadas.

Si no se puede acceder a datos geográficos, detené esta fase y solicitá
al usuario los datos necesarios. No inventes coordenadas ni geometrías.

### Fase 3 --- Generar el escenario 3D

1.  Crear el terreno base.
2.  Generar calzadas.
3.  Generar veredas y esquinas.
4.  Generar huellas y volúmenes de edificios.
5.  Aplicar materiales híbridos básicos.
6.  Generar colisiones.
7.  Exportar recursos en formatos compatibles con Godot.
8.  Incorporar los metadatos geográficos.

**Criterios de aceptación:**

-   La forma y ubicación de las cuatro manzanas coincide con los datos
    geográficos.
-   Las calles conectan correctamente.
-   Las veredas no presentan huecos importantes.
-   Los edificios ocupan sus huellas correspondientes.
-   Las alturas reales y estimadas están diferenciadas.
-   Los recursos se importan sin errores.

### Fase 4 --- Integrar el escenario con el jugador

1.  Reemplazar el escenario temporal por el escenario geográfico.
2.  Ubicar el punto de aparición en una zona transitable.
3.  Ajustar escala y velocidad del personaje.
4.  Verificar colisiones.
5.  Recorrer todas las calles y veredas.
6.  Corregir discontinuidades.

**Criterios de aceptación:**

-   Se puede iniciar el juego directamente en el escenario real.
-   El jugador puede recorrer las cuatro manzanas.
-   No atraviesa edificios.
-   No queda atrapado en colisiones incorrectas.
-   La escala se siente coherente con distancias reales.

### Fase 5 --- Guardado mínimo

1.  Guardar la posición del jugador.
2.  Recuperar la posición al volver a iniciar.
3.  Separar los datos originales de las modificaciones.
4.  Documentar el formato de persistencia.

**Criterio de aceptación:** cerrar y abrir el juego conserva la posición
del jugador sin modificar los recursos originales.

## 10. Pruebas y validación

El agente debe ejecutar las verificaciones disponibles después de cada
cambio importante.

Como mínimo:

-   Importación del proyecto.
-   Análisis de errores de GDScript.
-   Ejecución de la escena principal.
-   Prueba de movimiento.
-   Prueba de cámara.
-   Prueba de colisiones.
-   Validación de coordenadas.
-   Validación de continuidad de calles.
-   Validación de metadatos.

Cuando sea posible, usá el ejecutable de Godot en modo headless para
validar importación y ejecución. Si una prueba requiere inspección
visual, informá que debe realizarse manualmente y no afirmes que pasó.

No declares una tarea terminada solamente porque escribiste el código.
Debe existir una prueba o una explicación clara de cómo verificarla.

## 11. Reglas de trabajo del agente

1.  **Hablar poco:** informar lo necesario, en español.
2.  **Trabajar por etapas:** no intentar implementar todo de una vez.
3.  **Inspeccionar antes de modificar:** respetar archivos y decisiones
    existentes.
4.  **Cambios pequeños:** preferir entregas incrementales y
    comprobables.
5.  **No inventar datos:** diferenciar datos reales, estimaciones y
    placeholders.
6.  **No ocultar errores:** informar bloqueos y pruebas fallidas.
7.  **No introducir dependencias innecesarias:** justificar cada
    herramienta o plugin agregado.
8.  **Mantener documentación:** actualizar arquitectura, decisiones y
    progreso.
9.  **Preservar datos originales:** nunca sobrescribir la fuente
    geográfica.
10. **No ampliar el alcance:** pedir autorización antes de agregar
    funcionalidades.
11. **No afirmar éxito sin verificar:** registrar qué se ejecutó y cuál
    fue el resultado.
12. **Usar control de versiones:** revisar cambios y generar commits
    descriptivos si el usuario lo autoriza.

## 12. Formato de reporte al finalizar cada tarea

El agente debe responder con un resumen breve:

``` text
TAREA:
Qué se intentó realizar.

RESULTADO:
Completado / Parcial / Bloqueado.

ARCHIVOS:
Archivos creados o modificados.

VALIDACIÓN:
Comandos ejecutados y resultados.

PENDIENTES:
Problemas o decisiones que requieren intervención.

SIGUIENTE PASO:
La próxima tarea concreta.
```

No presentar reportes extensos salvo que el usuario los solicite.

## 13. Comandos y herramientas

Antes de ejecutar comandos, detectá el sistema operativo y las
herramientas disponibles.

Comandos orientativos:

``` bash
godot --version
```

Validación headless orientativa:

``` bash
godot --headless --path . --editor --quit
```

Ejecución del proyecto:

``` bash
godot --path .
```

Los nombres de ejecutables pueden variar según la instalación. En macOS
puede ser necesario invocar el binario dentro de la aplicación Godot o
configurar su ruta.

No instales herramientas, descargues grandes conjuntos de datos ni
ejecutes comandos destructivos sin informar al usuario y obtener
autorización cuando corresponda.

## 14. Documentación oficial

-   Godot Engine: https://docs.godotengine.org/en/stable/
-   Godot CharacterBody3D:
    https://docs.godotengine.org/en/stable/classes/class_characterbody3d.html
-   Godot glTF:
    https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/index.html
-   OpenStreetMap: https://www.openstreetmap.org/
-   OpenStreetMap Copyright and License:
    https://www.openstreetmap.org/copyright
-   QGIS: https://www.qgis.org/
-   GDAL: https://gdal.org/
-   Blender: https://www.blender.org/

## 15. Primera instrucción para el agente

Comenzá exclusivamente por la **Fase 0 --- Inspección del entorno**.

Después:

1.  Informá qué encontraste en el repositorio.
2.  Confirmá la versión de Godot disponible.
3.  Identificá qué partes del prototipo existente pueden reutilizarse.
4.  Proponé un plan breve para completar la Fase 1.
5.  No avances a la Fase 2 ni descargues datos geográficos hasta que el
    usuario revise el diagnóstico.

**Objetivo final de esta primera sesión:** dejar el proyecto
inspeccionado, comprender su estado y tener un plan concreto para
conseguir una primera versión ejecutable.
