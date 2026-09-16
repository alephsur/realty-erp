# Roadmap de producto — Realty ERP

Fecha: 14 de septiembre de 2026. Actualización: 15 de septiembre de 2026. Estado: F0-01 completada; F0-02 implementada con pruebas automatizadas; el resto del roadmap sigue pendiente.

## Objetivo de producto

Convertir Realty ERP en una herramienta que ayude a las agencias a dar seguimiento a cada oportunidad, anticipar bloqueos de las operaciones y demostrar al propietario el valor del trabajo realizado.

El segmento inicial propuesto son agencias de compraventa residencial en España. La gestión recurrente de alquileres, comunidades y promociones queda fuera de esta primera evolución para mantener un alcance coherente.

La diferenciación se buscará en tres resultados: menos oportunidades desatendidas, mejor coordinación hasta la firma y captación orientada por compradores reales. Las integraciones, las fotografías y los documentos son requisitos de uso cotidiano que deben acompañar esa propuesta.

## Supuestos y planificación

- Equipo de referencia: dos desarrolladores a tiempo completo, con participación semanal de una persona de producto y apoyo puntual de diseño y pruebas.
- Validación con tres a cinco agencias piloto, empezando con sus procesos y casos reales.
- Las duraciones son rangos orientativos por fase, no compromisos de entrega. Incluyen implementación y validación funcional del alcance descrito, pero no esperas de acceso a proveedores, migraciones complejas o cambios de alcance.
- Las fases se ordenan secuencialmente. Las entrevistas y la evaluación de integraciones pueden avanzar durante las fases de desarrollo.
- P0: necesario para operar con fiabilidad. P1: núcleo de la propuesta de valor. P2: ampliación condicionada por resultados y datos.
- Cada fase termina con una decisión de continuar, ajustar o reducir alcance según la evidencia del piloto.

| Fase | Prioridad | Duración estimada | Entrega principal | Dependencia |
|---|---|---|---|---|
| 0. Fiabilidad y definición | P0 | 1–2 semanas | Cierre coherente, compilación y métricas verificables | Ninguna |
| 1. Datos y trabajo diario | P0 | 3–4 semanas | Ficha conectada, actividad, tareas, archivos e importación | Fase 0 |
| 2. Seguimiento comercial | P1 | 3–4 semanas | Pantalla «Hoy», reglas y seguimiento de visitas | Fase 1 |
| 3. Operación hasta la firma | P1 | 4–6 semanas | Ofertas, hitos y gestión de bloqueos | Fases 1 y 2 |
| 4. Colaboración con propietario | P1 | 3–4 semanas | Espacio privado y decisiones compartidas | Fases 1 y 3 |
| 5. Demanda y captación | P1 | 4–6 semanas | Cruces explicables y demanda no cubierta | Fases 1 y 2; datos suficientes |
| 6. Rentabilidad | P2 | 3–5 semanas | Costes, cobros y resultados por canal | Fases 1 y 3; datos suficientes |

Horizonte orientativo: 21–31 semanas de trabajo secuencial con el equipo supuesto. Reestimar al terminar la fase 0 y después de cada piloto. Una integración externa especialmente compleja se presupuestará como entrega independiente.

## Fase 0 — Fiabilidad y definición del producto

**Resultado:** disponer de una base reproducible y de un flujo comercial cuyos datos sean consistentes.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F0-01 | Corregir errores de compilación y reconstruir el entorno local del backend | La compilación termina correctamente y una instalación documentada permite arrancar la aplicación y aplicar migraciones |
| F0-02 | Unificar el cierre desde ficha, tablero y registro de venta | Marcar una propiedad como vendida abre o ejecuta el mismo flujo de cierre; crea una única venta y su comisión, incluso ante reintentos |
| F0-03 | Definir transiciones, reapertura y corrección de operaciones cerradas | Los cambios incompatibles se rechazan con explicación; las correcciones conservan la trazabilidad y la coherencia económica |
| F0-04 | Corregir nombres y fórmulas de indicadores | Asistencia a visitas, conversión a oferta, conversión a cierre y métricas acumuladas tienen definiciones separadas y periodos explícitos |
| F0-05 | Verificar permisos e integridad entre entidades | Las pruebas cubren agencias distintas, roles, asignaciones y referencias entre clientes, propiedades, visitas y ventas |
| F0-06 | Incorporar comprobaciones automáticas de los flujos críticos | Se comprueban acceso, creación de oportunidad, visita y cierre; un cambio que los rompe impide dar la entrega por válida |

**F0-01 completada (15/09/2026):** compilación del frontend corregida; entorno local
del backend reconstruido con Python 3.12 y `uv.lock`; instalación local y Docker
documentadas en el [README](README.md#instalación-de-desarrollo-reproducible-f0-01).
Verificados el arranque de la API, registro e inicio de sesión con datos de prueba,
las diez migraciones desde una base PostgreSQL 15 vacía y su repetición sin cambios.
Incluye dos pruebas de configuración y arranque; la cobertura comercial de F0-06
sigue pendiente. Las comprobaciones usaron bases aisladas, sin modificar datos existentes.

**F0-02 implementada (15/09/2026):** formulario y operación de cierre comunes desde
Propiedades, tablero y Ventas; comprador, precio, agente y comisiones obligatorios;
acceso del agente asignado y de responsables de la agencia; transacción única,
reintentos y cierres concurrentes comprobados con PostgreSQL. Incluye importes
decimales, conservación de datos históricos e inventario de inconsistencias.
Las entradas de la interfaz se verifican con un DOM simulado; la inspección visual
en navegador real queda pendiente. Ver [reglas y validación de F0-02](docs/F0-02.md).

**F0-03 implementada (15/09/2026):** corrección y reapertura explícitas desde Ventas,
con motivo, versiones e historial. Las comisiones se corrigen o descuentan mediante
ajustes, conservando los pagos y facturas previos; la liquidación del agente incluye
todos los descuentos pendientes. Los cierres reabiertos dejan de contar en los
indicadores. Incluye pruebas de permisos, reintentos, concurrencia y coherencia
económica; migración probada en bases aisladas y aplicada a la instalación,
según confirmación del usuario.
Verificadas las pantallas en Chrome con datos ficticios. Ver [F0-03](docs/F0-03.md).

**F0-04 implementada (15/09/2026):** asistencia y conversión visita → cierre con
fórmulas independientes; ofertas identificadas como no disponibles hasta disponer
de su registro. Periodos y comparaciones UTC explícitos, series mensuales completas,
cartera actual separada de actividad y comisiones devengadas diferenciadas de pagos.
Verificado con 130 pruebas backend, 36 de interfaz, compilación y revisión visual
en Chrome con datos ficticios. No requiere migración. Ver
[diccionario y validación de F0-04](docs/F0-04.md).

Trabajo de producto asociado: observar el flujo de una captación, una visita y un cierre en las agencias piloto; acordar un glosario de estados y registrar una línea base de seguimiento. Inventariar los datos existentes antes de modificar el modelo.

**Puerta de salida:** completar el recorrido inmueble → cliente → visita → venta → comisión sin inconsistencias. Acordar el canal de entrada y el portal prioritarios para los pilotos, y comprobar la disponibilidad de integración.

## Fase 1 — Datos conectados y herramientas de trabajo diario

**Resultado:** que el agente encuentre en una ficha el contexto necesario para actuar y pueda registrar información sin duplicarla.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F1-01 | Relacionar inmuebles con propietarios del CRM | Se puede vincular uno o varios titulares, editar el contacto una sola vez y consultar sus inmuebles; la migración no fusiona personas por coincidencias dudosas |
| F1-02 | Separar persona, demanda y oportunidad | Una persona puede ser propietaria y compradora, tener varias búsquedas y participar en oportunidades distintas sin duplicar su identidad |
| F1-03 | Incorporar historial de actividad | Llamadas registradas, notas, visitas y cambios relevantes muestran autor, fecha y entidad; las notas internas se distinguen de la información compartible |
| F1-04 | Añadir tareas y siguiente acción | Cada tarea tiene responsable, vencimiento, estado y vínculo con cliente, inmueble u oportunidad |
| F1-05 | Completar ficha y archivos del inmueble | Fotografías ordenables, documentos categorizados y campos de ascensor, exterior, terraza, estado y ubicación; archivos privados accesibles solo por los roles previstos |
| F1-06 | Importar y exportar cartera y contactos | La importación presenta previsualización, errores y posibles duplicados antes de confirmar; repetir una importación identificable no duplica registros |
| F1-07 | Registrar procedencia y entrada de contactos | Un formulario o canal de entrada elegido crea una oportunidad con origen, fecha y responsable, manteniendo la relación con contactos existentes |
| F1-08 | Facilitar el uso en móvil | El agente puede consultar el contexto, registrar una nota y completar una visita sin desplazamientos horizontales ni formularios innecesarios |

Alcance de integraciones: empezar con un canal utilizado por los pilotos. Conservar desde ahora identificadores externos y estados de sincronización. Para publicación, reutilizar una pasarela disponible si encaja; no intentar conectar todos los portales en esta fase.

La nueva relación de propietarios deberá conservar la información antigua y marcar los casos que requieren revisión. Evitar asociaciones automáticas basadas únicamente en nombre.

**Puerta de salida:** cargar una muestra representativa de cartera, resolver duplicados y trabajar una oportunidad completa desde sus fichas relacionadas.

## Fase 2 — Seguimiento comercial y pantalla «Hoy»

**Resultado:** que ninguna oportunidad relevante quede sin una siguiente acción visible.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F2-01 | Crear la pantalla «Hoy» del agente | Agrupa agenda, tareas vencidas y oportunidades pendientes; cada elemento permite abrir el contexto y realizar la acción |
| F2-02 | Implementar reglas de seguimiento | Detecta contacto sin atender, visita sin seguimiento, propietario sin actualización e inmueble con actividad sin ofertas; umbrales configurables por agencia |
| F2-03 | Añadir explicación y tratamiento de avisos | Cada aviso muestra su motivo y permite completar, posponer o descartar con razón; la misma condición no crea avisos repetidos |
| F2-04 | Estructurar el resultado de las visitas | Se registran interés, objeciones, motivo de descarte y siguiente paso con un formulario breve |
| F2-05 | Unificar disponibilidad de agenda | La detección de solapamientos se aplica al crear y modificar visitas y citas; los avisos aparecen antes de confirmar la reserva |
| F2-06 | Implantar recordatorios y seguimiento externo | Un canal acordado permite programar recordatorios, comprobar entregas fallidas y evitar duplicados; respeta preferencias de contacto |
| F2-07 | Crear supervisión para responsables | El gerente ve oportunidades desatendidas y carga de trabajo, y puede reasignar o intervenir |

Primera versión: reglas deterministas y plantillas. La IA se incorporará después como ayuda para resumir contexto y redactar borradores; no será una dependencia para priorizar o ejecutar el seguimiento.

La pantalla del gerente deberá distinguir una tarea pendiente de un problema confirmado. El agente podrá corregir o descartar una señal con motivo, lo que permitirá ajustar las reglas.

**Puerta de salida:** los agentes piloto utilizan la pantalla para organizar su trabajo y las alertas producen acciones registradas. Revisar ruido y utilidad antes de añadir más reglas.

## Fase 3 — Expediente de operación y cierre

**Resultado:** que cada negociación tenga condiciones, hitos y bloqueos visibles hasta la firma.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F3-01 | Crear el expediente de operación | Relaciona inmueble, participantes, agentes, ofertas, tareas y documentos; admite oportunidades alternativas antes del cierre |
| F3-02 | Registrar ofertas y contrapropuestas | Conserva versiones, importe, condiciones, fechas y respuesta; permite compararlas sin perder el historial |
| F3-03 | Configurar hitos y requisitos | Cada hito tiene fecha, responsable y requisitos; el equipo ve lo completado, pendiente y no aplicable |
| F3-04 | Detectar bloqueos y vencimientos | Señala qué requisito falta, quién debe actuar y qué hito depende de él; desaparece al resolverse la condición |
| F3-05 | Vincular documentos y firma mediante proveedor | Se conoce la versión enviada, participantes y estado; los eventos repetidos del proveedor no duplican acciones |
| F3-06 | Conectar cierre y comisiones | Cerrar una operación utiliza el flujo único de la fase 0 y conserva comprador, precio final y reparto acordado |
| F3-07 | Registrar pérdida o cancelación | Conserva motivos, fase alcanzada y tareas de cierre; devuelve el inmueble al estado que corresponda sin borrar historial |

Extensión condicionada: relaciones entre operaciones cuando una compra depende de una venta previa. Empezar con vínculos y fechas compartidas; desarrollar una visualización de la cadena solo si los pilotos presentan suficientes casos. Si requiere coordinación entre agencias, tratarla como alcance posterior con permisos específicos.

**Puerta de salida:** completar una simulación representativa y acompañar operaciones reales, incluyendo una oferta rechazada y una cancelación, sin recurrir a un seguimiento paralelo para los hitos cubiertos.

## Fase 4 — Espacio del propietario y decisiones compartidas

**Resultado:** que el propietario entienda el trabajo realizado y pueda responder a propuestas concretas.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F4-01 | Dar acceso privado al propietario | Ve únicamente los inmuebles y documentos autorizados; se puede revocar el acceso y verificarlo con pruebas |
| F4-02 | Mostrar actividad y evolución | Presenta visitas realizadas, ofertas compartibles y acciones relevantes, con fechas y definiciones comprensibles |
| F4-03 | Recoger decisiones sobre comercialización | El agente propone una acción, el propietario responde y queda registrada la versión aceptada; los cambios de precio pasan por un flujo explícito |
| F4-04 | Preparar informes periódicos | El resumen se apoya en datos registrados y evita revelar contactos de compradores o notas internas |
| F4-05 | Resumir objeciones de visitas | Agrupa motivos y muestra el tamaño de la muestra; distingue observaciones de interpretaciones del agente |
| F4-06 | Añadir avisos de decisiones pendientes | Agente y propietario conocen qué respuesta falta y desde cuándo, sin recibir mensajes repetidos |

Primera versión: web adaptada a móvil, sin aplicación nativa. No incluir una valoración automática del inmueble ni recomendar bajadas de precio solo por antigüedad del anuncio.

**Puerta de salida:** propietarios piloto consultan la información y responden a propuestas; todas las cifras se pueden reconciliar con la actividad interna compartida.

## Fase 5 — Cruces explicables y captación por demanda

**Resultado:** orientar las visitas y la captación hacia necesidades reales y vigentes.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F5-01 | Ampliar las demandas | Recogen requisitos obligatorios, preferencias, zonas, plazo y fecha de última confirmación; se pueden pausar o cerrar |
| F5-02 | Mejorar el motor de cruces | Respeta restricciones obligatorias, explica coincidencias y concesiones y señala datos desconocidos sin asumir que se cumplen |
| F5-03 | Incorporar el aprendizaje de visitas | Propone ajustes de preferencias a partir de motivos registrados; el agente confirma los cambios |
| F5-04 | Calcular demanda no cubierta | Agrupa compradores únicos con búsqueda vigente y los compara con oferta compatible; distingue coincidencias exactas y aproximadas |
| F5-05 | Crear una vista de oportunidades de captación | Prioriza combinaciones de zona, características y presupuesto con demanda insuficientemente cubierta y permite ver cómo se calculan |
| F5-06 | Preparar argumentarios de captación | Genera una presentación con datos agregados, fecha y criterios de actividad; no expone información personal ni promete compradores garantizados |

Primera versión: tabla filtrable y reglas explicables. El mapa se añadirá cuando las ubicaciones estén normalizadas. La recomendación de financiación se limita al estado declarado por el cliente y no se presenta como aprobación crediticia.

**Puerta de salida:** se puede rastrear cada agregado hasta demandas válidas; se registra qué captaciones y visitas provienen de estas recomendaciones y sus resultados.

## Fase 6 — Rentabilidad de operaciones y canales

**Resultado:** que dirección pueda relacionar captación, trabajo comercial, cierre y resultado económico.

| ID | Mejora a implementar | Criterio de aceptación |
|---|---|---|
| F6-01 | Registrar costes directos | Cada coste tiene importe, categoría, fecha y vínculo con una operación, inmueble o canal |
| F6-02 | Separar honorarios, cobros y pagos | Distingue honorarios generados, cobros de la agencia y pagos a agentes; admite pagos parciales y no confunde caja con venta |
| F6-03 | Calcular margen de contribución | La fórmula identifica los costes incluidos y el periodo; no presenta el resultado como beneficio neto total de la empresa |
| F6-04 | Seguir el origen hasta el cierre | Deduplica contactos y aplica un criterio explícito de atribución; muestra operaciones sin origen identificado |
| F6-05 | Informar resultados por canal | Presenta contactos, oportunidades, ofertas, cierres y coste por cierre; distingue cohortes todavía abiertas |
| F6-06 | Exportar o integrar con contabilidad | Los datos se concilian con una muestra de operaciones; cualquier proveedor se integra con un alcance y contrato de datos definidos |

El registro de procedencia empieza en la fase 1 para disponer de historial cuando llegue esta fase. No construir un sistema contable completo dentro de este roadmap.

**Puerta de salida:** el gerente puede reconstruir los importes de una muestra de operaciones y comparar canales sin mezclar periodos o interpretar oportunidades abiertas como pérdidas.

## Hitos de entrega

| Hito | Momento orientativo | Qué debe poder demostrarse |
|---|---|---|
| A. Base consistente | Final de fase 0 | Un cierre genera datos coherentes desde cualquier pantalla |
| B. Piloto comercial | Final de fase 2; 7–10 semanas acumuladas | El agente organiza su trabajo y registra seguimiento desde la aplicación |
| C. Operación completa | Final de fase 3; 11–16 semanas acumuladas | Ofertas, documentos y bloqueos coordinados hasta el cierre |
| D. Servicio visible | Final de fase 4; 14–20 semanas acumuladas | El propietario consulta y responde a decisiones concretas |
| E. Captación orientada | Final de fase 5; 18–26 semanas acumuladas | La demanda vigente orienta captaciones y recomendaciones |
| F. Gestión económica | Final de fase 6; 21–31 semanas acumuladas | Se relacionan canales, operaciones, costes y cobros |

Estos hitos describen alcance de producto. La disponibilidad comercial también dependerá de migración, soporte, puesta en marcha e integraciones necesarias para cada agencia.

## Medición del piloto

Registrar la línea base durante las fases 0 y 1. Los siguientes umbrales son objetivos iniciales propuestos, sujetos a revisión; no resultados ya observados.

| Indicador | Definición | Objetivo inicial |
|---|---|---|
| Oportunidades con siguiente acción | Oportunidades abiertas con responsable y tarea futura / oportunidades abiertas | Al menos 90% |
| Seguimiento tras visita | Visitas realizadas con seguimiento registrado dentro del plazo acordado / visitas realizadas | Al menos 80%; plazo inicial de 24 horas laborables |
| Calidad de las alertas | Alertas consideradas útiles por los agentes / alertas revisadas | Medir semanalmente y reducir reglas con mucho descarte |
| Control de hitos | Hitos próximos con responsable y estado actualizado / hitos próximos | Al menos 90% |
| Uso del espacio del propietario | Propietarios invitados que consultan o responden durante el periodo | Establecer objetivo tras la primera cohorte |
| Calidad de demanda | Demandas vigentes con requisitos y fecha de confirmación / demandas activas | Al menos 80% antes de impulsar captación por demanda |
| Resultado comercial | Visita → oferta, oferta → cierre, duración y causas de pérdida | Comparar cohortes semejantes con la línea base |

Los primeros indicadores prueban adopción y disciplina operativa. La mejora de ventas necesita ciclos más largos y no debe atribuirse automáticamente al software por una comparación antes/después con poca muestra.

## Reglas de implementación

- Mantener React, FastAPI y PostgreSQL; ampliar la arquitectura existente antes de introducir nuevos servicios independientes.
- Centralizar las reglas de negocio compartidas por ficha, tablero, API e integraciones.
- Conservar eventos e historial desde el principio para explicar avisos y reconstruir resultados.
- Usar importes decimales y reglas explícitas de redondeo en los nuevos flujos económicos, con migración comprobada de los importes existentes.
- Incorporar trabajos en segundo plano, reintentos y deduplicación cuando se introduzcan recordatorios, informes e integraciones.
- Tratar documentos y accesos de propietarios como recursos con permisos propios, no como enlaces públicos permanentes.
- Diseñar las integraciones con estados de error visibles y recuperación, empezando por el proveedor más utilizado por los pilotos.
- Probar comportamientos críticos de cada fase, incluyendo permisos, migraciones y reintentos. Verificar en móvil los flujos usados durante visitas.
- Introducir IA donde reduzca trabajo de redacción o lectura, con fuentes visibles y corrección humana; mantener los cálculos y cambios de estado bajo reglas explícitas.

## Funcionalidades aplazadas

| Funcionalidad | Motivo | Cuándo reconsiderarla |
|---|---|---|
| Gestión recurrente de alquileres y comunidades | Requiere procesos y modelo económico distintos | Cuando ese segmento sea una decisión explícita de producto |
| Red propia de colaboración entre agencias | Necesita participación suficiente y permisos específicos | Con una base activa y demanda de colaboración comprobada |
| Aplicación móvil nativa | Aumenta mantenimiento antes de validar los flujos | Si la web móvil resulta insuficiente para tareas concretas |
| Valoración automática y predicción de cierre | Requiere datos representativos y validación | Cuando haya histórico suficiente y una fuente de datos adecuada |
| Integración con todos los portales | Alto coste y dependencia de proveedores | Según demanda comercial y uso real de cada portal |
| Chatbot genérico como producto central | Contribuye poco a los resultados prioritarios por sí solo | Como interfaz adicional de flujos ya útiles |

## Primer bloque de trabajo

1. Resolver F0-01 y documentar una instalación reproducible.
2. Definir el flujo único de cierre y sus correcciones con ejemplos de negocio.
3. Implementar F0-02 y las pruebas que eviten ventas o comisiones duplicadas.
4. Acordar el diccionario de indicadores y corregir sus cálculos y etiquetas.
5. Revisar permisos y referencias entre entidades con los casos de F0-05.
6. Validar con las agencias piloto el modelo de persona, propietario, demanda, oportunidad y operación antes de migrar datos.

## Base del roadmap

Propuesta elaborada a partir del análisis del código y de la conversación del proyecto. La compilación del frontend falló durante esa revisión; las comprobaciones del backend no pudieron ejecutarse por el entorno Python local. La presencia de módulos en el código no equivale a una validación completa de funcionamiento en producción.

El contraste competitivo anterior mostró que asistentes por WhatsApp, cruces, ofertas y espacios del propietario ya se anuncian en otras soluciones. Por eso la prioridad de este roadmap está en conectar esas capacidades con acciones y resultados medibles, sin presuponer exclusividad: [IA de Inmovilla](https://www.inmovilla.com/ia-inmobiliaria), [CRM de Witei](https://get.witei.com/es/crm-inmobiliario/) y [CRM de Inmoweb](https://www.inmoweb.es/crm-inmobiliario/).
